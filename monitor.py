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
    return now_ny.weekday() < 5 and time(9, 25) <= now_ny.time() <= time(16, 15)

def latest_price(ticker):
    try:
        d = yf.download(ticker, period="1d", interval="5m", prepost=False,
                        auto_adjust=False, progress=False, threads=False)
        if d.empty:
            return None
        close = d["Close"]
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
        token = os.environ.get("NTFY_TOKEN", "").strip()
        headers = {"Title": title, "Priority": priority, "Tags": tags}
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
    """Import BUY events sent by the public dashboard through the private ntfy topic."""
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return state

    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    since = state.get("ntfy_last_event_id")
    params = {"poll": "1", "since": since if since else "24h"}

    try:
        token = os.environ.get("NTFY_TOKEN", "").strip()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = requests.get(
            f"{server}/{topic}/json",
            params=params,
            headers=headers,
            timeout=20,
        )
        r.raise_for_status()
        for line in r.text.splitlines():
            if not line.strip():
                continue
            evt = json.loads(line)
            if evt.get("id"):
                state["ntfy_last_event_id"] = evt["id"]
            if evt.get("event") != "message":
                continue

            msg = evt.get("message", "")
            if msg.startswith("RISK_SETTINGS_JSON:"):
                payload = json.loads(msg.split("RISK_SETTINGS_JSON:", 1)[1])
                portfolio = float(payload.get("portfolio_eur", 0) or 0)
                risk_pct = float(payload.get("risk_per_trade_pct", 0) or 0)
                max_position_pct = float(payload.get("max_position_pct", 0) or 0)
                if portfolio > 0 and 0 < risk_pct <= 5 and 0 < max_position_pct <= 100:
                    state["risk_settings"] = {
                        "portfolio_eur": portfolio,
                        "risk_per_trade_pct": risk_pct,
                        "max_position_pct": max_position_pct
                    }
                    print("Imported risk settings:", state["risk_settings"])
                continue

            if not msg.startswith("TRADE_BUY_JSON:"):
                continue

            payload = json.loads(msg.split("TRADE_BUY_JSON:", 1)[1])
            ticker = str(payload.get("ticker", "")).upper().strip()
            entry = float(payload.get("entry", 0) or 0)
            qty = int(payload.get("qty", 0) or 0)
            stop_pct = float(payload.get("stop_pct", 0) or 0)
            target_pct = float(payload.get("target_pct", 0) or 0)
            bought_at = payload.get("bought_at") or datetime.now(NY).isoformat()

            if not ticker or entry <= 0 or qty <= 0:
                continue

            state.setdefault("positions", {})
            state["positions"][ticker] = {
                "entry": entry,
                "qty": qty,
                "stop_pct": stop_pct,
                "target_pct": target_pct,
                "opened_at": bought_at,
                "status": "real_open",
                "source": "dashboard_manual"
            }
            print("Imported real position:", ticker, entry, qty)

        return state
    except Exception as e:
        print("Manual position import failed:", e)
        return state


def effective_risk_settings(state, config):
    s = dict(config or {})
    s.update(state.get("risk_settings", {}) or {})
    return s

