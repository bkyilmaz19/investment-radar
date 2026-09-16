from __future__ import annotations
import json, re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import yfinance as yf
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
NY = ZoneInfo("America/New_York")

WATCHLIST = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMD": "AMD",
    "META": "Meta",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "GOOG": "Alphabet C",
    "TSLA": "Tesla",
    "AVGO": "Broadcom",
    "NFLX": "Netflix",
    "ORCL": "Oracle",
    "CRM": "Salesforce",
    "ADBE": "Adobe",
    "INTC": "Intel",
    "QCOM": "Qualcomm",
    "MU": "Micron",
    "AMAT": "Applied Materials",
    "LRCX": "Lam Research",
    "KLAC": "KLA",
    "ARM": "Arm Holdings",
    "SMCI": "Super Micro Computer",
    "PLTR": "Palantir",
    "NOW": "ServiceNow",
    "PANW": "Palo Alto Networks",
    "CRWD": "CrowdStrike",
    "SNOW": "Snowflake",
    "DDOG": "Datadog",
    "MDB": "MongoDB",
    "NET": "Cloudflare",
    "SHOP": "Shopify",
    "UBER": "Uber",
    "ABNB": "Airbnb",
    "BKNG": "Booking",
    "PYPL": "PayPal",
    "SQ": "Block",
    "COIN": "Coinbase",
    "HOOD": "Robinhood",
    "SOFI": "SoFi",
    "RBLX": "Roblox",
    "ROKU": "Roku",
    "SPOT": "Spotify",
    "TTD": "Trade Desk",
    "APP": "AppLovin",
    "JPM": "JPMorgan",
    "BAC": "Bank of America",
    "WFC": "Wells Fargo",
    "C": "Citigroup",
    "GS": "Goldman Sachs",
    "MS": "Morgan Stanley",
    "AXP": "American Express",
    "V": "Visa",
    "MA": "Mastercard",
    "SCHW": "Charles Schwab",
    "BLK": "BlackRock",
    "BX": "Blackstone",
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "COP": "ConocoPhillips",
    "SLB": "SLB",
    "EOG": "EOG Resources",
    "OXY": "Occidental Petroleum",
    "HAL": "Halliburton",
    "MPC": "Marathon Petroleum",
    "VLO": "Valero",
    "PSX": "Phillips 66",
    "LLY": "Eli Lilly",
    "UNH": "UnitedHealth",
    "JNJ": "Johnson & Johnson",
    "MRK": "Merck",
    "ABBV": "AbbVie",
    "PFE": "Pfizer",
    "BMY": "Bristol Myers Squibb",
    "AMGN": "Amgen",
    "GILD": "Gilead",
    "REGN": "Regeneron",
    "VRTX": "Vertex",
    "ISRG": "Intuitive Surgical",
    "TMO": "Thermo Fisher",
    "DHR": "Danaher",
    "MDT": "Medtronic",
    "SYK": "Stryker",
    "BSX": "Boston Scientific",
    "HCA": "HCA Healthcare",
    "ELV": "Elevance Health",
    "CI": "Cigna",
    "CAT": "Caterpillar",
    "DE": "Deere",
    "GE": "GE Aerospace",
    "RTX": "RTX",
    "LMT": "Lockheed Martin",
    "NOC": "Northrop Grumman",
    "BA": "Boeing",
    "HON": "Honeywell",
    "UPS": "UPS",
    "FDX": "FedEx",
    "UNP": "Union Pacific",
    "CSX": "CSX",
    "ETN": "Eaton",
    "PH": "Parker-Hannifin",
    "WMT": "Walmart",
    "COST": "Costco",
    "TGT": "Target",
    "HD": "Home Depot",
    "LOW": "Lowe's",
    "NKE": "Nike",
    "SBUX": "Starbucks",
    "MCD": "McDonald's",
    "CMG": "Chipotle",
    "TJX": "TJX",
    "ROST": "Ross Stores",
    "LULU": "Lululemon",
    "MAR": "Marriott",
    "HLT": "Hilton",
    "RCL": "Royal Caribbean",
    "CCL": "Carnival",
    "DAL": "Delta Air Lines",
    "UAL": "United Airlines",
    "AAL": "American Airlines",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
    "PM": "Philip Morris",
    "MO": "Altria",
    "PG": "Procter & Gamble",
    "CL": "Colgate-Palmolive",
    "MDLZ": "Mondelez",
    "KHC": "Kraft Heinz",
    "GIS": "General Mills",
    "DIS": "Disney",
    "CMCSA": "Comcast",
    "T": "AT&T",
    "VZ": "Verizon",
    "TMUS": "T-Mobile US",
    "CHTR": "Charter",
    "WBD": "Warner Bros. Discovery",
    "EA": "Electronic Arts",
    "TTWO": "Take-Two",
    "LYV": "Live Nation",
    "NEE": "NextEra Energy",
    "DUK": "Duke Energy",
    "SO": "Southern Company",
    "AEP": "American Electric Power",
    "EXC": "Exelon",
    "LIN": "Linde",
    "APD": "Air Products",
    "FCX": "Freeport-McMoRan",
    "NEM": "Newmont",
    "NUE": "Nucor",
    "STLD": "Steel Dynamics",
    "MMM": "3M",
    "EMR": "Emerson",
    "ITW": "Illinois Tool Works",
    "ASML": "ASML",
    "TSM": "Taiwan Semiconductor",
    "NVO": "Novo Nordisk",
    "AZN": "AstraZeneca",
    "GSK": "GSK",
    "SAP": "SAP",
    "SONY": "Sony",
    "TM": "Toyota",
    "BABA": "Alibaba",
    "PDD": "PDD",
    "JD": "JD.com",
    "BIDU": "Baidu",
    "MELI": "MercadoLibre",
    "SE": "Sea Limited",
    "RIVN": "Rivian",
    "LCID": "Lucid",
    "F": "Ford",
    "GM": "General Motors",
    "STLA": "Stellantis",
    "CVS": "CVS Health",
    "WBA": "Walgreens",
    "MCK": "McKesson",
    "COR": "Cencora",
    "ANET": "Arista Networks",
    "DELL": "Dell",
    "HPE": "HPE",
    "IBM": "IBM",
    "CSCO": "Cisco",
    "MRVL": "Marvell",
    "ON": "ON Semiconductor",
    "ADI": "Analog Devices",
    "TXN": "Texas Instruments",
    "NXPI": "NXP",
    "CEG": "Constellation Energy",
    "VST": "Vistra",
    "GEV": "GE Vernova",
    "FSLR": "First Solar",
    "ENPH": "Enphase",
    "DKNG": "DraftKings",
    "MGM": "MGM Resorts",
    "WYNN": "Wynn Resorts",
    "LVS": "Las Vegas Sands",
    "CVNA": "Carvana",
    "CHWY": "Chewy",
    "ETSY": "Etsy",
    "PINS": "Pinterest",
    "SNAP": "Snap",
    "MRNA": "Moderna",
    "BIIB": "Biogen",
    "RMD": "ResMed",
    "ZTS": "Zoetis",
    "DXCM": "DexCom"
}

