import os
import math
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template_string

# ============================================================
# RYU V2 - POCKET OPTION LIVE SIGNAL DASHBOARD
# ============================================================
#
# IMPORTANT:
# This application is SIGNAL-ONLY.
# It does not automatically place Pocket Option trades.
#
# Pocket Option live data must be supplied through the
# /api/feed endpoint by an authorized live-feed connector.
#
# Environment variables:
#
#   RYU_FEED_TOKEN = secret token used by your feed connector
#   RYU_DEFAULT_ASSET = EURUSD_otc
#   RYU_EXPIRY_SECONDS = 300
#
# Optional:
#   RYU_MIN_CONFIDENCE = 78
#
# ============================================================

app = Flask(__name__)

# -----------------------------
# Configuration
# -----------------------------

FEED_TOKEN = os.getenv("RYU_FEED_TOKEN", "")
DEFAULT_ASSET = os.getenv("RYU_DEFAULT_ASSET", "EURUSD_otc")
EXPIRY_SECONDS = int(os.getenv("RYU_EXPIRY_SECONDS", "300"))
MIN_CONFIDENCE = float(os.getenv("RYU_MIN_CONFIDENCE", "78"))

MAX_CANDLES = 500

TIMEFRAMES = {
    "1m": 60,
    "2m": 120,
    "3m": 180,
    "5m": 300,
}

# -----------------------------
# Runtime state
# -----------------------------

lock = threading.RLock()

assets = defaultdict(lambda: {
    "candles": deque(maxlen=MAX_CANDLES),
    "price": None,
    "payout": None,
    "last_tick": None,
    "signal": "WAIT",
    "confidence": 0,
    "entry": None,
    "signal_time": None,
    "expiry": EXPIRY_SECONDS,
    "timeframe": "1m",
})

selected_asset = DEFAULT_ASSET
selected_timeframe = "1m"

signal_history = deque(maxlen=100)
trade_history = deque(maxlen=100)

feed_status = {
    "connected": False,
    "last_update": None,
    "source": "Pocket Option",
    "message": "Waiting for live Pocket Option feed",
}


# ============================================================
# Utility functions
# ============================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clamp(value, low, high):
    return max(low, min(high, value))


def clean_number(value):
    try:
        return float(value)
    except Exception:
        return None


def authorized(req):
    if not FEED_TOKEN:
        return True

    supplied = (
        req.headers.get("X-RYU-FEED-TOKEN")
        or req.args.get("token")
        or (
            req.json.get("token")
            if request.is_json and isinstance(req.json, dict)
            else None
        )
    )

    return supplied == FEED_TOKEN


# ============================================================
# Candle normalization
# ============================================================

def normalize_candle(raw):
    """
    Accepts common OHLC formats.

    Example:
    {
        "timestamp": 1760000000,
        "open": 1.1000,
        "high": 1.1010,
        "low": 1.0990,
        "close": 1.1005,
        "volume": 0
    }
    """

    if not isinstance(raw, dict):
        return None

    ts = raw.get("timestamp", raw.get("time", raw.get("at")))

    try:
        ts = float(ts)
    except Exception:
        ts = time.time()

    # Convert milliseconds
    if ts > 10_000_000_000:
        ts /= 1000.0

    o = clean_number(raw.get("open", raw.get("o")))
    h = clean_number(raw.get("high", raw.get("h")))
    l = clean_number(raw.get("low", raw.get("l")))
    c = clean_number(raw.get("close", raw.get("c")))

    if None in (o, h, l, c):
        return None

    return {
        "timestamp": ts,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": clean_number(raw.get("volume", raw.get("v"))) or 0,
    }


def add_candle(asset, candle, payout=None):
    candle = normalize_candle(candle)

    if candle is None:
        return False

    with lock:
        state = assets[asset]
        candles = state["candles"]

        # Replace the currently forming candle when timestamps match.
        if candles and int(candles[-1]["timestamp"]) == int(candle["timestamp"]):
            candles[-1] = candle
        else:
            candles.append(candle)

        state["price"] = candle["close"]
        state["last_tick"] = time.time()

        if payout is not None:
            state["payout"] = clean_number(payout)

        feed_status["connected"] = True
        feed_status["last_update"] = now_iso()
        feed_status["message"] = "Live Pocket Option data received"

    return True


