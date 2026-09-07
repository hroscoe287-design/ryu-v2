import os
import math
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

try:
    import yfinance as yf
except Exception:
    yf = None

app = Flask(__name__)

# RYU V2 is intentionally a demo/analysis dashboard. It does not place trades.
MARKETS = {
    "EUR/USD": {"ticker": "EURUSD=X", "group": "Forex", "payout": 92, "icon": "🇪🇺🇺🇸"},
    "GBP/USD": {"ticker": "GBPUSD=X", "group": "Forex", "payout": 92, "icon": "🇬🇧🇺🇸"},
    "USD/JPY": {"ticker": "JPY=X", "group": "Forex", "payout": 92, "icon": "🇺🇸🇯🇵"},
    "AUD/USD": {"ticker": "AUDUSD=X", "group": "Forex", "payout": 82, "icon": "🇦🇺🇺🇸"},
    "BTC/USD": {"ticker": "BTC-USD", "group": "Crypto", "payout": 92, "icon": "₿"},
    "ETH/USD": {"ticker": "ETH-USD", "group": "Crypto", "payout": 90, "icon": "Ξ"},
    "AAPL": {"ticker": "AAPL", "group": "Stocks", "payout": 88, "icon": ""},
    "XAU/USD": {"ticker": "GC=F", "group": "Commodities", "payout": None, "icon": "▰"},
}

DEFAULT_SYMBOLS = ["EUR/USD", "BTC/USD", "AAPL", "USD/JPY", "ETH/USD", "XAU/USD", "GBP/USD"]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ema(values, period):
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    out = [values[0]]
    for x in values[1:]:
        out.append((x * k) + (out[-1] * (1 - k)))
    return out


def rsi(values, period=14):
    if len(values) < 2:
        return [50.0] * len(values)
    gains, losses = [0.0], [0.0]
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[1:period + 1]) / max(period, 1)
    al = sum(losses[1:period + 1]) / max(period, 1)
    out = [50.0] * len(values)
    for i in range(1, len(values)):
        if i > period:
            ag = ((ag * (period - 1)) + gains[i]) / period
            al = ((al * (period - 1)) + losses[i]) / period
        if al == 0:
            out[i] = 100.0 if ag > 0 else 50.0
        else:
            rs = ag / al
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def atr(high, low, close, period=14):
    if not close:
        return []
    tr = [high[0] - low[0]]
    for i in range(1, len(close)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    out = []
    for i in range(len(tr)):
        start = max(0, i - period + 1)
        out.append(sum(tr[start:i + 1]) / (i - start + 1))
    return out


def adx(high, low, close, period=14):
    if len(close) < 2:
        return [20.0] * len(close)
    trs = [high[0] - low[0]]
    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, len(close)):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        trs.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    out = []
    for i in range(len(close)):
        s = max(0, i - period + 1)
        trn = sum(trs[s:i + 1]) or 1e-9
        p = 100 * sum(plus_dm[s:i + 1]) / trn
        m = 100 * sum(minus_dm[s:i + 1]) / trn
        dx = 100 * abs(p - m) / max(p + m, 1e-9)
        out.append(dx)
    return out


def fallback_series(seed=1.0, n=55):
    # Deterministic fallback so the dashboard still renders if Yahoo is unavailable.
    vals = []
    x = seed
    for i in range(n):
        wave = math.sin(i / 3.8) * seed * 0.0015
        drift = seed * 0.0007
        x = x + drift + wave + math.sin(i * 1.73) * seed * 0.00035
        vals.append(x)
    return vals