POS = ['beat','beats','upgrade','upgraded','raises','raised','strong','record','approval','approved',
       'contract','wins','growth','surge','positive','buyback','guidance raised','profit rises','outperform',
       'tops estimates','raises outlook','record revenue','partnership']
NEG = ['miss','misses','downgrade','downgraded','cuts','cut guidance','warning','probe','lawsuit',
       'delay','recall','falls','weak','slump','investigation','fraud','ban','loss widens','underperform',
       'lowers outlook','offering','secondary offering']

def pct(a,b):
    return 0.0 if not b else (a/b-1)*100

def sentiment(text):
    t = text.lower()
    p = sum(1 for w in POS if w in t)
    n = sum(1 for w in NEG if w in t)
    return 1 if p > n else -1 if n > p else 0

def get_news(ticker, name):
    q = quote_plus(f"{ticker} {name} stock when:1d")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries[:6]:
        title = re.sub(r"\s+-\s+[^-]+$","",e.get("title","")).strip()
        out.append({"ticker":ticker,"title":title,"time":e.get("published","")[:25],"sentiment":sentiment(title)})
    return out

def atr14(frame):
    try:
        x = frame[['High','Low','Close']].dropna()
        if len(x) < 15: return None
        prev = x['Close'].shift(1)
        tr = pd.concat([(x['High']-x['Low']).abs(), (x['High']-prev).abs(), (x['Low']-prev).abs()], axis=1).max(axis=1)
        return float(tr.rolling(14).mean().iloc[-1])
    except Exception:
        return None