# ============================================================
# Technical calculations
# ============================================================

def closes(candles):
    return [x["close"] for x in candles]


def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2.0 / (period + 1.0)

    value = sum(values[:period]) / period

    for price in values[period:]:
        value = ((price - value) * multiplier) + value

    return value


def sma(values, period):
    if len(values) < period:
        return None

    return sum(values[-period:]) / period


def stddev(values, period):
    if len(values) < period:
        return None

    subset = values[-period:]
    mean = sum(subset) / period

    variance = sum((x - mean) ** 2 for x in subset) / period

    return math.sqrt(variance)


def rsi(values, period=14):
    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(len(values) - period, len(values)):
        change = values[i] - values[i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100.0 - (100.0 / (1.0 + rs))


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None

    trs = []

    for i in range(len(candles) - period, len(candles)):
        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"] - current["low"],
            abs(current["high"] - previous["close"]),
            abs(current["low"] - previous["close"]),
        )

        trs.append(tr)

    return sum(trs) / len(trs)


def macd(values):
    e12 = ema(values, 12)
    e26 = ema(values, 26)

    if e12 is None or e26 is None:
        return None, None

    line = e12 - e26

    # Approximate signal line from historical MACD values.
    macd_values = []

    for i in range(26, len(values) + 1):
        segment = values[:i]
        a = ema(segment, 12)
        b = ema(segment, 26)

        if a is not None and b is not None:
            macd_values.append(a - b)

    if len(macd_values) < 9:
        return line, None

    signal = ema(macd_values, 9)

    return line, signal


# ============================================================
# Alligator
# ============================================================

def alligator(values):
    """
    Simplified SMMA-style Alligator components.

    Jaw:   13
    Teeth: 8
    Lips:  5

    This is used as a trend/confluence filter.
    """

    if len(values) < 20:
        return None

    jaw = sma(values, 13)
    teeth = sma(values, 8)
    lips = sma(values, 5)

    if None in (jaw, teeth, lips):
        return None

    return {
        "jaw": jaw,
        "teeth": teeth,
        "lips": lips,
    }


# ============================================================
# RYU signal engine
# ============================================================