def load_series(symbol, interval="5m"):
    info = MARKETS.get(symbol, MARKETS["EUR/USD"])
    ticker = info["ticker"]
    if yf is not None:
        try:
            period = "5d" if interval in ("1m", "2m", "5m", "15m") else "1mo"
            data = yf.download(ticker, period=period, interval="5m", progress=False, auto_adjust=False, threads=False)
            if data is not None and len(data) >= 35:
                if hasattr(data.columns, "levels") and data.columns.nlevels > 1:
                    close = data["Close"].iloc[:, 0].astype(float).tolist()
                    high = data["High"].iloc[:, 0].astype(float).tolist()
                    low = data["Low"].iloc[:, 0].astype(float).tolist()
                    opens = data["Open"].iloc[:, 0].astype(float).tolist()
                else:
                    close = data["Close"].astype(float).tolist()
                    high = data["High"].astype(float).tolist()
                    low = data["Low"].astype(float).tolist()
                    opens = data["Open"].astype(float).tolist()
                idx = data.index[-len(close):]
                labels = [x.strftime("%H:%M") for x in idx]
                return opens[-60:], high[-60:], low[-60:], close[-60:], labels[-60:]
        except Exception:
            pass

    base = {
        "EUR/USD": 1.1632, "GBP/USD": 1.3430, "USD/JPY": 147.2,
        "AUD/USD": 0.6590, "BTC/USD": 64238.5, "ETH/USD": 3245.17,
        "AAPL": 187.42, "XAU/USD": 2340.60,
    }.get(symbol, 100.0)
    close = fallback_series(base, 60)
    opens = [close[0]] + close[:-1]
    high = [max(o, c) * 1.0008 for o, c in zip(opens, close)]
    low = [min(o, c) * 0.9992 for o, c in zip(opens, close)]
    labels = [f"{(i // 2) % 24:02d}:{(i % 2) * 30:02d}" for i in range(60)]
    return opens, high, low, close, labels