def get_session_context(ticker, prev_close):
    """Return context ONLY for the actual current New-York trading date.

    Never treats the most recent intraday bar as "today". This prevents
    yesterday's regular session/after-hours data from becoming a false live
    confirmation during the European morning.
    """
    now_ny = datetime.now(NY)
    today_ny = now_ny.date()
    result = {
        "premarket_price": None,
        "gap_pct": None,
        "premarket_move_pct": None,
        "live_price": None,
        "live_gap_pct": None,
        "regular_move_pct": None,
        "market_open": False,
        "session_phase": "pre_premarket",
        "bar_age_minutes": None,
        "vwap": None,
        "opening_range_high": None,
        "opening_range_low": None,
        "opening_range_ready": False,
        "breakout_confirmed": False,
    }
    if now_ny.weekday() >= 5:
        result["session_phase"] = "weekend"
        return result
    if now_ny.time() >= datetime.strptime("04:00", "%H:%M").time():
        result["session_phase"] = "premarket"
    if now_ny.time() >= datetime.strptime("09:30", "%H:%M").time():
        result["session_phase"] = "regular"
    if now_ny.time() >= datetime.strptime("16:00", "%H:%M").time():
        result["session_phase"] = "after_hours"

    try:
        intr = yf.download(
            ticker, period="2d", interval="5m", prepost=True,
            auto_adjust=False, progress=False, threads=False,
        )
        if intr.empty:
            return result
        if isinstance(intr.columns, pd.MultiIndex):
            intr.columns = intr.columns.get_level_values(0)
        intr = intr.dropna(subset=["Close"])
        if intr.empty:
            return result

        idx = intr.index
        local = idx.tz_convert(NY) if idx.tz is not None else idx.tz_localize(NY)
        intr = intr.copy(); intr.index = local

        # Critical guard: select the real calendar date in New York, not the
        # date of the last available bar.
        day = intr[intr.index.date == today_ny]
        if day.empty:
            return result

        # Reject stale bars. A stale prior snapshot must never become a live trigger.
        last_ts = day.index[-1].to_pydatetime()
        result["bar_age_minutes"] = max(0.0, (now_ny - last_ts).total_seconds() / 60.0)

        pre = day[(day.index.hour >= 4) & ((day.index.hour < 9) | ((day.index.hour == 9) & (day.index.minute < 30)))]
        if not pre.empty:
            first = float(pre["Close"].iloc[0]); last = float(pre["Close"].iloc[-1])
            result.update({
                "premarket_price": last,
                # Gap is the CURRENT premarket price vs prior official close.
                "gap_pct": pct(last, prev_close),
                "premarket_move_pct": pct(last, first),
            })

        # Do not allow regular-session confirmation before the actual NY open.
        if now_ny.time() >= datetime.strptime("09:30", "%H:%M").time():
            regular = day[((day.index.hour > 9) | ((day.index.hour == 9) & (day.index.minute >= 30))) & (day.index.hour < 16)]
            if not regular.empty:
                regular_open = float(regular["Open"].iloc[0]) if "Open" in regular.columns else float(regular["Close"].iloc[0])
                current = float(regular["Close"].iloc[-1])
                # 15-minute opening range + session VWAP. These are stronger entry
                # confirmations than merely being green since the opening print.
                first15 = regular[regular.index < regular.index[0] + pd.Timedelta(minutes=15)]
                or_high = float(first15["High"].max()) if len(first15) >= 3 else None
                or_low = float(first15["Low"].min()) if len(first15) >= 3 else None
                vwap = None
                if "Volume" in regular.columns:
                    vol = regular["Volume"].fillna(0).astype(float)
                    typical = ((regular["High"] + regular["Low"] + regular["Close"]) / 3).astype(float)
                    if float(vol.sum()) > 0:
                        vwap = float((typical * vol).sum() / vol.sum())
                fresh = result["bar_age_minutes"] is not None and result["bar_age_minutes"] <= 20
                opening_ready = len(first15) >= 3 and now_ny.time() >= datetime.strptime("09:45", "%H:%M").time()
                breakout = bool(opening_ready and fresh and or_high is not None and vwap is not None
                                and current >= or_high * 0.998 and current >= vwap
                                and pct(current, regular_open) >= 0)
                result.update({
                    "live_price": current,
                    "live_gap_pct": pct(current, prev_close),
                    "regular_move_pct": pct(current, regular_open),
                    "market_open": now_ny.time() < datetime.strptime("16:00", "%H:%M").time(),
                    "vwap": vwap,
                    "opening_range_high": or_high,
                    "opening_range_low": or_low,
                    "opening_range_ready": opening_ready,
                    "breakout_confirmed": breakout,
                })
    except Exception:
        pass
    return result

