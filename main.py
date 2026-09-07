import os
import math
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, request, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("ryu-v2")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")

app = Flask(__name__)

SYMBOLS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X",
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "AAPL": "AAPL",
    "XAU/USD": "GC=F",
}

DASHBOARD = r"""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RYU V2</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{margin:0;background:#050914;color:#eaf2ff;font-family:Arial,sans-serif}
.wrap{max-width:1200px;margin:auto;padding:18px}
h1{color:#20d7ff;margin:0 0 5px}.sub{color:#8ea8c7}
.grid{display:grid;grid-template-columns:2fr 1fr;gap:14px;margin-top:18px}
.card{background:#091326;border:1px solid #153c67;border-radius:16px;padding:16px;box-shadow:0 0 22px #061a33}
select,button{background:#0c1c35;color:white;border:1px solid #1c6db3;border-radius:10px;padding:10px}
.signal{font-size:28px;font-weight:800;margin:14px 0}.call{color:#20f28a}.put{color:#ff4f68}.wait{color:#ffd34d}
.row{display:flex;gap:8px;flex-wrap:wrap}.metric{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #132744}
.badge{padding:7px 10px;border-radius:999px;background:#102844}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<h1>RYU V2</h1><div class="sub">Analyze • Confirm • Demo Signal</div>
<div class="row" style="margin-top:14px">
<select id="symbol">
{% for s in symbols %}<option>{{s}}</option>{% endfor %}
</select>
<select id="period"><option value="1d">1 Day</option><option value="5d">5 Days</option><option value="1mo">1 Month</option></select>
<button onclick="loadData()">Refresh</button>
</div>
<div class="grid">
<div class="card"><canvas id="chart"></canvas></div>
<div class="card">
<div id="signal" class="signal wait">WAIT</div>
<div id="confidence" class="badge">Confidence: --</div>
<div class="metric"><span>Price</span><b id="price">--</b></div>
<div class="metric"><span>EMA 9 / 21 / 50</span><b id="ema">--</b></div>
<div class="metric"><span>MACD</span><b id="macd">--</b></div>
<div class="metric"><span>RSI</span><b id="rsi">--</b></div>
<div class="metric"><span>ADX</span><b id="adx">--</b></div>
<div class="metric"><span>ATR</span><b id="atr">--</b></div>
<div class="metric"><span>Conditions</span><b id="conditions">--</b></div>
<p class="sub">Demo/signal mode only. No live orders are placed.</p>
</div>
</div>
</div>
<script>
let chart;
async function loadData(){
  const s=document.getElementById('symbol').value;
  const p=document.getElementById('period').value;
  const r=await fetch(`/api/market?symbol=${encodeURIComponent(s)}&period=${p}`);
  const d=await r.json();
  if(d.error){alert(d.error);return}
  const sig=d.signal;
  const el=document.getElementById('signal');
  el.textContent=sig.direction;
  el.className='signal '+sig.direction.toLowerCase();
  document.getElementById('confidence').textContent=`Confidence: ${sig.confidence}%`;
  document.getElementById('price').textContent=d.price;
  document.getElementById('ema').textContent=`${d.indicators.ema9} / ${d.indicators.ema21} / ${d.indicators.ema50}`;
  document.getElementById('macd').textContent=d.indicators.macd;
  document.getElementById('rsi').textContent=d.indicators.rsi;
  document.getElementById('adx').textContent=d.indicators.adx;
  document.getElementById('atr').textContent=d.indicators.atr;
  document.getElementById('conditions').textContent=`${sig.conditions}/10`;
  const ctx=document.getElementById('chart').getContext('2d');
  if(chart) chart.destroy();
  chart=new Chart(ctx,{type:'line',data:{labels:d.chart.labels,datasets:[
    {label:s+' Price',data:d.chart.close,borderWidth:2,tension:.25},
    {label:'EMA 9',data:d.chart.ema9,borderWidth:1},
    {label:'EMA 21',data:d.chart.ema21,borderWidth:1},
    {label:'EMA 50',data:d.chart.ema50,borderWidth:1}
  ]},options:{responsive:true,interaction:{mode:'index',intersect:false},scales:{x:{ticks:{maxTicksLimit:10}},y:{beginAtZero:false}}}});
}
loadData();
setInterval(loadData,60000);
</script>
</body></html>
"""

def clean_df(df):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Open","High","Low","Close"]).copy()

def fetch_data(symbol, period="1d", interval="5m"):
    ticker = SYMBOLS.get(symbol)
    if not ticker:
        raise ValueError("Unsupported symbol")
    df = yf.download(
        ticker, period=period, interval=interval,
        auto_adjust=False, progress=False, threads=False
    )
    df = clean_df(df)
    if df.empty:
        raise ValueError("No market data returned")
    return df

