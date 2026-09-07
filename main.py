import os
import time
import math
import requests
import threading
from datetime import datetime, timezone

import yfinance as yf
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# ============================================================
# RYU V2
# MULTI-MARKET TRADING DASHBOARD
# FOREX / CRYPTO / STOCKS / OTC
# ============================================================

CACHE_SECONDS = 15

cache = {}
cache_lock = threading.Lock()


# ============================================================
# FOREX
# ============================================================

FOREX = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "USD/CHF": "CHF=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X",
    "NZD/USD": "NZDUSD=X",

    "EUR/GBP": "EURGBP=X",
    "EUR/JPY": "EURJPY=X",
    "EUR/CHF": "EURCHF=X",
    "EUR/AUD": "EURAUD=X",
    "EUR/CAD": "EURCAD=X",
    "EUR/NZD": "EURNZD=X",

    "GBP/JPY": "GBPJPY=X",
    "GBP/CHF": "GBPCHF=X",
    "GBP/AUD": "GBPAUD=X",
    "GBP/CAD": "GBPCAD=X",
    "GBP/NZD": "GBPNZD=X",

    "AUD/JPY": "AUDJPY=X",
    "AUD/NZD": "AUDNZD=X",
    "AUD/CAD": "AUDCAD=X",
    "AUD/CHF": "AUDCHF=X",

    "CAD/JPY": "CADJPY=X",
    "CAD/CHF": "CADCHF=X",

    "NZD/JPY": "NZDJPY=X",
    "NZD/CAD": "NZDCAD=X",
    "NZD/CHF": "NZDCHF=X",

    "USD/SGD": "SGD=X",
    "USD/HKD": "HKD=X",
    "USD/CNH": "CNH=X",
    "USD/SEK": "SEK=X",
    "USD/NOK": "NOK=X",
    "USD/DKK": "DKK=X",
    "USD/PLN": "PLN=X",
    "USD/MXN": "MXN=X",
    "USD/ZAR": "ZAR=X",
    "USD/TRY": "TRY=X",
}


# ============================================================
# CRYPTO
# Large practical list + Binance symbols
# ============================================================

CRYPTO = {
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "BNB/USD": "BNB-USD",
    "SOL/USD": "SOL-USD",
    "XRP/USD": "XRP-USD",
    "ADA/USD": "ADA-USD",
    "DOGE/USD": "DOGE-USD",
    "AVAX/USD": "AVAX-USD",
    "DOT/USD": "DOT-USD",
    "LINK/USD": "LINK-USD",
    "MATIC/USD": "MATIC-USD",
    "LTC/USD": "LTC-USD",
    "BCH/USD": "BCH-USD",
    "ATOM/USD": "ATOM-USD",
    "UNI/USD": "UNI-USD",
    "ETC/USD": "ETC-USD",
    "XLM/USD": "XLM-USD",
    "FIL/USD": "FIL-USD",
    "HBAR/USD": "HBAR-USD",
    "APT/USD": "APT-USD",
    "ARB/USD": "ARB-USD",
    "OP/USD": "OP-USD",
    "NEAR/USD": "NEAR-USD",
    "ALGO/USD": "ALGO-USD",
    "ICP/USD": "ICP-USD",
    "VET/USD": "VET-USD",
    "SAND/USD": "SAND-USD",
    "MANA/USD": "MANA-USD",
    "AAVE/USD": "AAVE-USD",
    "EOS/USD": "EOS-USD",
    "XTZ/USD": "XTZ-USD",
    "THETA/USD": "THETA-USD",
    "PEPE/USD": "PEPE-USD",
    "SHIB/USD": "SHIB-USD",
}


# ============================================================
# STOCKS
# Major US universe
# ============================================================