def analyze(asset, timeframe="1m"):
    with lock:
        candles = list(assets[asset]["candles"])
        payout = assets[asset]["payout"]

    if len(candles) < 60:
        return {
            "signal": "WAIT",
            "confidence": 0,
            "reason": "Waiting for at least 60 live candles",
            "asset": asset,
            "timeframe": timeframe,
            "price": assets[asset]["price"],
            "payout": payout,
        }

    values = closes(candles)

    price = values[-1]

    ema9 = ema(values, 9)
    ema20 = ema(values, 20)
    ema50 = ema(values, 50)

    rsi_value = rsi(values)

    macd_line, macd_signal = macd(values)

    bb_mid = sma(values, 20)
    bb_std = stddev(values, 20)

    alligator_data = alligator(values)

    atr_value = atr(candles)

    if None in (
        ema9,
        ema20,
        ema50,
        rsi_value,
        bb_mid,
        bb_std,
        alligator_data,
        atr_value,
    ):
        return {
            "signal": "WAIT",
            "confidence": 0,
            "reason": "Building technical history",
            "asset": asset,
            "timeframe": timeframe,
            "price": price,
            "payout": payout,
        }

    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    score_call = 0
    score_put = 0

    reasons_call = []
    reasons_put = []

    # -------------------------
    # EMA trend
    # -------------------------

    if ema9 > ema20 > ema50:
        score_call += 2
        reasons_call.append("EMA bullish alignment")

    elif ema9 < ema20 < ema50:
        score_put += 2
        reasons_put.append("EMA bearish alignment")

    # -------------------------
    # Alligator
    # -------------------------

    jaw = alligator_data["jaw"]
    teeth = alligator_data["teeth"]
    lips = alligator_data["lips"]

    if lips > teeth > jaw:
        score_call += 2
        reasons_call.append("Alligator bullish")

    elif lips < teeth < jaw:
        score_put += 2
        reasons_put.append("Alligator bearish")

    # -------------------------
    # MACD
    # -------------------------

    if macd_line is not None and macd_signal is not None:

        if macd_line > macd_signal and macd_line > 0:
            score_call += 2
            reasons_call.append("MACD bullish")

        elif macd_line < macd_signal and macd_line < 0:
            score_put += 2
            reasons_put.append("MACD bearish")

    # -------------------------
    # RSI
    # -------------------------

    if 50 <= rsi_value <= 68:
        score_call += 1
        reasons_call.append("RSI bullish zone")

    elif 32 <= rsi_value <= 50:
        score_put += 1
        reasons_put.append("RSI bearish zone")

    # -------------------------
    # Bollinger
    # -------------------------

    if price > bb_mid and price < bb_upper:
        score_call += 1
        reasons_call.append("Price above BB midpoint")

    elif price < bb_mid and price > bb_lower:
        score_put += 1
        reasons_put.append("Price below BB midpoint")

    # -------------------------
    # Price action
    # -------------------------

    last = candles[-1]
    previous = candles[-2]

    current_body = last["close"] - last["open"]
    previous_body = previous["close"] - previous["open"]

    if current_body > 0 and last["close"] > previous["close"]:
        score_call += 1
        reasons_call.append("Bullish price action")

    elif current_body < 0 and last["close"] < previous["close"]:
        score_put += 1
        reasons_put.append("Bearish price action")

    # -------------------------
    # Momentum
    # -------------------------

    if len(values) >= 6:

        momentum = price - values[-6]

        if momentum > 0:
            score_call += 1
            reasons_call.append("Positive momentum")

        elif momentum < 0:
            score_put += 1
            reasons_put.append("Negative momentum")

    max_score = 10

    if score_call > score_put:
        side = "CALL"
        score = score_call
        reasons = reasons_call

    elif score_put > score_call:
        side = "PUT"
        score = score_put
        reasons = reasons_put

    else:
        side = "WAIT"
        score = 0
        reasons = ["Conflicting technical conditions"]

    confidence = round(clamp((score / max_score) * 100, 0, 99), 1)

    # Don't manufacture high-confidence signals.
    if confidence < MIN_CONFIDENCE:
        side = "WAIT"

    return {
        "signal": side,
        "confidence": confidence,
        "score": score,
        "max_score": max_score,
        "asset": asset,
        "timeframe": timeframe,
        "price": price,
        "payout": payout,
        "entry": price if side != "WAIT" else None,
        "expiry_seconds": EXPIRY_SECONDS,
        "reasons": reasons,
        "indicators": {
            "ema9": ema9,
            "ema20": ema20,
            "ema50": ema50,
            "rsi": rsi_value,
            "macd": macd_line,
            "macd_signal": macd_signal,
            "bb_upper": bb_upper,
            "bb_mid": bb_mid,
            "bb_lower": bb_lower,
            "alligator_jaw": jaw,
            "alligator_teeth": teeth,
            "alligator_lips": lips,
            "atr": atr_value,
        },
        "timestamp": now_iso(),
    }


# ============================================================
# Signal generation
# ============================================================

def generate_signal(asset, timeframe):
    result = analyze(asset, timeframe)

    if result["signal"] != "WAIT":

        signal_history.appendleft({
            "time": now_iso(),
            "asset": asset,
            "timeframe": timeframe,
            "signal": result["signal"],
            "confidence": result["confidence"],
            "entry": result["entry"],
            "payout": result["payout"],
        })

    return result


# ============================================================
# Feed API
# ============================================================

@app.post("/api/feed")
def feed():

    if not authorized(request):
        return jsonify({
            "ok": False,
            "error": "Unauthorized feed connection"
        }), 401

    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        return jsonify({
            "ok": False,
            "error": "JSON body required"
        }), 400

    asset = body.get("asset")

    if not asset:
        return jsonify({
            "ok": False,
            "error": "asset required"
        }), 400

    payout = body.get("payout")

    accepted = 0

    candles = body.get("candles")

    if isinstance(candles, list):

        for candle in candles:

            if add_candle(asset, candle, payout):
                accepted += 1

    candle = body.get("candle")

    if isinstance(candle, dict):

        if add_candle(asset, candle, payout):
            accepted += 1

    # Optional tick-only update
    price = clean_number(body.get("price"))

    if price is not None:

        with lock:

            assets[asset]["price"] = price
            assets[asset]["last_tick"] = time.time()

            feed_status["connected"] = True
            feed_status["last_update"] = now_iso()
            feed_status["message"] = "Live Pocket Option tick received"

    return jsonify({
        "ok": True,
        "accepted": accepted,
        "asset": asset,
        "candles_available": len(assets[asset]["candles"]),
    })


