from __future__ import annotations

import json
import os
from datetime import datetime, time
from pathlib import Path

import requests
import yfinance as yf
from zoneinfo import ZoneInfo


NY = ZoneInfo("America/New_York")
BERLIN = ZoneInfo("Europe/Berlin")

STATE_PATH = Path("state/push_state.json")
RADAR_PATH = Path("data/radar.json")
CONFIG_PATH = Path("config.json")


def load_json(path, default):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def market_window_open(now_ny):
    return (
        now_ny.weekday() < 5
        and time(9, 45)
        <= now_ny.time()
        <= time(16, 15)
    )


def latest_price(ticker):
    """
    Fresh regular-session price only.
    Never reuse yesterday's last bar.
    """
    try:
        d = yf.download(
            ticker,
            period="2d",
            interval="5m",
            prepost=False,
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if d.empty:
            return None

        if hasattr(d.columns, "levels"):
            try:
                d.columns = (
                    d.columns.get_level_values(0)
                )
            except Exception:
                pass

        idx = d.index

        local = (
            idx.tz_convert(NY)
            if idx.tz is not None
            else idx.tz_localize(NY)
        )

        d = d.copy()
        d.index = local

        now = datetime.now(NY)

        d = d[
            d.index.date == now.date()
        ]

        d = d[
            (
                (d.index.hour > 9)
                |
                (
                    (d.index.hour == 9)
                    &
                    (d.index.minute >= 30)
                )
            )
            &
            (d.index.hour < 16)
        ]

        if d.empty:
            return None

        close = d["Close"].dropna()

        if not len(close):
            return None

        age = (
            now -
            close.index[-1].to_pydatetime()
        ).total_seconds() / 60

        if age > 20:
            return None

        return float(close.iloc[-1])

    except Exception as e:
        print(
            "Price lookup failed:",
            ticker,
            e
        )
        return None


def usd_to_eur_rate():
    """
    Best-effort live USD -> EUR conversion.
    """
    try:
        d = yf.download(
            "EURUSD=X",
            period="2d",
            interval="5m",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if d.empty:
            return None

        if hasattr(d.columns, "levels"):
            try:
                d.columns = (
                    d.columns.get_level_values(0)
                )
            except Exception:
                pass

        close = d["Close"].dropna()

        if not len(close):
            return None

        eurusd = float(
            close.iloc[-1]
        )

        if eurusd <= 0:
            return None

        return 1.0 / eurusd

    except Exception as e:
        print(
            "FX lookup failed:",
            e
        )
        return None


def push(
    title,
    message,
    priority="default",
    tags="bell"
):
    topic = os.environ.get(
        "NTFY_TOPIC",
        ""
    ).strip()

    if not topic:
        print(
            "NTFY_TOPIC not configured; "
            "skipping push."
        )
        return False

    server = os.environ.get(
        "NTFY_SERVER",
        "https://ntfy.sh"
    ).rstrip("/")

    try:
        token = os.environ.get(
            "NTFY_TOKEN",
            ""
        ).strip()

        token = (
            token
            .encode(
                "ascii",
                "ignore"
            )
            .decode("ascii")
        )

        safe_title = (
            str(title)
            .encode(
                "ascii",
                "ignore"
            )
            .decode("ascii")
            .strip()
            or "Investment Radar"
        )

        safe_priority = (
            str(priority)
            .encode(
                "ascii",
                "ignore"
            )
            .decode("ascii")
        )

        safe_tags = (
            str(tags)
            .encode(
                "ascii",
                "ignore"
            )
            .decode("ascii")
        )

        headers = {
            "Title": safe_title,
            "Priority": safe_priority,
            "Tags": safe_tags
        }

        if token:
            headers["Authorization"] = (
                f"Bearer {token}"
            )

        r = requests.post(
            f"{server}/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=20
        )

        r.raise_for_status()

        print(
            "Push sent:",
            title
        )

        return True

    except Exception as e:
        print(
            "Push failed:",
            e
        )
        return False


def worker_headers():
    token = os.environ.get(
        "MONITOR_TOKEN",
        ""
    ).strip()

    if not token:
        return None

    return {
        "Authorization":
            f"Bearer {token}",
        "Accept":
            "application/json"
    }


def acknowledge_trade(
    worker_url,
    trade_id,
    headers
):
    try:
        r = requests.post(
            f"{worker_url}/trades/ack",
            json={
                "id": trade_id
            },
            headers=headers,
            timeout=20
        )

        if r.status_code == 404:
            print(
                "Trade already acknowledged:",
                trade_id
            )
            return True

        r.raise_for_status()

        print(
            "Trade acknowledged:",
            trade_id
        )

        return True

    except Exception as e:
        print(
            "Trade ACK failed:",
            trade_id,
            e
        )
        return False


def import_manual_positions(state):
    """
    Import real dashboard purchases from
    Cloudflare TRADE_QUEUE.

    No TRADE_BUY_JSON ntfy transport anymore.
    """

    worker_url = os.environ.get(
        "WORKER_URL",
        ""
    ).strip().rstrip("/")

    if not worker_url:
        print(
            "WORKER_URL not configured; "
            "skipping trade import."
        )
        return state

    headers = worker_headers()

    if headers is None:
        print(
            "MONITOR_TOKEN not configured; "
            "skipping trade import."
        )
        return state

    try:
        r = requests.get(
            f"{worker_url}/trades/pending",
            headers=headers,
            timeout=20
        )

        r.raise_for_status()

        data = r.json()

        trades = data.get(
            "trades",
            []
        )

        if not isinstance(
            trades,
            list
        ):
            print(
                "Worker returned invalid "
                "trade list."
            )
            return state

        state.setdefault(
            "positions",
            {}
        )

        imported_ids = set(
            state.get(
                "imported_trade_ids",
                []
            )
            or []
        )

        for trade in trades:
            if not isinstance(
                trade,
                dict
            ):
                continue

            trade_id = str(
                trade.get(
                    "id",
                    ""
                )
            ).strip()

            ticker = str(
                trade.get(
                    "ticker",
                    ""
                )
            ).upper().strip()

            try:
                entry = float(
                    trade.get(
                        "entry",
                        0
                    )
                    or 0
                )

                qty = float(
                    trade.get(
                        "qty",
                        0
                    )
                    or 0
                )

                stop_pct = float(
                    trade.get(
                        "stop_pct",
                        0
                    )
                    or 0
                )

                target_pct = float(
                    trade.get(
                        "target_pct",
                        0
                    )
                    or 0
                )

            except (
                TypeError,
                ValueError
            ):
                print(
                    "Invalid trade numbers:",
                    trade
                )
                continue

            bought_at = (
                trade.get("bought_at")
                or
                datetime.now(NY)
                .isoformat()
            )

            entry_currency = str(
                trade.get(
                    "entry_currency",
                    "EUR"
                )
            ).upper().strip()

            if (
                not trade_id
                or not ticker
                or entry <= 0
                or qty <= 0
            ):
                print(
                    "Skipping invalid trade:",
                    trade
                )
                continue

            /*
             * Python doesn't use JS comments.
             */