STOCKS = {
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "NVDA": "NVDA",
    "AMZN": "AMZN",
    "META": "META",
    "GOOGL": "GOOGL",
    "GOOG": "GOOG",
    "TSLA": "TSLA",
    "AVGO": "AVGO",
    "BRK-B": "BRK-B",
    "JPM": "JPM",
    "LLY": "LLY",
    "V": "V",
    "MA": "MA",
    "XOM": "XOM",
    "WMT": "WMT",
    "COST": "COST",
    "NFLX": "NFLX",
    "AMD": "AMD",
    "INTC": "INTC",
    "QCOM": "QCOM",
    "MU": "MU",
    "ORCL": "ORCL",
    "CRM": "CRM",
    "ADBE": "ADBE",
    "CSCO": "CSCO",
    "IBM": "IBM",
    "UBER": "UBER",
    "ABNB": "ABNB",
    "DIS": "DIS",
    "NKE": "NKE",
    "MCD": "MCD",
    "KO": "KO",
    "PEP": "PEP",
    "BA": "BA",
    "CAT": "CAT",
    "GE": "GE",
    "GM": "GM",
    "F": "F",
    "T": "T",
    "VZ": "VZ",
    "PYPL": "PYPL",
    "SQ": "SQ",
    "SHOP": "SHOP",
    "PLTR": "PLTR",
    "COIN": "COIN",
    "HOOD": "HOOD",
    "RIVN": "RIVN",
    "LCID": "LCID",
}


# ============================================================
# OTC
#
# IMPORTANT:
# These are OTC-market securities, NOT Pocket Option's
# proprietary OTC pricing.
# ============================================================

OTC = {
    "Nintendo": "NTDOY",
    "Tencent": "TCEHY",
    "Alibaba": "BABA",
    "Toyota": "TM",
    "Sony": "SONY",
    "Volkswagen": "VWAGY",
    "Shell": "SHEL",
    "Unilever": "UL",
    "BP": "BP",
    "HSBC": "HSBC",
}


MARKETS = {
    "forex": FOREX,
    "crypto": CRYPTO,
    "stocks": STOCKS,
    "otc": OTC,
}


TIMEFRAMES = {
    "1m": {
        "interval": "1m",
        "period": "1d",
    },
    "2m": {
        "interval": "2m",
        "period": "1d",
    },
    "3m": {
        "interval": "2m",
        "period": "2d",
    },
}


# ============================================================
# INDICATORS
# ============================================================

def ema(values, period):

    if len(values) < period:
        return values[-1]

    multiplier = 2 / (period + 1)

    result = sum(values[:period]) / period

    for value in values[period:]:
        result = (
            (value - result) * multiplier
        ) + result

    return result


def rsi(values, period=14):

    if len(values) < period + 1:
        return 50

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = values[i] - values[i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):

        avg_gain = (
            ((avg_gain * (period - 1)) + gains[i])
            / period
        )

        avg_loss = (
            ((avg_loss * (period - 1)) + losses[i])
            / period
        )

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def macd(values):

    if len(values) < 35:
        return 0, 0, 0

    fast = ema(values, 12)
    slow = ema(values, 26)

    line = fast - slow

    history = []

    for i in range(26, len(values) + 1):

        subset = values[:i]

        history.append(
            ema(subset, 12)
            -
            ema(subset, 26)
        )

    signal = ema(history, 9)

    histogram = line - signal

    return line, signal, histogram


def bollinger(values, period=20):

    if len(values) < period:
        value = values[-1]
        return value, value, value

    window = values[-period:]

    middle = sum(window) / period

    variance = sum(
        (x - middle) ** 2
        for x in window
    ) / period

    deviation = math.sqrt(variance)

    return (
        middle + deviation * 2,
        middle,
        middle - deviation * 2,
    )


def atr(highs, lows, closes, period=14):

    if len(closes) < period + 1:
        return 0

    ranges = []

    for i in range(1, len(closes)):

        ranges.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    return sum(ranges[-period:]) / period


# ============================================================
# MARKET DATA
# ============================================================

