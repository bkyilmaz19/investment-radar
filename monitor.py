from __future__ import annotations
import json, os
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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def market_window_open(now_ny):
    # Give a small buffer around regular US market hours.
    return now_ny.weekday() < 5 and time(9, 25) <= now_ny.time() <= time(16, 15)

def latest_price(ticker):
    try:
        d = yf.download(ticker, period="1d", interval="5m", prepost=False,
                        auto_adjust=False, progress=False, threads=False)
        if d.empty:
            return None
        close = d["Close"]
        # yfinance may return DataFrame for one ticker in newer versions.
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        close = close.dropna()
        return float(close.iloc[-1]) if len(close) else None
    except Exception:
        return None

def push(title, message, priority="default", tags="bell"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("NTFY_TOPIC not configured; skipping push.")
        return False
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    try:
        r = requests.post(
            f"{server}/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": priority, "Tags": tags},
            timeout=20,
        )
        r.raise_for_status()
        print("Push sent:", title)
        return True
    except Exception as e:
        print("Push failed:", e)
        return False

def position_size(entry, stop_pct, config):
    portfolio = config.get("portfolio_eur")
    risk_pct = config.get("risk_per_trade_pct", 0.5)
    if not portfolio or not entry or not stop_pct:
        return None
    risk_eur = float(portfolio) * float(risk_pct) / 100.0
    loss_per_share = float(entry) * float(stop_pct) / 100.0
    if loss_per_share <= 0:
        return None
    return max(0, int(risk_eur // loss_per_share))

def main():
    now_ny = datetime.now(NY)
    if not market_window_open(now_ny):
        print("Outside regular US monitoring window:", now_ny.isoformat())
        return

    radar = load_json(RADAR_PATH, {})
    config = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {"signals": {}, "positions": {}})
    state.setdefault("signals", {})
    state.setdefault("positions", {})

    candidates = radar.get("candidates", [])
    today = now_ny.date().isoformat()

    # 1) New entry alerts: only once per ticker/day.
    for c in candidates:
        ticker = c.get("ticker")
        if not ticker or c.get("action_status") != "KAUF HEUTE":
            continue

        signal_key = f"{today}:{ticker}"
        if state["signals"].get(signal_key):
            continue

        price = latest_price(ticker)
        if price is None:
            continue

        stop_pct = float(c.get("stop_pct") or 0)
        target_pct = float(c.get("target_pct") or 0)
        qty = position_size(price, stop_pct, config)

        stop_price = price * (1 - stop_pct/100) if stop_pct else None
        target_price = price * (1 + target_pct/100) if target_pct else None

        qty_text = f"\nPositionsgröße nach deinem Risikolimit: {qty} Stück" if qty is not None else \
                   "\nPositionsgröße: nicht berechnet (portfolio_eur in config.json noch nicht gesetzt)."

        msg = (
            f"{ticker} erfüllt alle Dashboard-Regeln.\n"
            f"Referenzkurs: {price:.2f}\n"
            f"Score: {c.get('score','–')}/100\n"
            f"Stop/Invalidation: ca. {stop_price:.2f} ({-stop_pct:.2f}%)\n" if stop_price else
            f"{ticker} erfüllt alle Dashboard-Regeln.\nReferenzkurs: {price:.2f}\nScore: {c.get('score','–')}/100\n"
        )
        if target_price:
            msg += f"1. Ziel: ca. {target_price:.2f} (+{target_pct:.2f}%)\n"
        msg += f"Entry-Regel: {c.get('entry_note','')}{qty_text}\nKeine Gewinngarantie."

        if push(f"🟢 ENTRY-SIGNAL {ticker}", msg, priority="high", tags="chart_with_upwards_trend"):
            state["signals"][signal_key] = {"sent_at": datetime.now(BERLIN).isoformat(), "price": price}
            # Virtual tracking starts from the reference price. This is not proof the user actually bought.
            state["positions"][ticker] = {
                "entry": price,
                "stop_pct": stop_pct,
                "target_pct": target_pct,
                "opened_at": now_ny.isoformat(),
                "signal_key": signal_key,
                "status": "virtual_open"
            }

    # 2) Monitor virtual positions for exit conditions.
    for ticker, p in list(state["positions"].items()):
        if p.get("status") != "virtual_open":
            continue
        price = latest_price(ticker)
        if price is None:
            continue

        entry = float(p["entry"])
        stop_pct = float(p.get("stop_pct") or 0)
        target_pct = float(p.get("target_pct") or 0)
        pnl_pct = (price / entry - 1) * 100

        reason = None
        priority = "high"
        tags = "warning"

        if stop_pct and pnl_pct <= -stop_pct:
            reason = f"Stop/Invalidation erreicht ({pnl_pct:+.2f}%)."
            tags = "rotating_light"
        elif target_pct and pnl_pct >= target_pct:
            reason = f"Erstes Gewinnziel erreicht ({pnl_pct:+.2f}%)."
            tags = "moneybag"
        else:
            try:
                opened = datetime.fromisoformat(p["opened_at"]).astimezone(NY)
                # Time exit: by 15:45 ET on the next trading date or later.
                if now_ny.date() > opened.date() and now_ny.time() >= time(15,45):
                    reason = f"Zeit-Exit: Setup ist vom Vortag ({pnl_pct:+.2f}%)."
                    tags = "alarm_clock"
            except Exception:
                pass

        if reason:
            msg = (
                f"Virtuell überwachtes Setup {ticker}\n"
                f"Referenz-Einstieg: {entry:.2f}\n"
                f"Aktueller Kurs: {price:.2f}\n"
                f"Veränderung: {pnl_pct:+.2f}%\n"
                f"{reason}\n"
                f"Aktion: Position/Setup jetzt prüfen und Exit erwägen."
            )
            if push(f"🔴 EXIT-SIGNAL {ticker}", msg, priority=priority, tags=tags):
                p["status"] = "exit_alerted"
                p["exit_alert_at"] = now_ny.isoformat()
                p["exit_reference_price"] = price

    # Prune old signal keys after 14 days by keeping only recent positions/signals approximately.
    if len(state["signals"]) > 500:
        keys = list(state["signals"].keys())[-300:]
        state["signals"] = {k: state["signals"][k] for k in keys}

    state["last_check"] = datetime.now(BERLIN).isoformat()
    save_json(STATE_PATH, state)
    print(json.dumps(state, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