def position_size(entry, stop_pct, config):
    portfolio = config.get("portfolio_eur")
    risk_pct = config.get("risk_per_trade_pct", 0.5)
    max_position_pct = config.get("max_position_pct", 10.0)
    if not portfolio or not entry or not stop_pct:
        return None
    portfolio = float(portfolio)
    risk_eur = portfolio * float(risk_pct) / 100.0
    loss_per_share = float(entry) * float(stop_pct) / 100.0
    if loss_per_share <= 0:
        return None
    by_risk = int(risk_eur // loss_per_share)
    by_position_cap = int((portfolio * float(max_position_pct) / 100.0) // float(entry))
    return max(0, min(by_risk, by_position_cap))

def main():
    now_ny = datetime.now(NY)

    radar = load_json(RADAR_PATH, {})
    config = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {"signals": {}, "positions": {}})
    state.setdefault("signals", {})
    state.setdefault("positions", {})
    state = import_manual_positions(state)
    risk_settings = effective_risk_settings(state, config)

    # Manual trades are imported even outside market hours.
    if not market_window_open(now_ny):
        state["last_check"] = datetime.now(BERLIN).isoformat()
        save_json(STATE_PATH, state)
        print("Outside regular US monitoring window:", now_ny.isoformat())
        return

    candidates = radar.get("candidates", [])
    today = now_ny.date().isoformat()

    # 1) Entry alerts from the scanner.
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
        qty = position_size(price, stop_pct, risk_settings)

        stop_price = price * (1 - stop_pct/100) if stop_pct else None
        target_price = price * (1 + target_pct/100) if target_pct else None
        qty_text = (
            f"\nVorgeschlagene Kaufmenge: {qty} Stück"
            if qty is not None and qty > 0 else
            "\nKaufmenge: nicht berechnet oder unter 1 Stück."
        )

        msg = (
            f"{ticker} erfüllt alle Dashboard-Regeln.\n"
            f"Referenzkurs: {price:.2f}\n"
            f"Score: {c.get('score','–')}/100\n"
        )
        if stop_price:
            msg += f"Stop/Invalidation: ca. {stop_price:.2f} ({-stop_pct:.2f}%)\n"
        if target_price:
            msg += f"1. Ziel: ca. {target_price:.2f} (+{target_pct:.2f}%)\n"
        msg += f"Entry-Regel: {c.get('entry_note','')}{qty_text}\nKeine Gewinngarantie."

        if push(f"🟢 ENTRY-SIGNAL {ticker}", msg, priority="high", tags="chart_with_upwards_trend"):
            state["signals"][signal_key] = {
                "sent_at": datetime.now(BERLIN).isoformat(),
                "price": price
            }
            existing = state["positions"].get(ticker)
            if not existing or existing.get("status") not in ("real_open", "virtual_open"):
                state["positions"][ticker] = {
                    "entry": price,
                    "qty": None,
                    "stop_pct": stop_pct,
                    "target_pct": target_pct,
                    "opened_at": now_ny.isoformat(),
                    "signal_key": signal_key,
                    "status": "virtual_open",
                    "source": "entry_signal_reference"
                }

    # 2) Monitor real or virtual positions.
    for ticker, p in list(state["positions"].items()):
        if p.get("status") not in ("real_open", "virtual_open"):
            continue

        price = latest_price(ticker)
        if price is None:
            continue

        entry = float(p["entry"])
        qty = p.get("qty")
        stop_pct = float(p.get("stop_pct") or 0)
        target_pct = float(p.get("target_pct") or 0)
        pnl_pct = (price / entry - 1) * 100
        pnl_eur = (price - entry) * int(qty) if qty else None

        reason = None
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
                if now_ny.date() > opened.date() and now_ny.time() >= time(15,45):
                    reason = f"Zeit-Exit: Position ist vom Vortag ({pnl_pct:+.2f}%)."
                    tags = "alarm_clock"
            except Exception:
                pass

        if reason:
            source_label = "Echte Position" if p.get("status") == "real_open" else "Virtuelles Setup"
            msg = (
                f"{source_label} {ticker}\n"
                f"Einstieg: {entry:.2f}\n"
                + (f"Stückzahl: {qty}\n" if qty else "")
                + f"Aktueller Kurs: {price:.2f}\n"
                + f"Veränderung: {pnl_pct:+.2f}%\n"
                + (f"Unrealisierter P/L: {pnl_eur:+.2f}\n" if pnl_eur is not None else "")
                + f"{reason}\n"
                + (f"Aktion: {qty} Stück verkaufen / Position vollständig schließen." if qty else "Aktion: Position jetzt prüfen und Exit erwägen.")
            )
            if push(f"🔴 EXIT-SIGNAL {ticker}", msg, priority="high", tags=tags):
                p["status"] = "exit_alerted"
                p["exit_alert_at"] = now_ny.isoformat()
                p["exit_reference_price"] = price

    if len(state["signals"]) > 500:
        keys = list(state["signals"].keys())[-300:]
        state["signals"] = {k: state["signals"][k] for k in keys}

    state["last_check"] = datetime.now(BERLIN).isoformat()
    save_json(STATE_PATH, state)
    print(json.dumps(state, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