def get_data(symbol, timeframe):

    key = symbol + ":" + timeframe

    now = time.time()

    with cache_lock:

        if key in cache:

            item = cache[key]

            if now - item["time"] < CACHE_SECONDS:
                return item["data"]

    config = TIMEFRAMES[timeframe]

    ticker = yf.Ticker(symbol)

    df = ticker.history(
        period=config["period"],
        interval=config["interval"],
        auto_adjust=False,
        prepost=False,
    )

    if df is None or df.empty:
        raise RuntimeError(
            "No market data returned."
        )

    df = df.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )

    if len(df) < 35:
        raise RuntimeError(
            "Not enough candles."
        )

    opens = [
        float(x)
        for x in df["Open"].tolist()
    ]

    highs = [
        float(x)
        for x in df["High"].tolist()
    ]

    lows = [
        float(x)
        for x in df["Low"].tolist()
    ]

    closes = [
        float(x)
        for x in df["Close"].tolist()
    ]

    timestamps = [
        str(x)
        for x in df.index.tolist()
    ]

    data = {
        "open": opens[-150:],
        "high": highs[-150:],
        "low": lows[-150:],
        "close": closes[-150:],
        "timestamps": timestamps[-150:],
    }

    with cache_lock:

        cache[key] = {
            "time": now,
            "data": data,
        }

    return data


# ============================================================
# RYU SIGNAL ENGINE
# ============================================================

def analyze(data):

    closes = data["close"]
    highs = data["high"]
    lows = data["low"]

    price = closes[-1]

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)

    rsi_value = rsi(closes)

    macd_line, macd_signal, macd_hist = macd(
        closes
    )

    upper, middle, lower = bollinger(
        closes
    )

    atr_value = atr(
        highs,
        lows,
        closes
    )

    score = 0
    reasons = []

    # EMA trend
    if ema9 > ema21:

        score += 2

        reasons.append(
            "Short-term trend bullish"
        )

    elif ema9 < ema21:

        score -= 2

        reasons.append(
            "Short-term trend bearish"
        )

    # Major trend
    if ema21 > ema50:

        score += 2

        reasons.append(
            "Major trend bullish"
        )

    elif ema21 < ema50:

        score -= 2

        reasons.append(
            "Major trend bearish"
        )

    # RSI
    if 50 <= rsi_value <= 68:

        score += 1

        reasons.append(
            "RSI supports CALL"
        )

    elif 32 <= rsi_value < 50:

        score -= 1

        reasons.append(
            "RSI supports PUT"
        )

    if rsi_value > 75:

        score -= 1

        reasons.append(
            "RSI overbought"
        )

    elif rsi_value < 25:

        score += 1

        reasons.append(
            "RSI oversold"
        )

    # MACD
    if macd_hist > 0:

        score += 2

        reasons.append(
            "MACD bullish momentum"
        )

    elif macd_hist < 0:

        score -= 2

        reasons.append(
            "MACD bearish momentum"
        )

    # Price vs Bollinger midpoint
    if price > middle:

        score += 1

        reasons.append(
            "Price above Bollinger midpoint"
        )

    elif price < middle:

        score -= 1

        reasons.append(
            "Price below Bollinger midpoint"
        )

    # Latest candle
    if closes[-1] > closes[-2]:

        score += 1

        reasons.append(
            "Latest candle bullish"
        )

    elif closes[-1] < closes[-2]:

        score -= 1

        reasons.append(
            "Latest candle bearish"
        )

    if score >= 5:

        direction = "CALL"

    elif score <= -5:

        direction = "PUT"

    else:

        direction = "WAIT"

    maximum = 11

    raw_confidence = (
        abs(score) / maximum
    )

    confidence = 50 + (
        raw_confidence * 45
    )

    if direction == "WAIT":
        confidence = min(
            confidence,
            69
        )

    confidence = round(
        max(
            50,
            min(
                95,
                confidence
            )
        )
    )

    if confidence >= 85:
        risk = "LOW"

    elif confidence >= 75:
        risk = "MEDIUM"

    else:
        risk = "HIGH"

    if score >= 3:
        trend = "BULLISH"

    elif score <= -3:
        trend = "BEARISH"

    else:
        trend = "NEUTRAL"

    return {

        "direction": direction,

        "confidence": confidence,

        "score": score,

        "max_score": maximum,

        "risk": risk,

        "trend": trend,

        "entry": round(
            price,
            8
        ),

        "rsi": round(
            rsi_value,
            2
        ),

        "ema9": round(
            ema9,
            8
        ),

        "ema21": round(
            ema21,
            8
        ),

        "ema50": round(
            ema50,
            8
        ),

        "macd": round(
            macd_line,
            8
        ),

        "macd_signal": round(
            macd_signal,
            8
        ),

        "macd_histogram": round(
            macd_hist,
            8
        ),

        "bollinger_upper": round(
            upper,
            8
        ),

        "bollinger_middle": round(
            middle,
            8
        ),

        "bollinger_lower": round(
            lower,
            8
        ),

        "atr": round(
            atr_value,
            8
        ),

        "reasons": reasons[:6],

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }


# ============================================================
# BUILD SIGNAL
# ============================================================

def build_signal(
    market,
    asset,
    timeframe
):

    if market not in MARKETS:

        raise ValueError(
            "Invalid market."
        )

    if asset not in MARKETS[market]:

        raise ValueError(
            "Invalid asset."
        )

    if timeframe not in TIMEFRAMES:

        raise ValueError(
            "Invalid timeframe."
        )

    symbol = MARKETS[
        market
    ][asset]

    data = get_data(
        symbol,
        timeframe
    )

    result = analyze(data)

    result.update({

        "market": market,

        "asset": asset,

        "symbol": symbol,

        "timeframe": timeframe,

        "chart": {

            "timestamps":
                data["timestamps"],

            "open":
                data["open"],

            "high":
                data["high"],

            "low":
                data["low"],

            "close":
                data["close"],
        },
    })

    return result


# ============================================================
# API
# ============================================================

@app.route("/health")
def health():

    return jsonify({

        "status": "online",

        "engine": "RYU V2",

        "markets": [
            "forex",
            "crypto",
            "stocks",
            "otc",
        ],

        "time":
            datetime.now(
                timezone.utc
            ).isoformat(),
    })


@app.route("/api/markets")
def api_markets():

    return jsonify(MARKETS)


@app.route("/api/search")
def api_search():

    query = (
        request.args
        .get("q", "")
        .strip()
        .lower()
    )

    market = (
        request.args
        .get("market", "forex")
        .lower()
    )

    if market not in MARKETS:
        return jsonify([])

    results = []

    for name, symbol in MARKETS[
        market
    ].items():

        if (
            query in name.lower()
            or query in symbol.lower()
        ):

            results.append({

                "name": name,

                "symbol": symbol,
            })

    return jsonify(
        results[:100]
    )