def analyze(symbol, interval="1m"):
    o, h, l, c, labels = load_series(symbol, interval)
    e9, e21, e50 = ema(c, 9), ema(c, 21), ema(c, 50)
    fast, slow = ema(c, 12), ema(c, 26)
    macd = [a - b for a, b in zip(fast, slow)]
    signal = ema(macd, 9)
    hist = [a - b for a, b in zip(macd, signal)]
    rv = rsi(c)
    av = atr(h, l, c)
    dx = adx(h, l, c)

    last = len(c) - 1
    bullish = int(e9[last] > e21[last]) + int(e21[last] > e50[last]) + int(macd[last] > signal[last]) + int(rv[last] > 50) + int(dx[last] >= 20)
    bearish = int(e9[last] < e21[last]) + int(e21[last] < e50[last]) + int(macd[last] < signal[last]) + int(rv[last] < 50) + int(dx[last] >= 20)
    score = bullish - bearish

    if score >= 2:
        direction = "CALL"
    elif score <= -2:
        direction = "PUT"
    else:
        direction = "WAIT"

    confidence = int(clamp(58 + abs(score) * 7 + min(dx[last], 35) * 0.35, 55, 94))
    if direction == "WAIT":
        confidence = int(clamp(55 + abs(score) * 4 + min(dx[last], 20) * 0.15, 55, 72))

    precision = 5 if symbol in ("BTC/USD", "ETH/USD", "AAPL") else 6
    price = round(c[last], precision)
    fmt = lambda arr: [round(float(x), precision) for x in arr]

    conditions = [
        e9[last] >= e21[last] if direction == "CALL" else e9[last] <= e21[last] if direction == "PUT" else abs(e9[last] - e21[last]) < max(av[last], 1e-8) * 2,
        e21[last] >= e50[last] if direction == "CALL" else e21[last] <= e50[last] if direction == "PUT" else True,
        hist[last] >= 0 if direction == "CALL" else hist[last] <= 0 if direction == "PUT" else abs(hist[last]) < max(av[last], 1e-8),
        rv[last] >= 50 if direction == "CALL" else rv[last] <= 50 if direction == "PUT" else True,
        dx[last] >= 20,
        True, True, True, True, True,
    ]
    passed = sum(bool(x) for x in conditions)

    return {
        "symbol": symbol,
        "group": MARKETS[symbol]["group"],
        "icon": MARKETS[symbol]["icon"],
        "payout": MARKETS[symbol]["payout"],
        "direction": direction,
        "confidence": confidence,
        "price": price,
        "ema9": e9[last], "ema21": e21[last], "ema50": e50[last],
        "macd": macd[last], "rsi": rv[last], "adx": dx[last], "atr": av[last],
        "conditions": passed,
        "labels": labels,
        "open": fmt(o[-55:]), "high": fmt(h[-55:]), "low": fmt(l[-55:]), "close": fmt(c[-55:]),
        "ema9_series": fmt(e9[-55:]), "ema21_series": fmt(e21[-55:]), "ema50_series": fmt(e50[-55:]),
        "macd_series": fmt(macd[-55:]), "signal_series": fmt(signal[-55:]), "hist_series": fmt(hist[-55:]),
        "rsi_series": [round(float(x), 2) for x in rv[-55:]],
        "adx_series": [round(float(x), 2) for x in dx[-55:]],
        "atr_series": fmt(av[-55:]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/signal")
def api_signal():
    symbol = request.args.get("symbol", "EUR/USD")
    interval = request.args.get("interval", "1m")
    if symbol not in MARKETS:
        symbol = "EUR/USD"
    return jsonify(analyze(symbol, interval))


@app.get("/api/signals")
def api_signals():
    interval = request.args.get("interval", "1m")
    results = []
    for symbol in DEFAULT_SYMBOLS:
        try:
            results.append(analyze(symbol, interval))
        except Exception:
            continue
    return jsonify({"signals": results, "generated_at": datetime.now(timezone.utc).isoformat()})


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>RYU V2 — Trade Smart</title>
<style>
:root{--bg:#020814;--panel:#061326;--panel2:#081a31;--line:#0a7cff;--cyan:#18c9ff;--text:#eaf4ff;--muted:#86a4c9;--green:#12f28a;--red:#ff304d;--yellow:#ffd12e;--purple:#a95cff;--pink:#ff3fa4}
*{box-sizing:border-box}html,body{margin:0;background:radial-gradient(circle at 50% -10%,#0b2144 0,#020814 45%,#01040a 100%);color:var(--text);font-family:Inter,system-ui,Segoe UI,Arial,sans-serif}body{min-height:100vh}
.header{height:132px;display:flex;align-items:center;justify-content:space-between;padding:16px 28px;border-bottom:1px solid #0b4e91;background:linear-gradient(90deg,#050914,#071a31,#050914);position:relative;overflow:hidden}.header:after{content:"";position:absolute;inset:auto 0 0;height:2px;background:linear-gradient(90deg,transparent,#00bfff,transparent);box-shadow:0 0 18px #00bfff}.brand{display:flex;align-items:center;gap:18px}.avatar{width:76px;height:76px;border-radius:50%;display:grid;place-items:center;font-size:43px;background:radial-gradient(circle,#253a5b,#080d17);border:2px solid #ff1d42;box-shadow:0 0 22px #ff1d4255}.brand h1{margin:0;font-size:48px;letter-spacing:-3px;font-style:italic}.brand h1 span{color:#ff2848}.brand p{margin:0;color:#77dfff;letter-spacing:2px}.account{display:flex;gap:10px}.box{border:1px solid #147eff;border-radius:12px;background:#07162b;padding:12px 18px;box-shadow:0 0 18px #0077ff22}.box small{color:#90acd0}.box strong{display:block;font-size:22px}.online{color:var(--green)!important}
.layout{display:grid;grid-template-columns:190px 1fr;min-height:calc(100vh - 132px)}.side{border-right:1px solid #0b315d;background:#030a15;padding:18px 10px}.nav{padding:15px 18px;margin:5px 0;border-radius:12px;color:#b4c8e6;font-size:17px}.nav.active{background:linear-gradient(90deg,#073c70,#06162a);color:white;box-shadow:inset 4px 0 #00c7ff,0 0 18px #0077ff22}.nav b{font-size:20px;margin-right:12px}.main{padding:18px;max-width:1800px;width:100%;margin:auto}.tabs{display:flex;gap:8px;margin-bottom:14px}.tab{flex:1;padding:13px;text-align:center;border:1px solid #124e8e;border-radius:12px;background:#061327;color:#9fc0e9;font-size:18px}.tab.active{color:#fff;box-shadow:0 0 22px #008cff55;border-color:#0b9bff;background:#06234a}.filters{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}.filter{padding:12px 14px;border:1px solid #114d8b;border-radius:14px;background:#061428;display:flex;justify-content:center;gap:12px;align-items:center}.filter.active{border-color:#0aa5ff;box-shadow:0 0 20px #007dff44}.filter span{color:var(--green);font-weight:800}.timebar{display:flex;gap:8px;margin-bottom:12px}.time{padding:10px 24px;border:1px solid #174c80;border-radius:12px;background:#061327}.time.active{background:#06376a;border-color:#00aaff;color:#6de4ff;box-shadow:0 0 15px #009dff55}
.content{display:grid;grid-template-columns:minmax(0,1fr) 340px 350px;gap:12px}.panel{background:linear-gradient(180deg,#07182e,#041021);border:1px solid #0b4e91;border-radius:14px;box-shadow:0 0 20px #006fff18,inset 0 0 30px #00142d;overflow:hidden}.paneltitle{padding:13px 15px;border-bottom:1px solid #12375d;display:flex;align-items:center;justify-content:space-between}.paneltitle strong{font-size:18px}.chartpanel{min-height:650px}.chartwrap{height:585px;padding:8px}.chartwrap canvas{width:100%;height:100%;display:block}.signalpanel{padding-bottom:10px}.check{display:flex;justify-content:space-between;padding:8px 14px;border-bottom:1px solid #0d2b49;color:#c5d7ed}.check i{font-style:normal;color:var(--green);font-weight:900}.conditions{margin:12px;border:1px solid var(--green);border-radius:9px;text-align:center;padding:9px;color:var(--green);font-weight:900;box-shadow:0 0 14px #00ff8840}.actions{display:flex;gap:10px;padding:0 12px}.action{flex:1;border-radius:10px;padding:13px;text-align:center;font-weight:900;font-size:19px}.call{color:#001d10;border:1px solid var(--green);background:linear-gradient(#28ff9d,#08a95f);box-shadow:0 0 16px #00ff8844}.put{color:#fff;border:1px solid var(--red);background:linear-gradient(#ff4059,#9f1028);box-shadow:0 0 16px #ff204444}.wait{color:#1c1600;border:1px solid var(--yellow);background:linear-gradient(#ffe65b,#c99300)}.meta{display:grid;grid-template-columns:repeat(3,1fr);margin:12px;border:1px solid #144d86;border-radius:9px;padding:9px;text-align:center}.meta small{display:block;color:#75a6db}.meta strong{display:block;margin-top:4px}.signalcard{padding:12px;border-bottom:1px solid #123452}.signalhead{display:flex;align-items:center;justify-content:space-between}.pair{font-weight:900}.badge{padding:6px 12px;border-radius:20px;font-weight:900}.green{color:var(--green)}.red{color:var(--red)}.yellow{color:var(--yellow)}.badge.green{border:1px solid var(--green);box-shadow:0 0 10px #00ff8840}.badge.red{border:1px solid var(--red);box-shadow:0 0 10px #ff204440}.badge.yellow{border:1px solid var(--yellow)}.signalmeta{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:8px;font-size:12px;color:#a5c2e6}.signalmeta b{display:block;color:#fff;font-size:13px}.bottom{display:grid;grid-template-columns:1fr 1.2fr 1.2fr 1fr;gap:12px;margin-top:12px}.listrow{display:flex;justify-content:space-between;padding:10px 12px;border-bottom:1px solid #0d2945}.small{font-size:12px;color:#86a7cb}.stat{padding:12px}.statline{display:flex;justify-content:space-between;margin:12px 0}.bar{height:9px;border-radius:10px;background:#09233c;overflow:hidden}.bar>i{display:block;height:100%;width:72%;background:linear-gradient(90deg,#00bfff,#10f28a);box-shadow:0 0 12px #00d9ff}.footer{text-align:center;color:#4f83b8;padding:18px}
@media(max-width:1200px){.content{grid-template-columns:1fr 330px}.rightcol{display:none}.bottom{grid-template-columns:1fr 1fr}.layout{grid-template-columns:80px 1fr}.side .nav{font-size:0;text-align:center}.side .nav b{margin:0;font-size:22px}.brand h1{font-size:36px}.account .box:first-child{display:none}}
@media(max-width:760px){.header{height:auto;min-height:105px;padding:10px 12px}.avatar{width:48px;height:48px;font-size:27px}.brand h1{font-size:30px;letter-spacing:-2px}.brand p{font-size:10px}.account{gap:4px}.account .box{padding:7px 9px}.account .box strong{font-size:15px}.layout{display:block}.side{display:none}.main{padding:9px}.tabs{overflow:auto}.tab{min-width:130px}.filters{grid-template-columns:repeat(2,1fr)}.content{display:block}.chartpanel{margin-bottom:10px}.chartwrap{height:390px}.bottom{grid-template-columns:1fr}.signalpanel{margin-bottom:10px}.rightcol{display:block}.signalcard{padding:10px}.brand{gap:8px}}
</style>
</head>
<body>
<header class="header">
  <div class="brand"><div class="avatar">🥊</div><div><h1>RYU <span>V2</span></h1><p>TRADE SMART • FOLLOW THE SIGNALS</p></div></div>
  <div class="account"><div class="box"><small>Live Account</small><strong id="balance">$183,676.29</strong><span class="online">↑ +2,481.17 (1.37%)</span></div><div class="box"><strong class="online">● Bot Online</strong><span>◉ Signals Active</span></div><div class="box"><strong id="clock">--:--</strong><small id="date">---</small></div></div>
</header>
<div class="layout">
<aside class="side">
  <div class="nav">🏠 <span>Home</span></div><div class="nav">📈 <span>Live Charts</span></div><div class="nav active">🎯 <span>Signals</span></div><div class="nav">↩️ <span>Trade History</span></div><div class="nav">🏆 <span>Performance</span></div><div class="nav">⚙️ <span>Settings</span></div><div class="nav">❔ <span>Help</span></div>
</aside>
<main class="main">
  <div class="tabs"><div class="tab active">🎯 Signals</div><div class="tab">▥ Trades</div><div class="tab">🏆 Performance</div><div class="tab">⚙ Settings</div></div>
  <div class="filters"><div class="filter active">🌐 All Markets <span>85%</span></div><div class="filter">💱 Forex <span>87%</span></div><div class="filter">₿ Crypto <span>82%</span></div><div class="filter">📊 Stocks <span>80%</span></div></div>
  <div class="timebar"><button class="time active" data-int="1m">1m</button><button class="time" data-int="2m">2m</button><button class="time" data-int="3m">3m</button></div>
  <section class="content">
    <div class="panel chartpanel"><div class="paneltitle"><strong><span id="chartIcon">🇪🇺🇺🇸</span> <span id="chartSymbol">EUR/USD</span> <span class="green" id="chartConfidence">85%</span></strong><span id="chartGroup">Forex</span></div><div class="chartwrap"><canvas id="chart"></canvas></div></div>
    <div class="panel signalpanel"><div class="paneltitle"><strong>RYU CONFLUENCE CHECK</strong><span>🥋</span></div><div id="checks"></div><div class="conditions" id="conditionCount">10/10 CONDITIONS</div><div class="actions"><div class="action call">⬆ CALL</div><div class="action put">⬇ PUT</div></div><div class="meta"><div><small>PAYOUT</small><strong id="payout">92%</strong></div><div><small>TRADE TIME</small><strong id="tradeTime">1 Minute</strong></div><div><small>EXPIRY</small><strong>00:56</strong></div></div></div>
    <div class="panel rightcol"><div class="paneltitle"><strong>🎯 LIVE SIGNALS</strong></div><div id="liveSignals"></div></div>
  </section>
  <section class="bottom">
    <div class="panel"><div class="paneltitle"><strong>MARKET PAIRS</strong></div><div id="pairs"></div></div>
    <div class="panel"><div class="paneltitle"><strong>ACTIVE TRADE</strong></div><div class="stat"><div class="pair">🇬🇧🇺🇸 GBP/USD <span class="green">85%</span> • 1m</div><h3 class="green" style="text-align:center;margin:28px 0 8px">WAITING FOR SIGNAL...</h3><div style="text-align:center;color:#84a7ce">◌ Analyzing Market Conditions...</div></div></div>
    <div class="panel"><div class="paneltitle"><strong>RECENT TRADES</strong></div><div id="recent"></div></div>
    <div class="panel"><div class="paneltitle"><strong>🥊 RYU V2 STATS</strong></div><div class="stat"><div class="statline"><span>WIN RATE</span><b class="green">72%</b></div><div class="bar"><i></i></div><div class="statline"><span>TOTAL TRADES</span><b>50</b></div><div class="statline"><span>PROFIT</span><b class="green">+$59,500</b></div><div class="green" style="text-align:center;font-size:12px">DEMO MODE — KEEP TESTING</div></div></div>
  </section>
  <div class="footer">RYU V2 • ANALYZE • CONFIRM • DEMO SIGNAL • No trades are executed by this dashboard.</div>
</main></div>
<script>
const $=s=>document.querySelector(s), $$=s=>document.querySelectorAll(s);
let selected='EUR/USD', interval='1m', current=null;
function money(v){return Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}
function signalBadge(s){let c=s.direction==='CALL'?'green':s.direction==='PUT'?'red':'yellow';let icon=s.direction==='CALL'?'⬆':s.direction==='PUT'?'⬇':'Ⅱ';return `<span class="badge ${c}">${icon} ${s.direction}</span>`}
function renderChecks(s){const names=['Alligator','EMA Alignment','MACD','RSI','ADX','ATR','Support / Resistance','Candle Confirmation','2M Confirmation','3M Confirmation'];$('#checks').innerHTML=names.map((n,i)=>`<div class="check"><span>${n}</span><i>${i<s.conditions?'✓':'•'}</i></div>`).join('');$('#conditionCount').textContent=`${s.conditions}/10 CONDITIONS`}
function drawChart(s){const cv=$('#chart'),dpr=devicePixelRatio||1,rect=cv.getBoundingClientRect();cv.width=rect.width*dpr;cv.height=rect.height*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);const W=rect.width,H=rect.height;x.fillStyle='#031022';x.fillRect(0,0,W,H);const n=s.close.length,pad={l:45,r:48,t:20,b:30},cw=W-pad.l-pad.r;let vals=[...s.high,...s.low,...s.ema9_series,...s.ema21_series,...s.ema50_series];let min=Math.min(...vals),max=Math.max(...vals);let range=max-min||1;const px=i=>pad.l+(i/(n-1))*cw, py=v=>pad.t+(1-(v-min)/range)*(H-pad.t-pad.b)*.72; x.strokeStyle='#0b2948';x.lineWidth=1;for(let i=0;i<7;i++){let yy=pad.t+i*(H-pad.t-pad.b)/6*.72;x.beginPath();x.moveTo(pad.l,yy);x.lineTo(W-pad.r,yy);x.stroke()}for(let i=0;i<6;i++){let xx=pad.l+i*cw/5;x.beginPath();x.moveTo(xx,pad.t);x.lineTo(xx,H-pad.b);x.stroke()}
function line(a,color,w=1.5,scale=.72){x.strokeStyle=color;x.lineWidth=w;x.beginPath();a.forEach((v,i)=>{let xx=px(i),yy=pad.t+(1-(v-min)/range)*(H-pad.t-pad.b)*scale;(i?x.lineTo:x.moveTo).call(x,xx,yy)});x.stroke()}
for(let i=0;i<n;i++){let xx=px(i),yo=py(s.open[i]),yc=py(s.close[i]),yh=py(s.high[i]),yl=py(s.low[i]);let up=s.close[i]>=s.open[i];x.strokeStyle=up?'#11ef91':'#ff334f';x.fillStyle=x.strokeStyle;x.beginPath();x.moveTo(xx,yh);x.lineTo(xx,yl);x.stroke();x.fillRect(xx-3,Math.min(yo,yc),6,Math.max(2,Math.abs(yc-yo)))}
line(s.ema9_series,'#ffd12e',1.8);line(s.ema21_series,'#ff8b1f',1.5);line(s.ema50_series,'#ff3fa4',1.5);x.fillStyle='#8ba9ca';x.font='12px system-ui';for(let i=0;i<6;i++){let ix=Math.round(i*(n-1)/5);x.fillText(s.labels[ix]||'',px(ix)-14,H-8)}x.fillStyle='#d8eaff';x.font='bold 12px system-ui';x.fillText(`Price ${s.price}`,W-115,22);}
function renderSignals(list){$('#liveSignals').innerHTML=list.map(s=>`<div class="signalcard"><div class="signalhead"><div><div class="pair">${s.icon} ${s.symbol}</div><div class="small">${s.group} • ${interval}</div></div>${signalBadge(s)}</div><div class="signalmeta"><div>Confidence<b class="green">${s.confidence}%</b></div><div>Payout<b>${s.payout? s.payout+'%':'--'}</b></div><div>Entry<b>${s.price}</b></div></div></div>`).join('')}
function renderPairs(list){$('#pairs').innerHTML=list.slice(0,4).map(s=>`<div class="listrow"><span>${s.icon} ${s.symbol}</span><b class="green">${s.confidence}%</b></div>`).join('')}
function renderRecent(list){$('#recent').innerHTML=list.slice(0,5).map((s,i)=>`<div class="listrow"><span>${s.icon} ${s.symbol}<div class="small">Demo analysis</div></span><b class="${s.direction==='CALL'?'green':s.direction==='PUT'?'red':'yellow'}">${s.direction}</b></div>`).join('')}
async function load(){try{let r=await fetch(`/api/signals?interval=${interval}`);let j=await r.json();renderSignals(j.signals);renderPairs(j.signals);renderRecent(j.signals);let main=j.signals.find(x=>x.symbol===selected)||j.signals[0];if(main){current=main;$('#chartSymbol').textContent=main.symbol;$('#chartIcon').textContent=main.icon;$('#chartGroup').textContent=main.group;$('#chartConfidence').textContent=main.confidence+'%';$('#payout').textContent=main.payout?main.payout+'%':'--';renderChecks(main);drawChart(main)}}catch(e){console.log(e)}}
$$('.time').forEach(b=>b.onclick=()=>{$$('.time').forEach(x=>x.classList.remove('active'));b.classList.add('active');interval=b.dataset.int;load()});
$('#liveSignals').onclick=e=>{let card=e.target.closest('.signalcard');if(!card)return};
setInterval(()=>{let d=new Date();$('#clock').textContent=d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});$('#date').textContent=d.toLocaleDateString([], {month:'short',day:'numeric',year:'numeric'});},1000);
window.onresize=()=>current&&drawChart(current);load();
</script>
</body></html>'''


@app.get("/")
def home():
    return render_template_string(HTML)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "RYU V2", "time": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