def market_regime():
    try:
        d = yf.download(['SPY','QQQ'], period='8d', interval='1d', auto_adjust=True, progress=False, group_by='ticker')
        moves=[]
        for t in ['SPY','QQQ']:
            s=d[t]['Close'].dropna()
            if len(s)>=2: moves.append(pct(float(s.iloc[-1]),float(s.iloc[-2])))
        avg=sum(moves)/max(1,len(moves))
        if avg>0.8:return 'Risk-on / positives Momentum'
        if avg<-0.8:return 'Risk-off / erhöhte Vorsicht'
        return 'Gemischt / selektiv'
    except Exception:
        return 'Unklar / Daten prüfen'

def main():
    tickers=list(WATCHLIST)
    px=yf.download(tickers,period='30d',interval='1d',auto_adjust=False,progress=False,
                   group_by='ticker',threads=True)
    rows=[]
    for t in tickers:
        try:
            frame=px[t].dropna(how='all')
            c,v=frame['Close'].dropna(),frame['Volume'].dropna()
            if len(c)<16: continue
            # Daily momentum/volume must use completed sessions only. During
            # today's US session Yahoo may already expose an incomplete daily bar.
            now_ny = datetime.now(NY)
            try:
                last_daily_date = pd.Timestamp(c.index[-1]).date()
            except Exception:
                last_daily_date = None
            has_live_daily = last_daily_date == now_ny.date() and now_ny.weekday() < 5
            c_done = c.iloc[:-1] if has_live_daily else c
            v_done = v.iloc[:-1] if has_live_daily else v
            frame_done = frame.iloc[:-1] if has_live_daily else frame
            if len(c_done) < 16: continue
            prev_close=float(c_done.iloc[-1])
            c1=pct(float(c_done.iloc[-1]),float(c_done.iloc[-2]))
            c5=pct(float(c_done.iloc[-1]),float(c_done.iloc[-6]))
            vr=float(v_done.iloc[-1]/max(1.0,v_done.iloc[-6:-1].mean())) if len(v_done)>=6 else 1.0
            atr=atr14(frame_done); atr_pct=(atr/prev_close*100) if atr and prev_close else None
            avg_dollar_volume = float((c_done.iloc[-20:] * v_done.iloc[-20:]).mean()) if len(c_done) >= 20 else float((c_done * v_done).tail(10).mean())

            # Stage 1: cheap quantitative scan across the whole universe.
            qscore=50
            qscore += max(-12,min(15,c1*3.2))
            qscore += max(-10,min(10,c5*0.8))
            qscore += max(-6,min(14,(vr-1.0)*12))
            if atr_pct is not None:
                if 1.2<=atr_pct<=5.0:qscore+=7
                elif 0.7<=atr_pct<1.2:qscore+=3
                elif atr_pct>8:qscore-=8
            # Penalize obviously tiny price / highly unstable situations.
            if prev_close < 5:qscore-=10
            # Liquidity guard: favor names that can realistically be traded with
            # tight spreads; exclude thin names from final research candidates.
            if avg_dollar_volume >= 500_000_000: qscore += 6
            elif avg_dollar_volume >= 100_000_000: qscore += 4
            elif avg_dollar_volume >= 25_000_000: qscore += 1
            else: qscore -= 12
            rows.append(dict(ticker=t,name=WATCHLIST[t],score=qscore,c1=c1,c5=c5,vr=vr,
                             atr_pct=atr_pct,prev_close=prev_close,avg_dollar_volume=avg_dollar_volume,news=[],nsent=0))
        except Exception:
            continue

    rows.sort(key=lambda x:x['score'],reverse=True)

    # Stage 2: fetch news only for the strongest 24 quantitative setups.
    news_all=[]
    for r in rows[:24]:
        ns=get_news(r['ticker'],r['name'])
        r['news']=ns; news_all.extend(ns)
        r['nsent']=sum(n['sentiment'] for n in ns[:6])
        r['score'] += r['nsent']*4

    rows.sort(key=lambda x:x['score'],reverse=True)

    # Stage 3: premarket only for top 10. Keeps runtime/API load manageable.
    for r in rows[:10]:
        pm=get_session_context(r['ticker'],r['prev_close']); r.update(pm)
        gp=r.get('gap_pct'); pmove=r.get('premarket_move_pct')
        live_gap=r.get('live_gap_pct'); regular_move=r.get('regular_move_pct')
        market_open=bool(r.get('market_open'))

        # Before the open, score the premarket gap. After the open, score the
        # current gap vs. yesterday's close so gap recovery can improve a setup.
        rule_gap = live_gap if market_open and live_gap is not None else gp
        if rule_gap is not None:
            if 0.5<=rule_gap<=4.0:r['score']+=7
            elif -1.5<=rule_gap<0.5:r['score']+=5
            elif 4.0<rule_gap<=7.0:r['score']+=3
            elif rule_gap>10:r['score']-=8
            elif rule_gap<-3:r['score']-=5

        if market_open and regular_move is not None:
            r['score'] += max(-5,min(6,regular_move*1.5))
        elif pmove is not None:
            r['score'] += max(-4,min(5,pmove*1.5))

    for r in rows:
        r['score']=int(max(0,min(100,round(r['score']))))
    rows.sort(key=lambda x:x['score'],reverse=True)

    selected=[r for r in rows if r['score']>=65 and r.get('avg_dollar_volume',0) >= 25_000_000][:5]
    candidates=[]
    for r in selected:
        pos_titles=[n['title'] for n in r['news'] if n['sentiment']>0]
        neg_titles=[n['title'] for n in r['news'] if n['sentiment']<0]
        catalyst=pos_titles[0] if pos_titles else ('Premarket-/Momentum-Bestätigung' if r.get('gap_pct') is not None else 'Relative Stärke + Volumen; Bestätigung erforderlich')
        risk=neg_titles[0] if neg_titles else 'Momentum kann nach Eröffnung drehen; Overnight- und Gap-Risiko.'
        ap=r.get('atr_pct') or 2.0
        stop=max(0.7,min(2.5,ap*0.65)); target=max(1.2,min(5.0,stop*1.8))
        gap=r.get('gap_pct')
        live_gap=r.get('live_gap_pct')
        regular_move=r.get('regular_move_pct')
        market_open=bool(r.get('market_open'))
        session_phase=r.get('session_phase','pre_premarket')

        rule_gap = live_gap if market_open and live_gap is not None else gap
        confirmation_move = regular_move if market_open else r.get('premarket_move_pct')
        confirmation_available = rule_gap is not None and confirmation_move is not None
        live_confirmation_available = (market_open and regular_move is not None and live_gap is not None
                                       and bool(r.get('opening_range_ready'))
                                       and r.get('bar_age_minutes') is not None
                                       and r.get('bar_age_minutes') <= 20)
        breakout_confirmed = bool(r.get('breakout_confirmed'))

        if market_open:
            if rule_gap is None:
                entry='Live-Handel aktiv. Einstieg nur bei bestätigtem Breakout bzw. klarer relativer Stärke mit Volumen.'
            elif rule_gap < -1.5:
                entry=f'Live-Gap noch {rule_gap:+.2f}%. Warten, bis der Kurs mindestens in den erlaubten Gap-Bereich zurückkehrt und Stabilität zeigt.'
            elif not r.get('opening_range_ready'):
                entry=f'US-Handel läuft, aber die 15-Minuten-Opening-Range ist noch nicht abgeschlossen. Kein Entry vor 09:45 New-York-Zeit.'
            elif breakout_confirmed:
                entry=f'Live-Trigger bestätigt: Kurs hält VWAP und testet/überschreitet die 15-Minuten-Opening-Range; Gap {rule_gap:+.2f}%, seit Open {confirmation_move:+.2f}%. Bevorzugt Rücksetzer + erneute Stärke statt Hinterherjagen.'
            elif confirmation_move is not None:
                entry=f'Noch kein sauberer Live-Trigger. Gap {rule_gap:+.2f}%, seit Open {confirmation_move:+.2f}%. Warten auf VWAP-Halt plus Opening-Range-Bestätigung.'
            else:
                entry=f'Live-Gap {rule_gap:+.2f}%. Erst kaufen, wenn die Bewegung seit US-Open stabil/positiv wird.'
        elif gap is None:
            entry='Nur bei bestätigtem Breakout über das lokale Intraday-Hoch oder klarer relativer Stärke nach Eröffnung.'
        elif gap>0:
            entry=f'Premarket-Gap {gap:+.2f}%. Nicht blind jagen: Einstieg nur, wenn der Gap nach Eröffnung gehalten wird und Volumen bestätigt.'
        else:
            entry=f'Premarket-Gap {gap:+.2f}%. Nur interessant, wenn der Titel den Gap zügig zurückerobert; sonst auslassen.'

        criteria = {
          'score_ok': r['score'] >= 75,
          'momentum_ok': r['c1'] > 0 and r['c5'] > -1.0,
          'volume_ok': r['vr'] >= 1.10,
          'volatility_ok': (r.get('atr_pct') is not None and 1.0 <= r['atr_pct'] <= 6.0),
          'news_ok': r.get('nsent',0) >= 0,
          'gap_ok': (rule_gap is not None and -1.5 <= rule_gap <= 6.0),
          'confirmation_ok': (breakout_confirmed if market_open else (confirmation_move is not None and confirmation_move >= -0.5))
        }
        all_rules = all(criteria.values())

        if all_rules and live_confirmation_available:
            action_status = 'KAUF HEUTE'
            action_reason = 'Alle definierten Kriterien sind in der heutigen regulären US-Session live bestätigt.'
        elif all_rules and confirmation_available and not market_open:
            action_status = 'WARTEN'
            action_reason = 'Premarket-Setup bestätigt; KAUF HEUTE erst nach echter Bestätigung in der heutigen regulären US-Session.'
        elif r['score'] >= 65 and criteria['momentum_ok'] and criteria['volume_ok']:
            action_status = 'WARTEN'
            labels = {
                'score_ok':'Score',
                'momentum_ok':'Momentum',
                'volume_ok':'Volumen',
                'volatility_ok':'ATR',
                'news_ok':'News',
                'gap_ok':'Gap',
                'confirmation_ok':'Live-/Premarket-Bestätigung'
            }
            missing = [labels[k] for k,v in criteria.items() if not v]
            if not confirmation_available:
                missing.append('Live-/Premarket-Daten')
            action_reason = 'Gutes Setup, aber noch nicht alle Bedingungen erfüllt: ' + ', '.join(missing[:4])
        else:
            action_status = 'NICHT KAUFEN'
            action_reason = 'Das Setup erfüllt die Mindestregeln für einen kurzfristigen Einstieg nicht.'

        candidates.append({
          'ticker':r['ticker'],'name':r['name'],'score':r['score'],'stance':'Short-Term Momentum / Event',
          'thesis':f"1T {r['c1']:+.2f}%, 5T {r['c5']:+.2f}%, relatives Volumen {r['vr']:.2f}x" + (f", ATR {r['atr_pct']:.2f}%" if r.get('atr_pct') else ''),
          'catalyst':catalyst,'risk_note':risk,'entry_note':entry,
          'stop_pct':round(stop,2),'target_pct':round(target,2),
          'exit_note':'Zeithorizont wenige Stunden bis max. etwa 2 Handelstage. Spätestens am Folgetag vollständig neu bewerten.',
          'change_1d':f"{r['c1']:+.2f}%",'change_5d':f"{r['c5']:+.2f}%",'volume_ratio':f"{r['vr']:.2f}x",
          'atr_pct':f"{r['atr_pct']:.2f}%" if r.get('atr_pct') else 'n/a',
          'gap_pct':f"{gap:+.2f}%" if gap is not None else 'noch nicht verfügbar',
          'premarket_move_pct':f"{r['premarket_move_pct']:+.2f}%" if r.get('premarket_move_pct') is not None else 'noch nicht verfügbar',
          'live_gap_pct':f"{live_gap:+.2f}%" if live_gap is not None else 'noch nicht verfügbar',
          'regular_move_pct':f"{regular_move:+.2f}%" if regular_move is not None else 'noch nicht verfügbar',
          'avg_dollar_volume': round(r.get('avg_dollar_volume',0),2),
          'bar_age_minutes': round(r.get('bar_age_minutes'),1) if r.get('bar_age_minutes') is not None else None,
          'vwap': round(r.get('vwap'),2) if r.get('vwap') is not None else None,
          'opening_range_high': round(r.get('opening_range_high'),2) if r.get('opening_range_high') is not None else None,
          'opening_range_ready': bool(r.get('opening_range_ready')),
          'breakout_confirmed': breakout_confirmed,
          'session_phase':('US-Handel live' if market_open else ('Premarket' if session_phase == 'premarket' else ('After-Hours / US-Session beendet' if session_phase == 'after_hours' else ('Wochenende' if session_phase == 'weekend' else 'Vor US-Premarket')))),
          'action_status':action_status,
          'action_reason':action_reason,
          'criteria':criteria
        })

    avoid=[]
    for r in sorted(rows,key=lambda x:x['score'])[:5]:
        if r['score']<45:
            avoid.append({'ticker':r['ticker'],'reason':f"Schwaches kurzfristiges Setup (Score {r['score']}/100; 1T {r['c1']:+.2f}%, 5T {r['c5']:+.2f}%)."})

    now=datetime.now(TZ); regime=market_regime()
    if any(c.get('session_phase') == 'US-Handel live' for c in candidates):
        phase='US-Handel läuft: Live-Gap und Bewegung seit Eröffnung werden zur Bestätigung neu bewertet'
    elif any(c['gap_pct']!='noch nicht verfügbar' for c in candidates):
        phase='Premarket-Daten einbezogen, soweit verfügbar'
    else:
        phase='Früher Morning-Scan; US-Premarket ggf. noch nicht geöffnet'
    data={
      'generated_at_local':now.strftime('%d.%m.%Y %H:%M %Z'),
      'market_regime':regime,
      'universe_size':len(tickers),
      'scanned_count':len(rows),
      'summary':f"{regime}. {phase}. {len(rows)} von {len(tickers)} Aktien mit ausreichenden Daten geprüft; {len(candidates)} Top-Kandidaten angezeigt. Ranking: Momentum, relatives Volumen, ATR, News und Premarket soweit verfügbar. Kein Score garantiert einen Kursanstieg.",
      'candidates':candidates,'avoid':avoid,
      'news':sorted(news_all,key=lambda x:abs(x['sentiment']),reverse=True)
    }
    Path('data').mkdir(exist_ok=True)
    Path('data/radar.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