@app.route("/api/signal")
def api_signal():

    market = request.args.get(
        "market",
        "forex"
    )

    asset = request.args.get(
        "asset",
        "EUR/USD"
    )

    timeframe = request.args.get(
        "timeframe",
        "1m"
    )

    try:

        result = build_signal(
            market,
            asset,
            timeframe
        )

        return jsonify(result)

    except Exception as exc:

        return jsonify({

            "error": str(exc),

            "market": market,

            "asset": asset,

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

<meta
name="viewport"
content="width=device-width,initial-scale=1"
>

<title>RYU V2</title>

<style>

*{
box-sizing:border-box;
}

body{
margin:0;
background:#070a10;
color:#f4f7fb;
font-family:Arial,Helvetica,sans-serif;
}

.header{
height:70px;
display:flex;
align-items:center;
justify-content:space-between;
padding:0 22px;
background:#0b0f17;
border-bottom:1px solid #1d2635;
}

.logo{
font-size:27px;
font-weight:900;
letter-spacing:2px;
}

.logo span{
color:#54ddff;
}

.online{
color:#58e6a5;
font-size:12px;
}

.dot{
display:inline-block;
width:8px;
height:8px;
background:#58e6a5;
border-radius:50%;
margin-right:6px;
}

.layout{
display:flex;
min-height:calc(100vh - 70px);
}

.sidebar{
width:210px;
background:#090d14;
border-right:1px solid #1d2635;
padding:20px 13px;
}

.nav{
padding:14px;
margin-bottom:7px;
border-radius:9px;
color:#8994a7;
}

.nav.active,
.nav:hover{
background:#151c28;
color:white;
}

.main{
flex:1;
padding:22px;
max-width:1600px;
margin:auto;
}

.top{
display:flex;
justify-content:space-between;
align-items:flex-start;
gap:15px;
margin-bottom:18px;
}

h1{
margin:0;
font-size:25px;
}

.small{
font-size:12px;
color:#7f8a9e;
}

.market-tabs{
display:flex;
gap:7px;
flex-wrap:wrap;
}

button{
border:1px solid #293446;
background:#111722;
color:#cbd3df;
padding:9px 14px;
border-radius:8px;
cursor:pointer;
}

button.active{
background:#54ddff;
color:#061017;
border-color:#54ddff;
font-weight:bold;
}

.selector{
display:grid;
grid-template-columns:1fr auto auto;
gap:8px;
margin-bottom:16px;
}

input,
select{
width:100%;
background:#0d121b;
border:1px solid #293446;
color:white;
padding:12px;
border-radius:9px;
outline:none;
}

.asset-list{
max-height:0;
overflow:hidden;
transition:.2s;
}

.asset-list.open{
max-height:300px;
overflow-y:auto;
}

.asset-option{
padding:10px;
background:#101620;
border-bottom:1px solid #1d2635;
cursor:pointer;
}

.asset-option:hover{
background:#17202d;
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
padding:17px;
}

.label{
font-size:11px;
color:#7f8a9e;
text-transform:uppercase;
letter-spacing:1px;
}

.value{
font-size:26px;
font-weight:900;
margin-top:7px;
}

.green{
color:#58e6a5;
}

.red{
color:#ff637c;
}

.blue{
color:#54ddff;
}

.signal-grid{
display:grid;
grid-template-columns:1.3fr 1fr 1fr 1fr;
gap:13px;
margin-top:14px;
}

.signal-card{
min-height:235px;
}

.pair{
font-size:20px;
font-weight:900;
}

.direction{
font-size:48px;
font-weight:900;
margin:17px 0;
}

.meta{
display:flex;
justify-content:space-between;
padding:10px 0;
border-bottom:1px solid #1d2635;
}

.reason{
margin-top:8px;
padding:8px;
background:#111722;
border-radius:7px;
font-size:12px;
color:#abb5c5;
}

.chart{
height:370px;
margin-top:15px;
}

canvas{
width:100%;
height:100%;
}

table{
width:100%;
border-collapse:collapse;
margin-top:10px;
}

th,
td{
padding:12px 7px;
border-bottom:1px solid #1d2635;
text-align:left;
}

th{
font-size:10px;
color:#7f8a9e;
}

.footer{
font-size:11px;
color:#5f6a7c;
margin-top:16px;
}

.error{
color:#ff637c;
font-size:12px;
margin-top:8px;
}

@media(max-width:1050px){

.grid{
grid-template-columns:repeat(2,1fr);
}

.signal-grid{
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
}

.selector{
grid-template-columns:1fr;
}

.grid{
grid-template-columns:1fr 1fr;
}

.signal-grid{
grid-template-columns:1fr 1fr;
}

}

</style>

</head>

<body>

<header class="header">

<div class="logo">
RYU <span>V2</span>
</div>

<div class="online">
<span class="dot"></span>
<span id="status">ENGINE ONLINE</span>
</div>

</header>

<div class="layout">

<aside class="sidebar">

<div class="nav active">
◈ Signals
</div>

<div class="nav">
▣ Trades
</div>

<div class="nav">
◒ Performance
</div>

<div class="nav">
⚙ Settings
</div>

</aside>

<main class="main">

<div class="top">

<div>

<h1>
RYU V2 Trading Engine
</h1>

<div class="small">
Forex • Crypto • Stocks • OTC
</div>

</div>

<div class="market-tabs">

<button
class="market active"
data-market="forex"
>
Forex
</button>

<button
class="market"
data-market="crypto"
>
Crypto
</button>

<button
class="market"
data-market="stocks"
>
Stocks
</button>

<button
class="market"
data-market="otc"
>
OTC
</button>

</div>

</div>


<div class="selector">

<div>

<input
id="search"
placeholder="Search asset..."
autocomplete="off"
>

<div
id="assetList"
class="asset-list"
></div>

</div>

<select id="asset"></select>

<div style="display:flex;gap:5px">

<button class="tf active"
data-tf="1m"
>
1m
</button>

<button class="tf"
data-tf="2m"
>
2m
</button>

<button class="tf"
data-tf="3m"
>
3m
</button>

</div>

</div>


<section class="grid">

<div class="card">

<div class="label">
Selected Market
</div>

<div
class="value blue"
id="marketValue"
>
Forex
</div>

</div>


<div class="card">

<div class="label">
Asset
</div>

<div
class="value"
id="assetValue"
>
EUR/USD
</div>

</div>


<div class="card">

<div class="label">
RYU Signal
</div>

<div
class="value blue"
id="signal"
>
WAIT
</div>

</div>


<div class="card">

<div class="label">
Confidence
</div>

<div
class="value"
id="confidence"
>
--
</div>

</div>

</section>


<section class="signal-grid">


<div class="card signal-card">

<div
class="pair"
id="pair"
>
EUR/USD
</div>

<div class="small">
RYU V2 Decision
</div>

<div
class="direction blue"
id="direction"
>
WAIT
</div>

<div class="meta">

<span class="small">
Entry
</span>

<span id="entry">
--
</span>

</div>

<div class="meta">

<span class="small">
Risk
</span>

<span id="risk">
--
</span>

</div>

</div>


<div class="card signal-card">

<div class="label">
Trend
</div>

<div
class="value"
id="trend"
>
--
</div>

<div class="meta">
<span class="small">
EMA 9
</span>
<span id="ema9">
--
</span>
</div>

<div class="meta">
<span class="small">
EMA 21
</span>
<span id="ema21">
--
</span>
</div>

<div class="meta">
<span class="small">
EMA 50
</span>
<span id="ema50">
--
</span>
</div>

</div>


<div class="card signal-card">

<div class="label">
Momentum
</div>

<div
class="value blue"
id="rsi"
>
--
</div>

<div class="small">
RSI
</div>

<div class="meta">

<span class="small">
MACD
</span>

<span id="macd">
--
</span>

</div>

<div class="meta">

<span class="small">
Histogram
</span>

<span id="hist">
--
</span>

</div>

</div>


<div class="card signal-card">

<div class="label">
Confluence
</div>

<div
class="value"
id="score"
>
--
</div>

<div id="reasons">
</div>

</div>

</section>


<div class="card" style="margin-top:14px">

<div style="display:flex;justify-content:space-between">

<div>

<div
class="pair"
id="chartTitle"
>
EUR/USD
</div>

<div class="small">
Live market chart
</div>

</div>

<div class="green">
● LIVE
</div>

</div>

<div class="chart">

<canvas id="chart"></canvas>

</div>

<div
id="error"
class="error"
>
</div>

</div>


<div class="card" style="margin-top:14px">

<div class="pair">
RYU V2 Analysis
</div>

<table>

<thead>

<tr>

<th>
INDICATOR
</th>

<th>
VALUE
</th>

<th>
READING
</th>

</tr>

</thead>

<tbody>

<tr>

<td>
RSI
</td>

<td id="tRsi">
--
</td>

<td id="tRsiRead">
--
</td>

</tr>

<tr>

<td>
EMA
</td>

<td id="tEma">
--
</td>

<td id="tEmaRead">
--
</td>

</tr>

<tr>

<td>
MACD
</td>

<td id="tMacd">
--
</td>

<td id="tMacdRead">
--
</td>

</tr>

<tr>

<td>
Bollinger
</td>

<td id="tBb">
--
</td>

<td id="tBbRead">
--
</td>

</tr>

<tr>

<td>
RYU Decision
</td>

<td id="tDecision">
--
</td>

<td id="tDecisionRead">
--
</td>

</tr>

</tbody>

</table>

</div>


<div class="footer">

RYU V2 •
Market data engine •
Last update:
<span id="updated">
--
</span>

</div>

</main>

</div>


<script>

let market = "forex";
let timeframe = "1m";
let asset = "EUR/USD";
let currentData = null;

const assetSelect =
document.getElementById("asset");

const search =
document.getElementById("search");

const assetList =
document.getElementById("assetList");


function color(el, value){

el.classList.remove(
"green",
"red",
"blue"
);

if(
value === "CALL" ||
value === "BULLISH"
){

el.classList.add(
"green"
);

}

else if(
value === "PUT" ||
value === "BEARISH"
){

el.classList.add(
"red"
);

}

else{

el.classList.add(
"blue"
);

}

}


async function loadAssets(){

const response =
await fetch(
"/api/markets"
);

const markets =
await response.json();

const assets =
Object.keys(
markets[market]
);

assetSelect.innerHTML = "";

assets.forEach(name => {

const option =
document.createElement(
"option"
);

option.value = name;

option.textContent = name;

assetSelect.appendChild(
option
);

});

if(
assets.includes(asset)
){

assetSelect.value =
asset;

}

else{

asset =
assets[0];

assetSelect.value =
asset;

}

}


function showSearchResults(){

const query =
search.value
.toLowerCase()
.trim();

assetList.innerHTML = "";

if(!query){

assetList.classList.remove(
"open"
);

return;

}

const options =
Array.from(
assetSelect.options
);

const matches =
options.filter(
option =>
option.textContent
.toLowerCase()
.includes(query)
);

matches.slice(0,40).forEach(
option => {

const div =
document.createElement(
"div"
);

div.className =
"asset-option";

div.textContent =
option.textContent;

div.onclick = () => {

asset =
option.value;

assetSelect.value =
asset;

search.value =
asset;

assetList.classList.remove(
"open"
);

loadSignal();

};

assetList.appendChild(
div
);

});

assetList.classList.add(
"open"
);

}


async function loadSignal(){

document.getElementById(
"error"
).textContent = "";

try{

const response =
await fetch(
"/api/signal?market=" +
encodeURIComponent(market) +
"&asset=" +
encodeURIComponent(asset) +
"&timeframe=" +
encodeURIComponent(timeframe)
);

const data =
await response.json();

if(!response.ok){

throw new Error(
data.error ||
"Market data unavailable"
);

}

currentData = data;

update(data);

}

catch(error){

document.getElementById(
"error"
).textContent =
"Market data error: " +
error.message;

document.getElementById(
"status"
).textContent =
"DATA RETRYING";

}

}


function update(data){

document.getElementById(
"marketValue"
).textContent =
market.toUpperCase();

document.getElementById(
"assetValue"
).textContent =
data.asset;

document.getElementById(
"pair"
).textContent =
data.asset;

document.getElementById(
"chartTitle"
).textContent =
data.asset;

document.getElementById(
"signal"
).textContent =
data.direction;

document.getElementById(
"confidence"
).textContent =
data.confidence + "%";

document.getElementById(
"direction"
).textContent =
data.direction;

document.getElementById(
"entry"
).textContent =
data.entry;

document.getElementById(
"risk"
).textContent =
data.risk;

document.getElementById(
"trend"
).textContent =
data.trend;

document.getElementById(
"rsi"
).textContent =
data.rsi;

document.getElementById(
"ema9"
).textContent =
data.ema9;

document.getElementById(
"ema21"
).textContent =
data.ema21;

document.getElementById(
"ema50"
).textContent =
data.ema50;

document.getElementById(
"macd"
).textContent =
data.macd;

document.getElementById(
"hist"
).textContent =
data.macd_histogram;

document.getElementById(
"score"
).textContent =
Math.abs(data.score)
+ " / "
+ data.max_score;

color(
document.getElementById("signal"),
data.direction
);

color(
document.getElementById("direction"),
data.direction
);

color(
document.getElementById("trend"),
data.trend
);


const reasons =
document.getElementById(
"reasons"
);

reasons.innerHTML = "";

data.reasons.forEach(
reason => {

const div =
document.createElement(
"div"
);

div.className =
"reason";

div.textContent =
"✓ " + reason;

reasons.appendChild(
div
);

});


document.getElementById(
"tRsi"
).textContent =
data.rsi;

document.getElementById(
"tRsiRead"
).textContent =
data.rsi > 70
? "OVERBOUGHT"
: data.rsi < 30
? "OVERSOLD"
: data.rsi >= 50
? "BULLISH"
: "BEARISH";


document.getElementById(
"tEma"
).textContent =
data.ema9
+ " / "
+ data.ema21;

document.getElementById(
"tEmaRead"
).textContent =
data.ema9 > data.ema21
? "BULLISH"
: "BEARISH";


document.getElementById(
"tMacd"
).textContent =
data.macd;

document.getElementById(
"tMacdRead"
).textContent =
data.macd_histogram > 0
? "POSITIVE"
: "NEGATIVE";


document.getElementById(
"tBb"
).textContent =
data.bollinger_middle;

document.getElementById(
"tBbRead"
).textContent =
data.entry >
data.bollinger_middle
? "ABOVE MIDLINE"
: "BELOW MIDLINE";


document.getElementById(
"tDecision"
).textContent =
data.direction;

document.getElementById(
"tDecisionRead"
).textContent =
data.confidence
+ "% CONFIDENCE";


document.getElementById(
"updated"
).textContent =
new Date().toLocaleTimeString();

document.getElementById(
"status"
).textContent =
"ENGINE ONLINE";

drawChart(
data.chart
);

}


function drawChart(chart){

const canvas =
document.getElementById(
"chart"
);

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
dpr,
0,
0,
dpr,
0,
0
);

const w =
rect.width;

const h =
rect.height;

ctx.clearRect(
0,
0,
w,
h
);

const prices =
chart.close;

if(!prices ||
prices.length < 2){

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


ctx.strokeStyle =
"#1c2635";

ctx.lineWidth = 1;


for(
let i=1;
i<6;
i++
){

const y =
(h/6)*i;

ctx.beginPath();

ctx.moveTo(
0,
y
);

ctx.lineTo(
w,
y
);

ctx.stroke();

}


ctx.beginPath();

prices.forEach(
(price,i) => {

const x =
(i/(prices.length-1))
* w;

const y =
h -
(
(price-min)
/
range
)
*
(h-30)
-15;

if(i===0){

ctx.moveTo(
x,
y
);

}

else{

ctx.lineTo(
x,
y
);

}

});


ctx.strokeStyle =
"#54ddff";

ctx.lineWidth = 2;

ctx.stroke();


const last =
prices[
prices.length-1
];

const y =
h -
(
(last-min)
/
range
)
*
(h-30)
-15;


ctx.beginPath();

ctx.arc(
w,
y,
5,
0,
Math.PI*2
);

ctx.fillStyle =
"#58e6a5";

ctx.fill();

}


document.querySelectorAll(
".market"
).forEach(
button => {

button.onclick =
async () => {

document.querySelectorAll(
".market"
).forEach(
b =>
b.classList.remove(
"active"
)
);

button.classList.add(
"active"
);

market =
button.dataset.market;

await loadAssets();

await loadSignal();

};

});


document.querySelectorAll(
".tf"
).forEach(
button => {

button.onclick =
async () => {

document.querySelectorAll(
".tf"
).forEach(
b =>
b.classList.remove(
"active"
)
);

button.classList.add(
"active"
);

timeframe =
button.dataset.tf;

await loadSignal();

};

});


assetSelect.onchange =
() => {

asset =
assetSelect.value;

loadSignal();

};


search.oninput =
showSearchResults;


window.onresize =
() => {

if(currentData){

drawChart(
currentData.chart
);

}

};


async function start(){

await loadAssets();

await loadSignal();

setInterval(
loadSignal,
30000
);

}


start();

</script>

</body>

</html>
"""


@app.route("/")
def home():
    return render_template_string(
        HTML
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
)
