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
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def market_window_open(now_ny):
    return (
        now_ny.weekday() < 5
        and time(9, 45) <= now_ny.time() <= time(16, 15)
    )


def latest_price(ticker):
    """Fresh regular-session price only; never reuse yesterday's last bar."""
    try:
        d = yf.download(
            ticker,
            period="2d",
            interval="5m",
            prepost=False,
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if d.empty:
            return None

        if hasattr(d.columns, "levels"):
            try:
                d.columns = d.columns.get_level_values(0)
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

        d = d[d.index.date == now.date()]

        d = d[
            (
                (d.index.hour > 9)
                | (
                    (d.index.hour == 9)
                    & (d.index.minute >= 30)
                )
            )
            & (d.index.hour < 16)
        ]

        if d.empty:
            return None

        close = d["Close"].dropna()

        if not len(close):
            return None

        age = (
            now - close.index[-1].to_pydatetime()
        ).total_seconds() / 60

        if age > 20:
            return None

        return float(close.iloc[-1])

    except Exception as e:
        print("Price lookup failed:", ticker, e)
        return None


def usd_to_eur_rate():
    """Best-effort live USD->EUR conversion for monitoring TR EUR entries."""
    try:
        d = yf.download(
            "EURUSD=X",
            period="2d",
            interval="5m",
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if d.empty:
            return None

        if hasattr(d.columns, "levels"):
            try:
                d.columns = d.columns.get_level_values(0)
            except Exception:
                pass

        close = d["Close"].dropna()

        if not len(close):
            return None

        eurusd = float(close.iloc[-1])

        return (1.0 / eurusd) if eurusd > 0 else None

    except Exception as e:
        print("FX lookup failed:", e)
        return None


def push(title, message, priority="default", tags="bell"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()

    if not topic:
        print("NTFY_TOPIC not configured; skipping push.")
        return False

    server = os.environ.get(
        "NTFY_SERVER",
        "https://ntfy.sh",
    ).rstrip("/")

    try:
        token = os.environ.get("NTFY_TOKEN", "").strip()

        # HTTP headers ASCII-safe halten.
        token = token.encode("ascii", "ignore").decode("ascii")

        safe_title = (
            str(title)
            .encode("ascii", "ignore")
            .decode("ascii")
            .strip()
            or "Investment Radar"
        )

        safe_priority = (
            str(priority)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

        safe_tags = (
            str(tags)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

        headers = {
            "Title": safe_title,
            "Priority": safe_priority,
            "Tags": safe_tags,
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        r = requests.post(
            f"{server}/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=20,
        )

        r.raise_for_status()

        print("Push sent:", title)
        return True

    except Exception as e:
        print("Push failed:", e)
        return False


def import_manual_positions(state):
    """
    Importiert echte Dashboard-Käufe aus der
    geschützten Cloudflare TRADE_QUEUE.

    TRADE_BUY_JSON über ntfy wird nicht mehr verwendet.
    """

    worker_url = os.environ.get(
        "WORKER_URL",
        "",
    ).strip().rstrip("/")

    monitor_token = os.environ.get(
        "MONITOR_TOKEN",
        "",
    ).strip()

    if not worker_url:
        print("WORKER_URL not configured; skipping trade import.")
        return state

    if not monitor_token:
        print("MONITOR_TOKEN not configured; skipping trade import.")
        return state

    headers = {
        "Authorization": f"Bearer {monitor_token}",
        "Accept": "application/json",
    }

    try:
        r = requests.get(
            f"{worker_url}/trades/pending",
            headers=headers,
            timeout=20,
        )

        r.raise_for_status()

        data = r.json()
        trades = data.get("trades", [])

        if not isinstance(trades, list):
            print("Worker returned invalid trade list.")
            return state

        state.setdefault("positions", {})

        imported_ids = set(
            state.get("imported_trade_ids", []) or []
        )

        for trade in trades:
            if not isinstance(trade, dict):
                continue

            trade_id = str(
                trade.get("id", "")
            ).strip()

            ticker = str(
                trade.get("ticker", "")
            ).upper().strip()

            try:
                entry = float(
                    trade.get("entry", 0) or 0
                )

                qty = float(
                    trade.get("qty", 0) or 0
                )

                stop_pct = float(
                    trade.get("stop_pct", 0) or 0
                )

                target_pct = float(
                    trade.get("target_pct", 0) or 0
                )

            except (TypeError, ValueError):
                print("Invalid trade numbers:", trade)
                continue

            bought_at = (
                trade.get("bought_at")
                or datetime.now(NY).isoformat()
            )

            entry_currency = str(
                trade.get("entry_currency", "EUR")
            ).upper().strip()

            if (
                not trade_id
                or not ticker
                or entry <= 0
                or qty <= 0
            ):
                print("Skipping invalid trade:", trade)
                continue

            # Falls GitHub den Trade schon importiert hat,
            # aber ACK beim letzten Lauf fehlgeschlagen ist.
            if trade_id in imported_ids:
                try:
                    ack = requests.post(
                        f"{worker_url}/trades/ack",
                        json={"id": trade_id},
                        headers=headers,
                        timeout=20,
                    )

                    if ack.ok or ack.status_code == 404:
                        print(
                            "Queued duplicate already handled:",
                            trade_id,
                        )

                except Exception as e:
                    print(
                        "Duplicate ACK warning:",
                        trade_id,
                        e,
                    )

                continue

            state["positions"][ticker] = {
                "entry": entry,
                "qty": qty,
                "stop_pct": stop_pct,
                "target_pct": target_pct,
                "opened_at": bought_at,
                "entry_currency": entry_currency,
                "status": "real_open",
                "source": "dashboard_worker_queue",
                "trade_id": trade_id,
            }

            imported_ids.add(trade_id)

            state["imported_trade_ids"] = list(
                imported_ids
            )[-500:]

            # WICHTIG:
            # Erst lokal speichern.
            # Erst danach darf der Worker den KV-Eintrag löschen.
            save_json(STATE_PATH, state)

            print(
                "Imported real position:",
                ticker,
                entry,
                qty,
                entry_currency,
            )

            try:
                ack = requests.post(
                    f"{worker_url}/trades/ack",
                    json={"id": trade_id},
                    headers=headers,
                    timeout=20,
                )

                if ack.ok:
                    print(
                        "Trade acknowledged:",
                        trade_id,
                    )

                else:
                    print(
                        "Trade ACK failed:",
                        trade_id,
                        ack.status_code,
                        ack.text[:300],
                    )

            except Exception as e:
                print(
                    "Trade ACK failed:",
                    trade_id,
                    e,
                )

        state["imported_trade_ids"] = list(
            imported_ids
        )[-500:]

        return state

    except Exception as e:
        print("Worker trade import failed:", e)
        return state


def effective_risk_settings(state, config):
    s = dict(config or {})

    s.update(
        state.get("risk_settings", {}) or {}
    )

    return s


def suggested_investment_eur(stop_pct, config):
    """
    Return a EUR position amount from portfolio risk
    and max-position cap.

    Because stop_pct is percentage based, this calculation
    is currency-neutral:

    position_eur * stop_pct/100 <= allowed risk_eur
    """

    portfolio = config.get("portfolio_eur")

    risk_pct = config.get(
        "risk_per_trade_pct",
        0.5,
    )

    max_position_pct = config.get(
        "max_position_pct",
        10.0,
    )

    if not portfolio or not stop_pct:
        return None

    try:
        portfolio = float(portfolio)
        stop_pct = float(stop_pct)
        risk_pct = float(risk_pct)
        max_position_pct = float(max_position_pct)

    except (TypeError, ValueError):
        return None

    if (
        portfolio <= 0
        or stop_pct <= 0
        or risk_pct <= 0
        or max_position_pct <= 0
    ):
        return None

    risk_eur = (
        portfolio
        * risk_pct
        / 100.0
    )

    by_risk_eur = (
        risk_eur
        / (stop_pct / 100.0)
    )

    cap_eur = (
        portfolio
        * max_position_pct
        / 100.0
    )

    amount = min(
        by_risk_eur,
        cap_eur,
    )

    return round(
        max(0.0, amount),
        2,
    )


def main():
    now_ny = datetime.now(NY)

    radar = load_json(
        RADAR_PATH,
        {},
    )

    config = load_json(
        CONFIG_PATH,
        {},
    )

    state = load_json(
        STATE_PATH,
        {
            "signals": {},
            "positions": {},
        },
    )

    state.setdefault(
        "signals",
        {},
    )

    state.setdefault(
        "positions",
        {},
    )

    # Alte virtuelle Positionen entfernen.
    # Nur tatsächlich im Dashboard gespeicherte
    # Käufe dürfen Exit-Alarme auslösen.
    state["positions"] = {
        t: pos
        for t, pos in state["positions"].items()
        if pos.get("status") != "virtual_open"
    }

    # Neue echte Positionen aus Cloudflare importieren.
    # Das geschieht auch außerhalb der Handelszeit.
    state = import_manual_positions(state)

    risk_settings = effective_risk_settings(
        state,
        config,
    )

    # Außerhalb des Überwachungsfensters werden neue
    # Positionen zwar importiert, aber keine Kurs-Signale geprüft.
    if not market_window_open(now_ny):
        state["last_check"] = (
            datetime.now(BERLIN).isoformat()
        )

        save_json(
            STATE_PATH,
            state,
        )

        print(
            "Outside regular US monitoring window:",
            now_ny.isoformat(),
        )

        return

    candidates = radar.get(
        "candidates",
        [],
    )

    today = now_ny.date().isoformat()

    # ==========================================================
    # 1) ENTRY SIGNALS
    # ==========================================================

    for c in candidates:
        ticker = c.get("ticker")

        if (
            not ticker
            or c.get("action_status") != "KAUF HEUTE"
        ):
            continue

        signal_key = f"{today}:{ticker}"

        if state["signals"].get(signal_key):
            continue

        price = latest_price(ticker)

        if price is None:
            continue

        stop_pct = float(
            c.get("stop_pct") or 0
        )

        target_pct = float(
            c.get("target_pct") or 0
        )

        investment_eur = suggested_investment_eur(
            stop_pct,
            risk_settings,
        )

        stop_price = (
            price * (1 - stop_pct / 100)
            if stop_pct
            else None
        )

        target_price = (
            price * (1 + target_pct / 100)
            if target_pct
            else None
        )

        if (
            investment_eur is not None
            and investment_eur >= 1
        ):
            investment_text = (
                f"\nVorgeschlagener Einsatz: "
                f"{investment_eur:.2f} EUR"
            )

        else:
            investment_text = (
                "\nKEIN KAUF - sinnvolle "
                "Positionsgroesse nicht berechenbar."
            )

        msg = (
            f"{ticker} erfüllt alle Dashboard-Regeln.\n"
            f"Referenzkurs: {price:.2f}\n"
            f"Score: {c.get('score', '–')}/100\n"
        )

        if stop_price:
            msg += (
                f"Stop/Invalidation: "
                f"ca. {stop_price:.2f} "
                f"({-stop_pct:.2f}%)\n"
            )

        if target_price:
            msg += (
                f"1. Ziel: "
                f"ca. {target_price:.2f} "
                f"(+{target_pct:.2f}%)\n"
            )

        msg += (
            f"Entry-Regel: "
            f"{c.get('entry_note', '')}"
            f"{investment_text}\n\n"

            "NACH DEM KAUF IM DASHBOARD EINTRAGEN:\n"

            f"Ticker: {ticker}\n"

            "Kaufkurs: tatsaechlicher "
            "TR-Ausfuehrungskurs in EUR\n"

            "Stueckzahl: tatsaechlich gekaufte "
            "Anteile (Dezimalstellen erlaubt)\n"

            "Kaufzeit: tatsaechliche "
            "Ausfuehrungszeit\n"

            f"Stop %: {stop_pct:.2f}\n"

            f"Gewinnziel %: "
            f"{target_pct:.2f}\n"

            "Danach: Position speichern "
            "& ueberwachen.\n"

            "Keine Gewinngarantie."
        )

        if push(
            f"ENTRY-SIGNAL {ticker}",
            msg,
            priority="high",
            tags="chart_with_upwards_trend",
        ):
            state["signals"][signal_key] = {
                "sent_at":
                    datetime.now(BERLIN).isoformat(),

                "price":
                    price,
            }

    # ==========================================================
    # 2) ECHTE POSITIONEN ÜBERWACHEN
    # ==========================================================

    for ticker, p in list(
        state["positions"].items()
    ):
        if p.get("status") != "real_open":
            continue

        price_usd = latest_price(ticker)

        if price_usd is None:
            continue

        entry_currency = str(
            p.get(
                "entry_currency",
                "EUR",
            )
        ).upper()

        # Dashboard/Trade Republic Kaufkurs ist normalerweise EUR.
        if entry_currency == "EUR":
            usd_eur = usd_to_eur_rate()

            if usd_eur is None:
                print(
                    "FX unavailable; "
                    "skipping EUR position monitoring for",
                    ticker,
                )
                continue

            price_eur = (
                price_usd
                * usd_eur
            )

        elif entry_currency == "USD":
            price_eur = price_usd

        else:
            print(
                "Unsupported entry currency:",
                ticker,
                entry_currency,
            )
            continue

        entry = float(
            p["entry"]
        )

        qty = p.get("qty")

        stop_pct = float(
            p.get("stop_pct") or 0
        )

        target_pct = float(
            p.get("target_pct") or 0
        )

        pnl_pct = (
            price_eur / entry - 1
        ) * 100

        pnl_eur = (
            (price_eur - entry)
            * float(qty)
            if qty
            else None
        )

        reason = None
        tags = "warning"

        # STOP
        if (
            stop_pct
            and pnl_pct <= -stop_pct
        ):
            reason = (
                "Stop/Invalidation erreicht "
                f"({pnl_pct:+.2f}%)."
            )

            tags = "rotating_light"

        # GEWINNZIEL
        elif (
            target_pct
            and pnl_pct >= target_pct
        ):
            reason = (
                "Erstes Gewinnziel erreicht "
                f"({pnl_pct:+.2f}%)."
            )

            tags = "moneybag"

        # ZEIT-EXIT
        else:
            try:
                opened = datetime.fromisoformat(
                    p["opened_at"]
                ).astimezone(NY)

                if (
                    now_ny.date() > opened.date()
                    and now_ny.time() >= time(15, 45)
                ):
                    reason = (
                        "Zeit-Exit: Position ist "
                        "vom Vortag "
                        f"({pnl_pct:+.2f}%)."
                    )

                    tags = "alarm_clock"

            except Exception:
                pass

        if reason:
            msg = (
                f"Echte Position {ticker}\n"

                f"Einstieg: "
                f"{entry:.2f} "
                f"{entry_currency}\n"

                + (
                    f"Stückzahl: {qty}\n"
                    if qty
                    else ""
                )

                + (
                    f"Aktueller Kurs "
                    f"(ca. {entry_currency}): "
                    f"{price_eur:.2f}\n"
                )

                + (
                    f"Veränderung: "
                    f"{pnl_pct:+.2f}%\n"
                )

                + (
                    f"Unrealisierter P/L: "
                    f"{pnl_eur:+.2f} "
                    f"{entry_currency}\n"
                    if pnl_eur is not None
                    else ""
                )

                + f"{reason}\n"

                + (
                    f"Aktion: {qty} Stück verkaufen / "
                    "Position vollständig schließen."
                    if qty
                    else
                    "Aktion: Position jetzt prüfen "
                    "und Exit erwägen."
                )
            )

            if push(
                f"EXIT-SIGNAL {ticker}",
                msg,
                priority="high",
                tags=tags,
            ):
                p["status"] = "exit_alerted"

                p["exit_alert_at"] = (
                    now_ny.isoformat()
                )

                p[
                    "exit_reference_price_eur"
                ] = price_eur

    # Signal-Historie begrenzen.
    if len(state["signals"]) > 500:
        keys = list(
            state["signals"].keys()
        )[-300:]

        state["signals"] = {
            k: state["signals"][k]
            for k in keys
        }

    state["last_check"] = (
        datetime.now(BERLIN).isoformat()
    )

    save_json(
        STATE_PATH,
        state,
    )

    print(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
