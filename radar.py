from __future__ import annotations
import json, math, re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import yfinance as yf
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')

WATCHLIST = {
    'AAPL':'Apple','MSFT':'Microsoft','NVDA':'NVIDIA','AMD':'AMD','META':'Meta',
    'AMZN':'Amazon','GOOGL':'Alphabet','TSLA':'Tesla','AVGO':'Broadcom','NFLX':'Netflix',
    'XOM':'Exxon Mobil','CVX':'Chevron','JPM':'JPMorgan','BAC':'Bank of America',
    'LLY':'Eli Lilly','UNH':'UnitedHealth','GSK':'GSK','NOW':'ServiceNow','PLTR':'Palantir',
    'ASML':'ASML','MU':'Micron','ARM':'Arm Holdings','SMCI':'Super Micro Computer'
}

POS = ['beat','beats','upgrade','upgraded','raises','raised','strong','record','approval','approved',
       'contract','wins','growth','surge','positive','buyback','guidance raised','profit rises','outperform']
NEG = ['miss','misses','downgrade','downgraded','cuts','cut guidance','warning','probe','lawsuit',
       'delay','recall','falls','weak','slump','investigation','fraud','ban','loss widens','underperform']

def pct(a,b):
    return 0.0 if not b else (a/b-1)*100

def sentiment(text):
    t = text.lower()
    p = sum(1 for w in POS if w in t)
    n = sum(1 for w in NEG if w in t)
    return 1 if p > n else -1 if n > p else 0

def get_news(ticker, name):
    q = quote_plus(f'{ticker} {name} stock when:1d')
    url = f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en'
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries[:6]:
        title = re.sub(r'\s+-\s+[^-]+$','',e.get('title','')).strip()
        out.append({'ticker':ticker,'title':title,'time':e.get('published','')[:25],'sentiment':sentiment(title)})
    return out

def atr14(frame: pd.DataFrame) -> float | None:
    try:
        h, l, c = frame['High'].dropna(), frame['Low'].dropna(), frame['Close'].dropna()
        x = pd.concat([h,l,c], axis=1).dropna()
        if len(x) < 15:
            return None
        prev = x['Close'].shift(1)
        tr = pd.concat([(x['High']-x['Low']).abs(), (x['High']-prev).abs(), (x['Low']-prev).abs()], axis=1).max(axis=1)
        return float(tr.rolling(14).mean().iloc[-1])
    except Exception:
        return None

def get_premarket(ticker: str, prev_close: float) -> dict:
    result = {'premarket_price':None,'gap_pct':None,'premarket_move_pct':None,'premarket_volume':None}
    try:
        intr = yf.download(ticker, period='2d', interval='5m', prepost=True, auto_adjust=False, progress=False, threads=False)
        if intr.empty:
            return result
        if isinstance(intr.columns, pd.MultiIndex):
            intr.columns = intr.columns.get_level_values(0)
        intr = intr.dropna(subset=['Close'])
        if intr.empty:
            return result
        # yfinance timestamps are exchange-local or tz-aware depending on version.
        idx = intr.index
        try:
            local = idx.tz_convert('America/New_York') if idx.tz is not None else idx.tz_localize('America/New_York')
        except Exception:
            local = idx
        intr = intr.copy(); intr.index = local
        today = intr.index[-1].date()
        day = intr[intr.index.date == today]
        if day.empty:
            return result
        # US premarket: 04:00-09:29 ET. If unavailable, leave values empty rather than inventing them.
        mask = [(x.hour > 4 or (x.hour == 4 and x.minute >= 0)) and (x.hour < 9 or (x.hour == 9 and x.minute < 30)) for x in day.index]
        pre = day.loc[mask]
        if pre.empty:
            return result
        first = float(pre['Close'].iloc[0]); last = float(pre['Close'].iloc[-1])
        vol = float(pre['Volume'].fillna(0).sum()) if 'Volume' in pre else None
        result.update({
            'premarket_price': last,
            'gap_pct': pct(first, prev_close),
            'premarket_move_pct': pct(last, first),
            'premarket_volume': vol,
        })
    except Exception:
        pass
    return result