# ============================================================
# Signal API
# ============================================================

@app.get("/api/signal")
def api_signal():

    asset = request.args.get("asset", selected_asset)
    timeframe = request.args.get("timeframe", selected_timeframe)

    if timeframe not in TIMEFRAMES:
        timeframe = "1m"

    result = analyze(asset, timeframe)

    return jsonify(result)


# ============================================================
# Select asset
# ============================================================

@app.post("/api/select")
def select_asset():

    global selected_asset
    global selected_timeframe

    body = request.get_json(silent=True) or {}

    asset = body.get("asset")

    timeframe = body.get("timeframe", "1m")

    if asset:
        selected_asset = asset

    if timeframe in TIMEFRAMES:
        selected_timeframe = timeframe

    return jsonify({
        "ok": True,
        "asset": selected_asset,
        "timeframe": selected_timeframe,
    })


# ============================================================
# Dashboard state
# ============================================================

@app.get("/api/state")
def state():

    with lock:

        result_assets = {}

        for name, data in assets.items():

            result_assets[name] = {
                "price": data["price"],
                "payout": data["payout"],
                "candles": len(data["candles"]),
                "last_tick": data["last_tick"],
            }

    signal = analyze(
        selected_asset,
        selected_timeframe
    )

    return jsonify({
        "ok": True,
        "feed": feed_status,
        "selected_asset": selected_asset,
        "selected_timeframe": selected_timeframe,
        "expiry_seconds": EXPIRY_SECONDS,
        "assets": result_assets,
        "signal": signal,
        "signal_history": list(signal_history),
        "trade_history": list(trade_history),
        "server_time": now_iso(),
    })


# ============================================================
# Record a manually executed demo trade
# ============================================================

@app.post("/api/trade")
def record_trade():

    body = request.get_json(silent=True) or {}

    record = {
        "time": now_iso(),
        "asset": body.get("asset", selected_asset),
        "direction": body.get("direction"),
        "entry": clean_number(body.get("entry")),
        "result": body.get("result"),
        "payout": clean_number(body.get("payout")),
        "amount": clean_number(body.get("amount")),
        "profit": clean_number(body.get("profit")),
    }

    trade_history.appendleft(record)

    return jsonify({
        "ok": True,
        "trade": record,
    })


# ============================================================
# Health check
# ============================================================

@app.get("/health")
def health():

    return jsonify({
        "status": "online",
        "ryu": "V2",
        "feed_connected": feed_status["connected"],
        "last_update": feed_status["last_update"],
        "message": feed_status["message"],
        "live_data_required": True,
    })


# ============================================================
# Dashboard
# ============================================================