def indicators(df):
    close, high, low = df["Close"], df["High"], df["Low"]
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    tr = pd.concat([
        high-low,
        (high-close.shift()).abs(),
        (low-close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    plus_di = 100 * plus_dm.rolling(14).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.rolling(14).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, np.nan)
    adx = dx.rolling(14).mean()

    return {
        "ema9": ema9, "ema21": ema21, "ema50": ema50,
        "macd": macd, "macd_signal": macd_signal,
        "rsi": rsi, "atr": atr, "adx": adx,
    }

def make_signal(df):
    ind = indicators(df)
    i = -1
    prev = -2
    close = float(df["Close"].iloc[i])
    e9, e21, e50 = (float(ind[k].iloc[i]) for k in ("ema9","ema21","ema50"))
    macd = float(ind["macd"].iloc[i]); ms = float(ind["macd_signal"].iloc[i])
    rsi = float(ind["rsi"].iloc[i]) if not math.isnan(float(ind["rsi"].iloc[i])) else 50.0
    adx = float(ind["adx"].iloc[i]) if not math.isnan(float(ind["adx"].iloc[i])) else 0.0

    bull = [
        e9 > e21,
        e21 > e50,
        macd > ms,
        rsi > 50,
        adx >= 20,
        close > e9,
        close > e21,
        float(df["Close"].iloc[i]) > float(df["Open"].iloc[i]),
        float(ind["macd"].iloc[i]) > float(ind["macd"].iloc[prev]),
        close > float(df["Close"].iloc[prev]),
    ]
    bear = [
        e9 < e21,
        e21 < e50,
        macd < ms,
        rsi < 50,
        adx >= 20,
        close < e9,
        close < e21,
        float(df["Close"].iloc[i]) < float(df["Open"].iloc[i]),
        float(ind["macd"].iloc[i]) < float(ind["macd"].iloc[prev]),
        close < float(df["Close"].iloc[prev]),
    ]
    b, s = sum(bull), sum(bear)
    if b >= 7 and b > s:
        direction, conditions = "CALL", b
    elif s >= 7 and s > b:
        direction, conditions = "PUT", s
    else:
        direction, conditions = "WAIT", max(b, s)
    confidence = int(min(99, max(50, round(50 + abs(b-s)*5 + max(0, max(b,s)-7)*4))))
    return direction, confidence, conditions, ind

def fmt(v):
    return round(float(v), 6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Open Ryu V2 Dashboard", url=PUBLIC_URL or "https://example.com")]]
    await update.message.reply_text(
        "🔥 RYU V2 ONLINE\n\nAnalyze • Confirm • Demo Signal\n\nUse /signal EUR/USD or /signal BTC/USD.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = " ".join(context.args).strip().upper() if context.args else "EUR/USD"
    if symbol not in SYMBOLS:
        await update.message.reply_text("Supported: " + ", ".join(SYMBOLS.keys()))
        return
    try:
        df = fetch_data(symbol, "5d", "15m")
        direction, confidence, conditions, ind = make_signal(df)
        price = float(df["Close"].iloc[-1])
        await update.message.reply_text(
            f"RYU V2 — {symbol}\n"
            f"Signal: {direction}\n"
            f"Confidence: {confidence}%\n"
            f"Conditions: {conditions}/10\n"
            f"Price: {price:.6f}\n\n"
            f"Demo/signal mode only — no live orders."
        )
    except Exception as e:
        log.exception("Signal error")
        await update.message.reply_text(f"Unable to calculate signal: {e}")

@app.get("/")
def home():
    return render_template_string(DASHBOARD, symbols=SYMBOLS.keys())

@app.get("/healthz")
def healthz():
    return jsonify(status="ok", service="ryu-v2")

@app.get("/api/market")
def market():
    symbol = request.args.get("symbol", "EUR/USD")
    period = request.args.get("period", "1d")
    try:
        df = fetch_data(symbol, period, "5m" if period == "1d" else "15m")
        direction, confidence, conditions, ind = make_signal(df)
        n = min(len(df), 120)
        x = df.tail(n)
        out = {
            "symbol": symbol,
            "price": fmt(x["Close"].iloc[-1]),
            "signal": {"direction": direction, "confidence": confidence, "conditions": conditions},
            "indicators": {
                "ema9": fmt(ind["ema9"].iloc[-1]),
                "ema21": fmt(ind["ema21"].iloc[-1]),
                "ema50": fmt(ind["ema50"].iloc[-1]),
                "macd": fmt(ind["macd"].iloc[-1]),
                "rsi": fmt(ind["rsi"].iloc[-1]),
                "adx": fmt(ind["adx"].iloc[-1]),
                "atr": fmt(ind["atr"].iloc[-1]),
            },
            "chart": {
                "labels": [str(v) for v in x.index],
                "close": [fmt(v) for v in x["Close"]],
                "ema9": [fmt(v) for v in ind["ema9"].tail(n)],
                "ema21": [fmt(v) for v in ind["ema21"].tail(n)],
                "ema50": [fmt(v) for v in ind["ema50"].tail(n)],
            },
        }
        return jsonify(out)
    except Exception as e:
        log.exception("Market error")
        return jsonify(error=str(e)), 502

def build_telegram_app():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is missing")
    bot = Application.builder().token(TELEGRAM_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("signal", signal_cmd))
    return bot

telegram_app = None

@app.post("/telegram")
async def telegram_webhook():
    global telegram_app
    if WEBHOOK_SECRET:
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if supplied != WEBHOOK_SECRET:
            return "forbidden", 403
    if telegram_app is None:
        telegram_app = build_telegram_app()
        await telegram_app.initialize()
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "ok"

@app.post("/admin/setup-webhook")
async def setup_webhook():
    global telegram_app
    if not PUBLIC_URL:
        return jsonify(error="PUBLIC_URL is missing"), 400
    telegram_app = build_telegram_app()
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(
        url=f"{PUBLIC_URL}/telegram",
        secret_token=WEBHOOK_SECRET or None,
        allowed_updates=["message"],
    )
    return jsonify(status="webhook-set", url=f"{PUBLIC_URL}/telegram")

@app.post("/admin/delete-webhook")
async def delete_webhook():
    global telegram_app
    if telegram_app is None:
        telegram_app = build_telegram_app()
        await telegram_app.initialize()
    await telegram_app.bot.delete_webhook(drop_pending_updates=False)
    return jsonify(status="webhook-deleted")

if __name__ == "__main__":
    # Local development only. Render should start with gunicorn.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