def market_regime():
    try:
        d = yf.download(['SPY','QQQ'], period='8d', interval='1d', auto_adjust=True, progress=False, group_by='ticker')
        moves = []
        for t in ['SPY','QQQ']:
            s = d[t]['Close'].dropna()
            if len(s) >= 2:
                moves.append(pct(float(s.iloc[-1]),float(s.iloc[-2])))
        avg = sum(moves)/len(moves)
        if avg > 0.8: return 'Risk-on / positives Momentum'
        if avg < -0.8: return 'Risk-off / erhöhte Vorsicht'
        return 'Gemischt / selektiv'
    except Exception:
        return 'Unklar / Daten prüfen'

def main():
    tickers = list(WATCHLIST)
    px = yf.download(tickers, period='30d', interval='1d', auto_adjust=False, progress=False, group_by='ticker', threads=True)
    news_all, rows = [], []

    for t in tickers:
        try:
            frame = px[t] if len(tickers) > 1 else px
            frame = frame.dropna(how='all')
            c, v = frame['Close'].dropna(), frame['Volume'].dropna()
            if len(c) < 16:
                continue
            prev_close = float(c.iloc[-1])
            c1 = pct(float(c.iloc[-1]), float(c.iloc[-2]))
            c5 = pct(float(c.iloc[-1]), float(c.iloc[-6]))
            vr = float(v.iloc[-1] / max(1.0, v.iloc[-6:-1].mean())) if len(v) >= 6 else 1.0
            atr = atr14(frame)
            atr_pct = (atr / prev_close * 100) if atr and prev_close else None
            ns = get_news(t, WATCHLIST[t]); news_all.extend(ns)
            nsent = sum(n['sentiment'] for n in ns[:6])

            # Base ranking: short momentum + volume + fresh catalyst + tradable volatility.
            score = 48
            score += max(-10, min(13, c1 * 3.0))
            score += max(-8, min(10, c5 * 0.7))
            score += max(-5, min(12, (vr - 1.0) * 12))
            score += nsent * 4
            if atr_pct is not None:
                # Favor enough movement to matter, but penalize extreme volatility.
                if 1.2 <= atr_pct <= 4.5: score += 7
                elif 0.7 <= atr_pct < 1.2: score += 3
                elif atr_pct > 7: score -= 6
            score = int(max(15, min(90, round(score))))
            rows.append(dict(ticker=t,name=WATCHLIST[t],score=score,c1=c1,c5=c5,vr=vr,atr=atr,atr_pct=atr_pct,prev_close=prev_close,nsent=nsent,news=ns))
        except Exception:
            continue

    rows.sort(key=lambda x:x['score'], reverse=True)

    # Premarket enrichment only for strongest names to reduce API load.
    for r in rows[:8]:
        pm = get_premarket(r['ticker'], r['prev_close'])
        r.update(pm)
        gp = r.get('gap_pct')
        pmove = r.get('premarket_move_pct')
        if gp is not None:
            # Positive but not absurd gaps score best; huge gaps are harder to chase safely.
            if 0.5 <= gp <= 4.0: r['score'] += 7
            elif 4.0 < gp <= 7.0: r['score'] += 3
            elif gp > 10.0: r['score'] -= 7
            elif gp < -3.0: r['score'] -= 5
        if pmove is not None:
            r['score'] += max(-4,min(5, pmove*1.5))
        r['score'] = int(max(15,min(94,round(r['score']))))

    rows.sort(key=lambda x:x['score'], reverse=True)
    selected = [r for r in rows if r['score'] >= 65][:5]
    candidates = []

    for r in selected:
        pos_titles = [n['title'] for n in r['news'] if n['sentiment'] > 0]
        neg_titles = [n['title'] for n in r['news'] if n['sentiment'] < 0]
        catalyst = pos_titles[0] if pos_titles else ('Premarket-/Momentum-Bestätigung' if r.get('gap_pct') is not None else 'Relative Stärke + Volumen; Bestätigung erforderlich')
        risk = neg_titles[0] if neg_titles else 'Momentum kann nach Eröffnung drehen; Overnight- und Gap-Risiko.'
        atr_pct = r.get('atr_pct') or 2.0
        # Orientation only: targets/stops are derived from volatility, not promises.
        stop_pct = max(0.7, min(2.5, atr_pct * 0.65))
        target_pct = max(1.2, min(5.0, stop_pct * 1.8))
        gap = r.get('gap_pct')
        if gap is None:
            entry = 'Nur bei bestätigtem Breakout über das lokale Intraday-Hoch oder klarer relativer Stärke nach Eröffnung.'
        elif gap > 0:
            entry = f'Premarket-Gap {gap:+.2f}%. Nicht blind jagen: Einstieg nur, wenn der Gap nach Eröffnung gehalten wird und Volumen bestätigt.'
        else:
            entry = f'Premarket-Gap {gap:+.2f}%. Nur interessant, wenn der Titel den Gap zügig zurückerobert; sonst auslassen.'

        candidates.append({
            'ticker':r['ticker'],'name':r['name'],'score':r['score'],
            'stance':'Short-Term Momentum / Event',
            'thesis':f"1T {r['c1']:+.2f}%, 5T {r['c5']:+.2f}%, relatives Volumen {r['vr']:.2f}x" + (f", ATR {r['atr_pct']:.2f}%" if r.get('atr_pct') else ''),
            'catalyst':catalyst,'risk_note':risk,'entry_note':entry,
            'stop_pct':round(stop_pct,2),'target_pct':round(target_pct,2),
            'exit_note':'Zeithorizont wenige Stunden bis max. etwa 2 Handelstage. Spätestens am Folgetag vollständig neu bewerten; kein Verlierer-Halten aus Hoffnung.',
            'change_1d':f"{r['c1']:+.2f}%",'change_5d':f"{r['c5']:+.2f}%",'volume_ratio':f"{r['vr']:.2f}x",
            'atr_pct':f"{r['atr_pct']:.2f}%" if r.get('atr_pct') else 'n/a',
            'gap_pct':f"{gap:+.2f}%" if gap is not None else 'noch nicht verfügbar',
            'premarket_move_pct':f"{r['premarket_move_pct']:+.2f}%" if r.get('premarket_move_pct') is not None else 'noch nicht verfügbar'
        })

    avoid = []
    for r in sorted(rows,key=lambda x:x['score'])[:5]:
        if r['score'] < 50:
            avoid.append({'ticker':r['ticker'],'reason':f"Schwaches kurzfristiges Setup (Score {r['score']}/100; 1T {r['c1']:+.2f}%, 5T {r['c5']:+.2f}%)."})

    now = datetime.now(TZ)
    regime = market_regime()
    phase = 'Premarket-Daten einbezogen, soweit verfügbar' if any(c['gap_pct'] != 'noch nicht verfügbar' for c in candidates) else 'Früher Morning-Scan; US-Premarket ggf. noch nicht geöffnet'
    summary = (f'{regime}. {phase}. {len(candidates)} Kandidat(en) erfüllen den Mindestscore. '
               'Ranking: kurzfristiges Momentum, relatives Volumen, aktuelle News/Katalysatoren, ATR und Premarket-Gap soweit verfügbar. '
               'Kein Score garantiert einen Kursanstieg.')

    data = {
        'generated_at_local':now.strftime('%d.%m.%Y %H:%M %Z'),
        'market_regime':regime,
        'summary':summary,
        'candidates':candidates,
        'avoid':avoid,
        'news':sorted(news_all,key=lambda x:abs(x['sentiment']), reverse=True)
    }
    Path('data').mkdir(exist_ok=True)
    Path('data/radar.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