HTML = r"""
<!doctype html>
<html>
<head>

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>RYU V2</title>

<style>

*{
    box-sizing:border-box;
}

body{
    margin:0;
    background:#05070b;
    color:#eef2f7;
    font-family:Arial,Helvetica,sans-serif;
}

.header{
    height:72px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 22px;
    background:#090c12;
    border-bottom:1px solid #202631;
}

.logo{
    font-size:28px;
    font-weight:900;
    letter-spacing:3px;
}

.logo span{
    color:#ff2f2f;
}

.status{
    display:flex;
    align-items:center;
    gap:8px;
    font-size:12px;
}

.dot{
    width:9px;
    height:9px;
    border-radius:50%;
    background:#ff3030;
}

.dot.live{
    background:#20e879;
    box-shadow:0 0 14px #20e879;
}

.layout{
    display:grid;
    grid-template-columns:250px 1fr 330px;
    min-height:calc(100vh - 72px);
}

.sidebar,
.right{
    background:#080b10;
    border-right:1px solid #202631;
}

.right{
    border-right:0;
    border-left:1px solid #202631;
}

.panel{
    padding:18px;
}

.section-title{
    color:#8993a3;
    font-size:11px;
    font-weight:bold;
    letter-spacing:1.4px;
    margin-bottom:12px;
}

.search{
    width:100%;
    background:#11151d;
    border:1px solid #282e38;
    color:white;
    border-radius:8px;
    padding:11px;
}

.filters{
    display:flex;
    gap:5px;
    margin:12px 0;
}

.filter{
    flex:1;
    background:#10141b;
    border:1px solid #272d37;
    color:#9da6b5;
    padding:8px 4px;
    border-radius:6px;
    font-size:11px;
}

.filter.active{
    color:white;
    border-color:#ff3b3b;
}

.asset{
    display:flex;
    justify-content:space-between;
    align-items:center;
    padding:12px 5px;
    border-bottom:1px solid #171c24;
    cursor:pointer;
}

.asset:hover{
    background:#10141b;
}

.asset-name{
    font-weight:bold;
    font-size:13px;
}

.asset-meta{
    color:#7e8998;
    font-size:10px;
    margin-top:3px;
}

.main{
    padding:20px;
}

.asset-header{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:14px;
}

.asset-title{
    font-size:24px;
    font-weight:900;
}

.price{
    font-size:24px;
    font-weight:bold;
}

.timeframes{
    display:flex;
    gap:5px;
    overflow-x:auto;
    margin-bottom:12px;
}

.tf{
    white-space:nowrap;
    background:#10141b;
    color:#a8b0bd;
    border:1px solid #292f39;
    border-radius:6px;
    padding:8px 12px;
}

.tf.active{
    background:#1a222d;
    border-color:#ff3b3b;
    color:white;
}

.chart{
    height:420px;
    background:
        linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),
        linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px),
        #080b10;
    background-size:40px 40px;
    border:1px solid #222832;
    border-radius:12px;
    display:flex;
    align-items:center;
    justify-content:center;
    position:relative;
    overflow:hidden;
}

.chart-message{
    text-align:center;
    color:#7e8998;
}

.chart-message strong{
    display:block;
    color:#e9edf4;
    font-size:20px;
    margin-bottom:8px;
}

.signal-box{
    margin-top:15px;
    border:1px solid #272e39;
    border-radius:14px;
    padding:20px;
    background:#0b0f15;
}

.signal-box.call{
    border-color:#1de879;
    box-shadow:0 0 35px rgba(29,232,121,.08);
}

.signal-box.put{
    border-color:#ff3434;
    box-shadow:0 0 35px rgba(255,52,52,.08);
}

.signal-box.wait{
    border-color:#626b78;
}

.signal-label{
    color:#8d97a5;
    font-size:11px;
    letter-spacing:1.5px;
}

.signal{
    font-size:44px;
    font-weight:1000;
    margin:8px 0;
}

.call .signal{
    color:#20ef7a;
}

.put .signal{
    color:#ff3e3e;
}

.confidence{
    height:8px;
    border-radius:20px;
    background:#171c24;
    overflow:hidden;
    margin:10px 0;
}

.confidence-bar{
    height:100%;
    background:#20e879;
    width:0%;
}

.signal-details{
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:8px;
}

.detail{
    background:#10141b;
    padding:12px;
    border-radius:8px;
}

.detail small{
    display:block;
    color:#798392;
    font-size:10px;
    margin-bottom:4px;
}

.detail strong{
    font-size:14px;
}

.countdown{
    margin-top:14px;
    text-align:center;
    font-size:32px;
    font-weight:900;
}

.enter{
    width:100%;
    margin-top:15px;
    padding:16px;
    border:0;
    border-radius:9px;
    background:#1ce878;
    color:#031108;
    font-weight:1000;
    font-size:16px;
}

.enter:disabled{
    background:#272d36;
    color:#7c8693;
}

.reason{
    color:#9ca6b5;
    font-size:12px;
    padding:5px 0;
}

.history{
    margin-top:15px;
}

.history-row{
    display:flex;
    justify-content:space-between;
    padding:10px 0;
    border-bottom:1px solid #171c24;
    font-size:12px;
}

.bottom{
    margin-top:15px;
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:12px;
}

.card{
    background:#0b0f15;
    border:1px solid #232a34;
    border-radius:10px;
    padding:15px;
}

.card h3{
    margin:0 0 10px;
    font-size:12px;
    color:#8f99a8;
}

.big{
    font-size:22px;
    font-weight:900;
}

.warning{
    color:#ffbb32;
}

.good{
    color:#20e879;
}

.bad{
    color:#ff3e3e;
}

@media(max-width:1050px){

    .layout{
        grid-template-columns:1fr;
    }

    .sidebar,
    .right{
        border:0;
        border-bottom:1px solid #202631;
    }

    .sidebar{
        display:none;
    }

    .right{
        order:3;
    }

    .main{
        order:2;
    }

}

</style>

</head>

<body>

<div class="header">

    <div class="logo">
        RYU <span>V2</span>
    </div>

    <div>
        AI TRADING ASSISTANT
    </div>

    <div class="status">
        <span id="dot" class="dot"></span>
        <span id="feedStatus">FEED OFFLINE</span>
    </div>

</div>

<div class="layout">

<div class="sidebar">

<div class="panel">

<div class="section-title">
ASSETS
</div>

<input
    id="search"
    class="search"
    placeholder="Search assets..."
>

<div class="filters">
<button class="filter active">ALL</button>
<button class="filter">FOREX</button>
<button class="filter">CRYPTO</button>
<button class="filter">STOCKS</button>
</div>

<div id="assetList">

<div class="asset" onclick="selectAsset('EURUSD_otc')">
<div>
<div class="asset-name">EUR/USD OTC</div>
<div class="asset-meta">Forex</div>
</div>
<div>★</div>
</div>

<div class="asset" onclick="selectAsset('GBPUSD_otc')">
<div>
<div class="asset-name">GBP/USD OTC</div>
<div class="asset-meta">Forex</div>
</div>
<div>★</div>
</div>

<div class="asset" onclick="selectAsset('USDJPY_otc')">
<div>
<div class="asset-name">USD/JPY OTC</div>
<div class="asset-meta">Forex</div>
</div>
<div>★</div>
</div>

<div class="asset" onclick="selectAsset('BTCUSD_otc')">
<div>
<div class="asset-name">BTC/USD OTC</div>
<div class="asset-meta">Crypto</div>
</div>
<div>★</div>
</div>

<div class="asset" onclick="selectAsset('ETHUSD_otc')">
<div>
<div class="asset-name">ETH/USD OTC</div>
<div class="asset-meta">Crypto</div>
</div>
<div>★</div>
</div>

<div class="asset" onclick="selectAsset('XAUUSD_otc')">
<div>
<div class="asset-name">Gold OTC</div>
<div class="asset-meta">Commodity</div>
</div>
<div>★</div>
</div>

</div>

</div>

</div>

<div class="main">

<div class="asset-header">

<div>

<div class="asset-title" id="assetTitle">
EUR/USD OTC
</div>

<div style="color:#7e8998;font-size:12px">
Pocket Option OTC • Live Feed
</div>

</div>

<div class="price" id="price">
--
</div>

</div>

<div class="timeframes">

<button class="tf active" onclick="setTF('1m',this)">
1m
</button>

<button class="tf" onclick="setTF('2m',this)">
2m
</button>

<button class="tf" onclick="setTF('3m',this)">
3m
</button>

<button class="tf" onclick="setTF('5m',this)">
5m
</button>

</div>

<div class="chart">

<div class="chart-message" id="chartMessage">

<strong>WAITING FOR POCKET OPTION</strong>

Connect the live feed to RYU V2.<br>
RYU will not fabricate candles or signals.

</div>

</div>

<div id="signalBox" class="signal-box wait">

<div class="signal-label">
RYU V2 LIVE SIGNAL
</div>

<div id="signal" class="signal">
WAIT
</div>

<div>
Confidence: <strong id="confidence">0%</strong>
</div>

<div class="confidence">
<div id="confidenceBar" class="confidence-bar"></div>
</div>

<div class="signal-details">

<div class="detail">
<small>ENTRY</small>
<strong id="entry">--</strong>
</div>

<div class="detail">
<small>EXPIRY</small>
<strong>5 MIN</strong>
</div>

<div class="detail">
<small>PAYOUT</small>
<strong id="payout">--</strong>
</div>

<div class="detail">
<small>CANDLES</small>
<strong id="candles">0</strong>
</div>

</div>

<div class="countdown" id="countdown">
WAIT
</div>

<button
    id="enter"
    class="enter"
    disabled
>
WAIT FOR SIGNAL
</button>

<div id="reasons" style="margin-top:15px"></div>

</div>

<div class="bottom">

<div class="card">

<h3>LIVE MARKET</h3>

<div class="big" id="marketPrice">
--
</div>

<div id="marketStatus">
Waiting for feed
</div>

</div>

<div class="card">

<h3>CONFLUENCE</h3>

<div class="big" id="confluence">
0 / 10
</div>

<div>
EMA • Alligator • MACD • RSI • BB • Momentum
</div>

</div>

<div class="card">

<h3>SERVER TIME</h3>

<div class="big" id="serverTime">
--
</div>

<div>
UTC
</div>

</div>

</div>

</div>

<div class="right">

<div class="panel">

<div class="section-title">
RYU V2 LIVE SIGNAL
</div>

<div class="signal-box wait">

<div class="signal-label">
SELECTED MARKET
</div>

<div class="big" id="rightAsset">
EUR/USD OTC
</div>

<div style="margin-top:12px">

TIMEFRAME:
<strong id="rightTF">1m</strong>

</div>

<div style="margin-top:10px">

EXPIRY:
<strong>5 MINUTES</strong>

</div>

<hr style="border-color:#202631;margin:18px 0">

<div class="signal-label">
SIGNAL
</div>

<div id="rightSignal"
     class="signal"
     style="font-size:38px">
WAIT
</div>

<div>
Confidence:
<strong id="rightConfidence">0%</strong>
</div>

<div class="confidence">

<div
    id="rightConfidenceBar"
    class="confidence-bar">
</div>

</div>

<div style="margin-top:12px">

Entry:
<strong id="rightEntry">--</strong>

</div>

<div style="margin-top:10px">

Payout:
<strong id="rightPayout">--</strong>

</div>

<div class="countdown"
     id="rightCountdown">
WAIT
</div>

<button
    class="enter"
    id="rightEnter"
    disabled>
WAIT FOR SIGNAL
</button>

</div>

<div class="history">

<div class="section-title">
RECENT SIGNALS
</div>

<div id="history">
No signals yet.
</div>

</div>

</div>

</div>

</div>

<script>

let asset = "EURUSD_otc";
let timeframe = "1m";
let latestSignal = "WAIT";
let signalTimestamp = null;

function displayAsset(a){

    return a
        .replace("_otc"," OTC")
        .replace("EURUSD","EUR/USD")
        .replace("GBPUSD","GBP/USD")
        .replace("USDJPY","USD/JPY")
        .replace("BTCUSD","BTC/USD")
        .replace("ETHUSD","ETH/USD")
        .replace("XAUUSD","GOLD/USD");

}

function selectAsset(a){

    asset = a;

    fetch("/api/select",{
        method:"POST",
        headers:{
            "Content-Type":"application/json"
        },
        body:JSON.stringify({
            asset:asset,
            timeframe:timeframe
        })
    });

    document.getElementById("assetTitle").innerText =
        displayAsset(asset);

    document.getElementById("rightAsset").innerText =
        displayAsset(asset);

    update();
}

function setTF(tf,button){

    timeframe = tf;

    document.querySelectorAll(".tf")
        .forEach(x => x.classList.remove("active"));

    button.classList.add("active");

    fetch("/api/select",{
        method:"POST",
        headers:{
            "Content-Type":"application/json"
        },
        body:JSON.stringify({
            asset:asset,
            timeframe:timeframe
        })
    });

    document.getElementById("rightTF").innerText =
        timeframe;

    update();
}

function formatPrice(value){

    if(value === null || value === undefined)
        return "--";

    return Number(value).toFixed(6);
}

function update(){

    fetch(
        "/api/state?asset=" +
        encodeURIComponent(asset) +
        "&timeframe=" +
        encodeURIComponent(timeframe)
    )
    .then(r => r.json())
    .then(data => {

        const feed = data.feed;

        const dot =
            document.getElementById("dot");

        const feedStatus =
            document.getElementById("feedStatus");

        if(feed.connected){

            dot.classList.add("live");

            feedStatus.innerText =
                "POCKET OPTION LIVE";

        }else{

            dot.classList.remove("live");

            feedStatus.innerText =
                "FEED OFFLINE";

        }

        const s = data.signal;

        latestSignal = s.signal;

        document.getElementById("price").innerText =
            formatPrice(s.price);

        document.getElementById("marketPrice").innerText =
            formatPrice(s.price);

        document.getElementById("entry").innerText =
            formatPrice(s.entry);

        document.getElementById("rightEntry").innerText =
            formatPrice(s.entry);

        document.getElementById("payout").innerText =
            s.payout == null ? "--" : s.payout + "%";

        document.getElementById("rightPayout").innerText =
            s.payout == null ? "--" : s.payout + "%";

        document.getElementById("confidence").innerText =
            s.confidence + "%";

        document.getElementById("rightConfidence").innerText =
            s.confidence + "%";

        document.getElementById("confidenceBar").style.width =
            s.confidence + "%";

        document.getElementById("rightConfidenceBar").style.width =
            s.confidence + "%";

        document.getElementById("candles").innerText =
            data.assets[asset]
            ? data.assets[asset].candles
            : "0";

        document.getElementById("confluence").innerText =
            (s.score || 0) + " / " + (s.max_score || 10);

        document.getElementById("signal").innerText =
            s.signal;

        document.getElementById("rightSignal").innerText =
            s.signal;

        const box =
            document.getElementById("signalBox");

        box.classList.remove(
            "call",
            "put",
            "wait"
        );

        if(s.signal === "CALL")
            box.classList.add("call");

        else if(s.signal === "PUT")
            box.classList.add("put");

        else
            box.classList.add("wait");

        const enter =
            document.getElementById("enter");

        const rightEnter =
            document.getElementById("rightEnter");

        if(
            feed.connected &&
            (s.signal === "CALL" || s.signal === "PUT")
        ){

            enter.disabled = false;
            rightEnter.disabled = false;

            enter.innerText =
                "ENTER " + s.signal;

            rightEnter.innerText =
                "ENTER " + s.signal;

        }else{

            enter.disabled = true;
            rightEnter.disabled = true;

            enter.innerText =
                feed.connected
                ? "WAIT FOR SIGNAL"
                : "FEED OFFLINE";

            rightEnter.innerText =
                feed.connected
                ? "WAIT FOR SIGNAL"
                : "FEED OFFLINE";
        }

        const reasons =
            document.getElementById("reasons");

        reasons.innerHTML = "";

        if(s.reasons){

            s.reasons.forEach(r => {

                const div =
                    document.createElement("div");

                div.className = "reason";

                div.innerText =
                    "✓ " + r;

                reasons.appendChild(div);

            });

        }

        const history =
            document.getElementById("history");

        if(data.signal_history.length){

            history.innerHTML = "";

            data.signal_history
                .slice(0,8)
                .forEach(h => {

                    const row =
                        document.createElement("div");

                    row.className =
                        "history-row";

                    row.innerHTML =
                        "<span>" +
                        displayAsset(h.asset) +
                        "</span>" +
                        "<strong>" +
                        h.signal +
                        " " +
                        h.confidence +
                        "%</strong>";

                    history.appendChild(row);

                });

        }

        document.getElementById("marketStatus")
            .innerText =
            feed.connected
            ? "LIVE"
            : "Waiting for Pocket Option";

        document.getElementById("serverTime")
            .innerText =
            new Date().toLocaleTimeString();

        document.getElementById("chartMessage")
            .innerHTML =
            feed.connected
            ? "<strong>POCKET OPTION LIVE</strong>" +
              "RYU is analyzing the live feed."
            : "<strong>WAITING FOR POCKET OPTION</strong>" +
              "RYU will not fabricate candles or signals.";

    })
    .catch(() => {

        document.getElementById("feedStatus")
            .innerText =
            "RYU OFFLINE";

    });

}

setInterval(update,1000);

update();

</script>

</body>
</html>
"""


@app.get("/")
def dashboard():
    return render_template_string(HTML)


# ============================================================
# Start
# ============================================================

if __name__ == "__main__":

    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )
