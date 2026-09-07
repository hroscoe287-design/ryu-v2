import os
import math
import time
import threading
from datetime import datetime, timezone

import yfinance as yf
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# ============================================================
# RYU V2 - PRODUCTION SINGLE FILE DASHBOARD
# ============================================================

APP_NAME = "RYU V2"
CACHE_SECONDS = 20

SYMBOLS = {
    "forex": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "JPY=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "CAD=X",
        "USD/CHF": "CHF=X",
    },
    "crypto": {
        "BTC/USD": "BTC-USD",
        "ETH/USD": "ETH-USD",
        "SOL/USD": "SOL-USD",
        "XRP/USD": "XRP-USD",
    },
    "stocks": {
        "AAPL": "AAPL",
        "TSLA": "TSLA",
        "NVDA": "NVDA",
        "MSFT": "MSFT",
        "AMZN": "AMZN",
        "META": "META",
    },
}

TIMEFRAMES = {
    "1m": {"interval": "1m", "period": "1d"},
    "2m": {"interval": "2m", "period": "1d"},
    "3m": {"interval": "2m", "period": "2d"},
}

cache = {}
cache_lock = threading.Lock()


# ============================================================
# INDICATORS
# ============================================================

def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values, period):
    if not values:
        return None

    alpha = 2 / (period + 1)
    result = values[0]

    for value in values[1:]:
        result = (value * alpha) + (result * (1 - alpha))

    return result


def rsi(values, period=14):
    if len(values) < period + 1:
        return 50.0

    gains = []
    losses = []

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values):
    if len(values) < 35:
        return 0.0, 0.0, 0.0

    fast = ema(values, 12)
    slow = ema(values, 26)

    line = fast - slow

    macd_history = []
    for i in range(26, len(values) + 1):
        subset = values[:i]
        macd_history.append(ema(subset, 12) - ema(subset, 26))

    signal = ema(macd_history, 9)
    histogram = line - signal

    return line, signal, histogram


def atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0.0

    true_ranges = []

    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    return sum(true_ranges[-period:]) / period


def bollinger(values, period=20, multiplier=2):
    if len(values) < period:
        middle = values[-1]
        return middle, middle, middle

    window = values[-period:]
    middle = sum(window) / period

    variance = sum((x - middle) ** 2 for x in window) / period
    deviation = math.sqrt(variance)

    return (
        middle + multiplier * deviation,
        middle,
        middle - multiplier * deviation,
    )


# ============================================================
# MARKET DATA
# ============================================================

def clean_number(value):
    try:
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    except Exception:
        return None


def get_market_data(symbol, timeframe):
    now = time.time()
    key = f"{symbol}:{timeframe}"

    with cache_lock:
        cached = cache.get(key)
        if cached and now - cached["time"] < CACHE_SECONDS:
            return cached["data"]

    config = TIMEFRAMES.get(timeframe, TIMEFRAMES["1m"])

    ticker = yf.Ticker(symbol)

    try:
        df = ticker.history(
            period=config["period"],
            interval=config["interval"],
            auto_adjust=False,
            prepost=False,
        )
    except Exception as exc:
        raise RuntimeError(f"Market data error: {exc}")

    if df is None or df.empty:
        raise RuntimeError("No market data returned.")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    if len(df) < 30:
        raise RuntimeError("Not enough market data.")

    closes = [float(x) for x in df["Close"].tolist()]
    highs = [float(x) for x in df["High"].tolist()]
    lows = [float(x) for x in df["Low"].tolist()]
    opens = [float(x) for x in df["Open"].tolist()]

    volumes = []
    if "Volume" in df.columns:
        volumes = [
            clean_number(x) or 0
            for x in df["Volume"].tolist()
        ]

    timestamps = []

    for index in df.index:
        try:
            timestamps.append(index.isoformat())
        except Exception:
            timestamps.append(str(index))

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamps": timestamps[-100:],
        "open": opens[-100:],
        "high": highs[-100:],
        "low": lows[-100:],
        "close": closes[-100:],
        "volume": volumes[-100:],
        "price": closes[-1],
        "previous_price": closes[-2],
    }

    with cache_lock:
        cache[key] = {
            "time": now,
            "data": result,
        }

    return result


# ============================================================
# SIGNAL ENGINE
# ============================================================

def calculate_signal(data):
    closes = data["close"]
    highs = data["high"]
    lows = data["low"]

    price = closes[-1]

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)

    rsi_value = rsi(closes, 14)

    macd_line, macd_signal, macd_hist = macd(closes)

    upper, middle, lower = bollinger(closes)

    atr_value = atr(highs, lows, closes)

    score = 0
    reasons = []

    # Trend
    if ema9 > ema21:
        score += 2
        reasons.append("EMA 9 above EMA 21")
    elif ema9 < ema21:
        score -= 2
        reasons.append("EMA 9 below EMA 21")

    # Longer trend
    if ema21 > ema50:
        score += 1
        reasons.append("Long trend bullish")
    elif ema21 < ema50:
        score -= 1
        reasons.append("Long trend bearish")

    # RSI
    if 50 <= rsi_value <= 68:
        score += 1
        reasons.append("RSI bullish zone")
    elif 32 <= rsi_value < 50:
        score -= 1
        reasons.append("RSI bearish zone")

    # Avoid chasing extreme RSI
    if rsi_value > 75:
        score -= 1
        reasons.append("RSI overbought")
    elif rsi_value < 25:
        score += 1
        reasons.append("RSI oversold")

    # MACD
    if macd_hist > 0:
        score += 2
        reasons.append("MACD momentum positive")
    elif macd_hist < 0:
        score -= 2
        reasons.append("MACD momentum negative")

    # Bollinger position
    if price > middle:
        score += 1
        reasons.append("Price above Bollinger midpoint")
    elif price < middle:
        score -= 1
        reasons.append("Price below Bollinger midpoint")

    # Recent candle direction
    if closes[-1] > closes[-2]:
        score += 1
        reasons.append("Latest candle rising")
    elif closes[-1] < closes[-2]:
        score -= 1
        reasons.append("Latest candle falling")

    max_score = 11
    strength = abs(score) / max_score

    if score >= 4:
        direction = "CALL"
    elif score <= -4:
        direction = "PUT"
    else:
        direction = "WAIT"

    confidence = 50 + (strength * 45)

    if direction == "WAIT":
        confidence = min(confidence, 69)

    confidence = round(max(50, min(95, confidence)))

    if confidence >= 85:
        risk = "LOW"
    elif confidence >= 75:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    if score >= 4:
        trend = "BULLISH"
    elif score <= -4:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    payout = 92

    return {
        "direction": direction,
        "confidence": confidence,
        "score": score,
        "max_score": max_score,
        "risk": risk,
        "trend": trend,
        "payout": payout,
        "entry": round(price, 6),
        "rsi": round(rsi_value, 2),
        "ema9": round(ema9, 6),
        "ema21": round(ema21, 6),
        "ema50": round(ema50, 6),
        "macd": round(macd_line, 8),
        "macd_signal": round(macd_signal, 8),
        "macd_histogram": round(macd_hist, 8),
        "bollinger_upper": round(upper, 6),
        "bollinger_middle": round(middle, 6),
        "bollinger_lower": round(lower, 6),
        "atr": round(atr_value, 8),
        "reasons": reasons,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_signal(asset, market, timeframe):
    symbol = SYMBOLS.get(market, {}).get(asset)

    if not symbol:
        raise ValueError("Unknown asset.")

    data = get_market_data(symbol, timeframe)
    signal = calculate_signal(data)

    signal["asset"] = asset
    signal["market"] = market
    signal["timeframe"] = timeframe
    signal["symbol"] = symbol

    signal["price_change"] = round(
        ((data["price"] - data["previous_price"])
         / data["previous_price"]) * 100,
        4,
    )

    signal["chart"] = {
        "timestamps": data["timestamps"],
        "close": data["close"],
        "high": data["high"],
        "low": data["low"],
    }

    return signal


# ============================================================
# API
# ============================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "engine": APP_NAME,
        "time": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/markets")
def markets():
    return jsonify(SYMBOLS)


@app.route("/api/signal")
def api_signal():
    market = request.args.get("market", "forex").lower()
    asset = request.args.get("asset", "EUR/USD")
    timeframe = request.args.get("timeframe", "1m")

    if market not in SYMBOLS:
        return jsonify({"error": "Invalid market."}), 400

    if asset not in SYMBOLS[market]:
        return jsonify({"error": "Invalid asset."}), 400

    if timeframe not in TIMEFRAMES:
        return jsonify({"error": "Invalid timeframe."}), 400

    try:
        result = build_signal(asset, market, timeframe)
        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "error": str(exc),
            "asset": asset,
            "market": market,
            "timeframe": timeframe,
        }), 503


# ============================================================
# DASHBOARD
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RYU V2</title>

<style>
*{
    box-sizing:border-box;
}

body{
    margin:0;
    background:#070a10;
    color:#f5f7fb;
    font-family:Arial,Helvetica,sans-serif;
}

.header{
    height:70px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 24px;
    background:#0b0f17;
    border-bottom:1px solid #1b2432;
}

.logo{
    font-size:26px;
    font-weight:900;
    letter-spacing:2px;
}

.logo span{
    color:#54ddff;
}

.status{
    color:#59e6a5;
    font-size:13px;
}

.dot{
    display:inline-block;
    width:8px;
    height:8px;
    border-radius:50%;
    background:#59e6a5;
    margin-right:6px;
}

.layout{
    display:flex;
    min-height:calc(100vh - 70px);
}

.sidebar{
    width:205px;
    background:#090d14;
    border-right:1px solid #1b2432;
    padding:20px 13px;
}

.nav{
    padding:14px;
    border-radius:9px;
    margin-bottom:7px;
    color:#8c97aa;
    cursor:pointer;
}

.nav.active,
.nav:hover{
    background:#151c28;
    color:white;
}

.main{
    flex:1;
    padding:22px;
    max-width:1500px;
    margin:auto;
}

.top{
    display:flex;
    justify-content:space-between;
    gap:15px;
    align-items:center;
    margin-bottom:20px;
}

h1{
    margin:0;
    font-size:25px;
}

.small{
    color:#7f8a9d;
    font-size:12px;
}

.filters{
    display:flex;
    gap:7px;
    flex-wrap:wrap;
}

button,
select{
    background:#111722;
    border:1px solid #283344;
    color:#d9dfeb;
    padding:9px 13px;
    border-radius:8px;
    cursor:pointer;
}

button.active{
    background:#54ddff;
    color:#061017;
    border-color:#54ddff;
    font-weight:bold;
}

.grid{
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:13px;
}

.card{
    background:#0d121b;
    border:1px solid #1c2635;
    border-radius:13px;
    padding:18px;
}

.label{
    color:#7e899d;
    font-size:11px;
    text-transform:uppercase;
    letter-spacing:1px;
}

.value{
    font-size:26px;
    font-weight:800;
    margin-top:7px;
}

.green{
    color:#59e6a5;
}

.red{
    color:#ff637c;
}

.blue{
    color:#54ddff;
}

.signal-layout{
    display:grid;
    grid-template-columns:1.25fr 1fr 1fr 1fr;
    gap:13px;
    margin-top:15px;
}

.signal-card{
    min-height:235px;
}

.pair{
    font-size:20px;
    font-weight:800;
}

.direction{
    font-size:47px;
    font-weight:900;
    margin:18px 0;
}

.meta{
    display:flex;
    justify-content:space-between;
    padding:10px 0;
    border-bottom:1px solid #1c2635;
}

.chart-card{
    margin-top:15px;
}

.chart-wrap{
    height:360px;
    margin-top:15px;
}

canvas{
    width:100%;
    height:100%;
}

.reason{
    margin-top:9px;
    padding:8px;
    background:#111722;
    border-radius:7px;
    color:#aab4c5;
    font-size:12px;
}

table{
    width:100%;
    border-collapse:collapse;
    margin-top:12px;
}

th,
td{
    padding:12px 8px;
    border-bottom:1px solid #1c2635;
    text-align:left;
    font-size:13px;
}

th{
    color:#7f899b;
    font-size:11px;
}

.footer{
    color:#5e697a;
    font-size:11px;
    margin-top:17px;
}

.loading{
    opacity:.55;
}

.error{
    color:#ff637c;
    margin-top:8px;
    font-size:12px;
}

@media(max-width:1050px){
    .grid{
        grid-template-columns:repeat(2,1fr);
    }

    .signal-layout{
        grid-template-columns:1fr 1fr;
    }
}

@media(max-width:700px){
    .sidebar{
        display:none;
    }

    .main{
        padding:13px;
    }

    .top{
        flex-direction:column;
        align-items:flex-start;
    }

    .grid,
    .signal-layout{
        grid-template-columns:1fr 1fr;
    }

    .signal-layout .signal-card:first-child{
        grid-column:1/-1;
    }
}
</style>
</head>

<body>

<header class="header">
    <div class="logo">RYU <span>V2</span></div>
    <div class="status">
        <span class="dot"></span>
        <span id="engineStatus">ENGINE ONLINE</span>
    </div>
</header>

<div class="layout">

<aside class="sidebar">
    <div class="nav active">◈ Signals</div>
    <div class="nav">▣ Trades</div>
    <div class="nav">◒ Performance</div>
    <div class="nav">⚙ Settings</div>
</aside>

<main class="main">

<div class="top">

<div>
<h1>RYU V2 Trading Dashboard</h1>
<div class="small">Live market data • Technical signal engine</div>
</div>

<div class="filters">
    <button class="market active" data-market="forex">Forex</button>
    <button class="market" data-market="crypto">Crypto</button>
    <button class="market" data-market="stocks">Stocks</button>

    <select id="asset"></select>

    <button class="tf active" data-tf="1m">1m</button>
    <button class="tf" data-tf="2m">2m</button>
    <button class="tf" data-tf="3m">3m</button>
</div>

</div>

<section class="grid">

<div class="card">
<div class="label">Market</div>
<div class="value blue" id="marketValue">EUR/USD</div>
</div>

<div class="card">
<div class="label">Signal</div>
<div class="value" id="signalValue">WAIT</div>
</div>

<div class="card">
<div class="label">Confidence</div>
<div class="value" id="confidenceValue">--%</div>
</div>

<div class="card">
<div class="label">Payout</div>
<div class="value green" id="payoutValue">92%</div>
</div>

</section>

<section class="signal-layout">

<div class="card signal-card">
<div class="pair" id="pair">EUR/USD</div>
<div class="small" id="timeframeLabel">1 minute</div>

<div class="direction" id="direction">WAIT</div>

<div class="meta">
<span class="small">Entry</span>
<span id="entry">--</span>
</div>

<div class="meta">
<span class="small">Confidence</span>
<span id="confidence">--%</span>
</div>

<div class="meta">
<span class="small">Risk</span>
<span id="risk">--</span>
</div>
</div>

<div class="card signal-card">
<div class="label">Trend</div>
<div class="value" id="trend">--</div>

<div class="meta" style="margin-top:20px">
<span class="small">EMA 9</span>
<span id="ema9">--</span>
</div>

<div class="meta">
<span class="small">EMA 21</span>
<span id="ema21">--</span>
</div>

<div class="meta">
<span class="small">EMA 50</span>
<span id="ema50">--</span>
</div>
</div>

<div class="card signal-card">
<div class="label">Momentum</div>
<div class="value blue" id="rsi">--</div>
<div class="small" style="margin-top:5px">RSI</div>

<div class="meta" style="margin-top:20px">
<span class="small">MACD</span>
<span id="macd">--</span>
</div>

<div class="meta">
<span class="small">Histogram</span>
<span id="histogram">--</span>
</div>
</div>

<div class="card signal-card">
<div class="label">Confluence</div>
<div class="value" id="score">-- / 11</div>

<div id="reasons"></div>
</div>

</section>

<div class="card chart-card">

<div style="display:flex;justify-content:space-between">
<div>
<div class="pair" id="chartTitle">EUR/USD</div>
<div class="small">Live price action</div>
</div>

<div class="green">● LIVE</div>
</div>

<div class="chart-wrap">
<canvas id="chart"></canvas>
</div>

<div id="error" class="error"></div>

</div>

<div class="card" style="margin-top:15px">

<div class="pair">Signal Analysis</div>

<table>
<thead>
<tr>
<th>INDICATOR</th>
<th>VALUE</th>
<th>READING</th>
</tr>
</thead>

<tbody>

<tr>
<td>RSI</td>
<td id="tableRsi">--</td>
<td id="rsiReading">--</td>
</tr>

<tr>
<td>EMA Trend</td>
<td id="tableEma">--</td>
<td id="emaReading">--</td>
</tr>

<tr>
<td>MACD</td>
<td id="tableMacd">--</td>
<td id="macdReading">--</td>
</tr>

<tr>
<td>Bollinger</td>
<td id="tableBollinger">--</td>
<td id="bollingerReading">--</td>
</tr>

<tr>
<td>RYU Decision</td>
<td id="tableDecision">--</td>
<td id="decisionReading">--</td>
</tr>

</tbody>
</table>

</div>

<div class="footer">
RYU V2 • Live technical analysis engine •
<span id="updated">--</span>
</div>

</main>
</div>

<script>

let market = "forex";
let timeframe = "1m";
let currentAsset = "EUR/USD";
let currentData = null;

const assetSelect = document.getElementById("asset");

function setColor(element, direction){
    element.classList.remove("green","red","blue");

    if(direction === "CALL" || direction === "BULLISH"){
        element.classList.add("green");
    }
    else if(direction === "PUT" || direction === "BEARISH"){
        element.classList.add("red");
    }
    else{
        element.classList.add("blue");
    }
}

async function loadMarkets(){

    const response = await fetch("/api/markets");
    const markets = await response.json();

    assetSelect.innerHTML = "";

    Object.keys(markets[market]).forEach(asset => {

        const option = document.createElement("option");
        option.value = asset;
        option.textContent = asset;

        assetSelect.appendChild(option);
    });

    if(markets[market][currentAsset]){
        assetSelect.value = currentAsset;
    }else{
        currentAsset = Object.keys(markets[market])[0];
        assetSelect.value = currentAsset;
    }
}

async function loadSignal(){

    document.body.classList.add("loading");

    try{

        const url =
            "/api/signal?market=" +
            encodeURIComponent(market) +
            "&asset=" +
            encodeURIComponent(currentAsset) +
            "&timeframe=" +
            encodeURIComponent(timeframe);

        const response = await fetch(url);
        const data = await response.json();

        if(!response.ok){
            throw new Error(data.error || "Unable to load market data.");
        }

        currentData = data;
        updateDashboard(data);

        document.getElementById("engineStatus").textContent =
            "ENGINE ONLINE";

    }catch(error){

        document.getElementById("error").textContent =
            "Market data unavailable: " + error.message;

        document.getElementById("engineStatus").textContent =
            "DATA RETRYING";

    }finally{

        document.body.classList.remove("loading");
    }
}

function updateDashboard(data){

    const direction = data.direction;

    document.getElementById("marketValue").textContent =
        data.asset;

    document.getElementById("signalValue").textContent =
        direction;

    document.getElementById("confidenceValue").textContent =
        data.confidence + "%";

    document.getElementById("payoutValue").textContent =
        data.payout + "%";

    document.getElementById("pair").textContent =
        data.asset;

    document.getElementById("chartTitle").textContent =
        data.asset;

    document.getElementById("timeframeLabel").textContent =
        data.timeframe;

    document.getElementById("direction").textContent =
        direction;

    document.getElementById("entry").textContent =
        data.entry;

    document.getElementById("confidence").textContent =
        data.confidence + "%";

    document.getElementById("risk").textContent =
        data.risk;

    document.getElementById("trend").textContent =
        data.trend;

    document.getElementById("rsi").textContent =
        data.rsi;

    document.getElementById("ema9").textContent =
        data.ema9;

    document.getElementById("ema21").textContent =
        data.ema21;

    document.getElementById("ema50").textContent =
        data.ema50;

    document.getElementById("macd").textContent =
        data.macd;

    document.getElementById("histogram").textContent =
        data.macd_histogram;

    document.getElementById("score").textContent =
        Math.abs(data.score) + " / " + data.max_score;

    setColor(document.getElementById("signalValue"), direction);
    setColor(document.getElementById("direction"), direction);
    setColor(document.getElementById("trend"), data.trend);

    document.getElementById("tableRsi").textContent =
        data.rsi;

    document.getElementById("rsiReading").textContent =
        data.rsi > 70 ? "OVERBOUGHT" :
        data.rsi < 30 ? "OVERSOLD" :
        data.rsi >= 50 ? "BULLISH" : "BEARISH";

    document.getElementById("tableEma").textContent =
        data.ema9 + " / " + data.ema21;

    document.getElementById("emaReading").textContent =
        data.ema9 > data.ema21 ? "BULLISH" : "BEARISH";

    document.getElementById("tableMacd").textContent =
        data.macd;

    document.getElementById("macdReading").textContent =
        data.macd_histogram > 0 ? "POSITIVE" : "NEGATIVE";

    document.getElementById("tableBollinger").textContent =
        data.bollinger_middle;

    document.getElementById("bollingerReading").textContent =
        data.entry > data.bollinger_middle ?
        "ABOVE MIDLINE" : "BELOW MIDLINE";

    document.getElementById("tableDecision").textContent =
        direction;

    document.getElementById("decisionReading").textContent =
        data.confidence + "% CONFIDENCE";

    const reasons =
        document.getElementById("reasons");

    reasons.innerHTML = "";

    data.reasons.slice(0,4).forEach(reason => {

        const div = document.createElement("div");

        div.className = "reason";
        div.textContent = "✓ " + reason;

        reasons.appendChild(div);
    });

    document.getElementById("updated").textContent =
        new Date().toLocaleTimeString();

    drawChart(data.chart);
}

function drawChart(chart){

    const canvas =
        document.getElementById("chart");

    const ctx =
        canvas.getContext("2d");

    const rect =
        canvas.getBoundingClientRect();

    const dpr =
        window.devicePixelRatio || 1;

    canvas.width =
        rect.width * dpr;

    canvas.height =
        rect.height * dpr;

    ctx.setTransform(
        dpr,0,0,dpr,0,0
    );

    const w = rect.width;
    const h = rect.height;

    ctx.clearRect(0,0,w,h);

    const prices = chart.close;

    if(!prices || prices.length < 2){
        return;
    }

    let min =
        Math.min(...prices);

    let max =
        Math.max(...prices);

    let range =
        max - min;

    if(range === 0){
        range = 1;
    }

    ctx.strokeStyle = "#1b2534";
    ctx.lineWidth = 1;

    for(let i=1;i<6;i++){

        const y =
            (h / 6) * i;

        ctx.beginPath();
        ctx.moveTo(0,y);
        ctx.lineTo(w,y);
        ctx.stroke();
    }

    for(let i=1;i<10;i++){

        const x =
            (w / 10) * i;

        ctx.beginPath();
        ctx.moveTo(x,0);
        ctx.lineTo(x,h);
        ctx.stroke();
    }

    ctx.beginPath();

    prices.forEach((price,i)=>{

        const x =
            (i / (prices.length-1)) * w;

        const y =
            h - ((price-min)/range) * (h-30) - 15;

        if(i === 0){
            ctx.moveTo(x,y);
        }else{
            ctx.lineTo(x,y);
        }
    });

    ctx.strokeStyle = "#54ddff";
    ctx.lineWidth = 2;
    ctx.stroke();

    const last =
        prices[prices.length-1];

    const lastX = w;
    const lastY =
        h - ((last-min)/range) * (h-30) - 15;

    ctx.beginPath();
    ctx.arc(lastX,lastY,5,0,Math.PI*2);
    ctx.fillStyle="#59e6a5";
    ctx.fill();
}

document.querySelectorAll(".market").forEach(button => {

    button.addEventListener("click", async () => {

        document.querySelectorAll(".market")
            .forEach(b => b.classList.remove("active"));

        button.classList.add("active");

        market =
            button.dataset.market;

        await loadMarkets();
        await loadSignal();
    });
});

document.querySelectorAll(".tf").forEach(button => {

    button.addEventListener("click", async () => {

        document.querySelectorAll(".tf")
            .forEach(b => b.classList.remove("active"));

        button.classList.add("active");

        timeframe =
            button.dataset.tf;

        await loadSignal();
    });
});

assetSelect.addEventListener("change", () => {

    currentAsset =
        assetSelect.value;

    loadSignal();
});

window.addEventListener("resize", () => {

    if(currentData){
        drawChart(currentData.chart);
    }
});

async function start(){

    await loadMarkets();
    await loadSignal();

    setInterval(loadSignal, 30000);
}

start();

</script>

</body>
</html>
"""


@app.route("/")
def dashboard():
    return render_template_string(HTML)


# ============================================================
# RENDER ENTRY POINT
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        )
