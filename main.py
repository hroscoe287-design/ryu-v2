import os
import json
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template_string

# ============================================================
# RYU V2 - POCKET OPTION LIVE SIGNAL DASHBOARD
# ============================================================
#
# SIGNAL ONLY.
# This application does NOT place Pocket Option trades.
#
# Pocket Option connector -> /api/feed -> Ryu engine -> UI
#
# ============================================================

app = Flask(__name__)

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

TIMEFRAMES = [1, 2, 3]
DEFAULT_TIMEFRAME = 1
DEFAULT_EXPIRY = 5

MAX_TICKS = 5000
MAX_CANDLES = 500

lock = threading.Lock()

selected_asset = os.getenv("DEFAULT_ASSET", "EUR/USD")
selected_timeframe = int(
    os.getenv("DEFAULT_TIMEFRAME", str(DEFAULT_TIMEFRAME))
)

expiry_minutes = int(
    os.getenv("SIGNAL_EXPIRY_MINUTES", str(DEFAULT_EXPIRY))
)

# ------------------------------------------------------------
# ASSET LIST
# ------------------------------------------------------------

ASSETS = {
    "FOREX": [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "USD/CAD",
        "USD/CHF",
        "NZD/USD",
    ],
    "CRYPTO": [
        "BTC/USD",
        "ETH/USD",
        "SOL/USD",
        "XRP/USD",
    ],
    "STOCKS": [
        "AAPL",
        "TSLA",
        "NVDA",
        "AMZN",
        "META",
        "MSFT",
    ],
}

# ------------------------------------------------------------
# MARKET DATA
# ------------------------------------------------------------

market = defaultdict(
    lambda: {
        "ticks": deque(maxlen=MAX_TICKS),
        "candles": deque(maxlen=MAX_CANDLES),
        "last_price": None,
        "last_timestamp": None,
        "payout": None,
        "source": "none",
    }
)

current_signal = {
    "asset": selected_asset,
    "direction": "WAIT",
    "confidence": 0,
    "entry": None,
    "expiry_minutes": expiry_minutes,
    "signal_time": None,
    "candle_time": None,
    "reason": "Waiting for live Pocket Option data",
    "source": "none",
}

stats = {
    "ticks": 0,
    "candles": 0,
    "signals": 0,
    "wins": 0,
    "losses": 0,
}

# ------------------------------------------------------------
# TECHNICAL FUNCTIONS
# ------------------------------------------------------------

def sma(values, period):
    if len(values) < period:
        return None

    values = list(values)[-period:]
    return sum(values) / period


def ema(values, period):
    values = list(values)

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    result = sum(values[:period]) / period

    for price in values[period:]:
        result = ((price - result) * multiplier) + result

    return result


def rsi(values, period=14):
    values = list(values)

    if len(values) < period + 1:
        return None

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

    gains = gains[-period:]
    losses = losses[-period:]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def macd(values):
    values = list(values)

    if len(values) < 26:
        return None, None

    fast = ema(values, 12)
    slow = ema(values, 26)

    if fast is None or slow is None:
        return None, None

    line = fast - slow

    # Approximation for real-time signal processing.
    signal = line

    return line, signal


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None

    trs = []

    candles = list(candles)

    for i in range(1, len(candles)):
        current = candles[i]
        previous = candles[i - 1]

        high = current["high"]
        low = current["low"]
        previous_close = previous["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )

        trs.append(tr)

    if len(trs) < period:
        return None

    return sum(trs[-period:]) / period


def alligator(candles):
    """
    Simplified Williams Alligator calculation.

    Jaw   = SMA 13
    Teeth = SMA 8
    Lips  = SMA 5
    """

    closes = [c["close"] for c in candles]

    if len(closes) < 13:
        return None

    jaw = sma(closes, 13)
    teeth = sma(closes, 8)
    lips = sma(closes, 5)

    return {
        "jaw": jaw,
        "teeth": teeth,
        "lips": lips,
    }


# ------------------------------------------------------------
# CANDLE BUILDER
# ------------------------------------------------------------

def candle_bucket(timestamp, timeframe_minutes):
    seconds = timeframe_minutes * 60
    return int(timestamp // seconds) * seconds


def add_tick(asset, price, timestamp=None, payout=None):
    if timestamp is None:
        timestamp = time.time()

    try:
        price = float(price)
        timestamp = float(timestamp)
    except Exception:
        return False

    with lock:
        data = market[asset]

        data["ticks"].append(
            {
                "timestamp": timestamp,
                "price": price,
            }
        )

        data["last_price"] = price
        data["last_timestamp"] = timestamp
        data["source"] = "pocket_option"

        if payout is not None:
            try:
                data["payout"] = float(payout)
            except Exception:
                pass

        stats["ticks"] += 1

    build_candle(asset, price, timestamp)

    return True


def build_candle(asset, price, timestamp):
    global current_signal

    bucket = candle_bucket(timestamp, selected_timeframe)

    with lock:
        candles = market[asset]["candles"]

        if candles and candles[-1]["timestamp"] == bucket:
            candle = candles[-1]

            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price

        else:
            candle = {
                "timestamp": bucket,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            }

            candles.append(candle)
            stats["candles"] += 1

    if asset == selected_asset:
        calculate_signal(asset)


# ------------------------------------------------------------
# RYU SIGNAL ENGINE
# ------------------------------------------------------------

def calculate_signal(asset):
    global current_signal

    with lock:
        candles = list(market[asset]["candles"])

    if len(candles) < 30:
        current_signal = {
            "asset": asset,
            "direction": "WAIT",
            "confidence": 0,
            "entry": market[asset]["last_price"],
            "expiry_minutes": expiry_minutes,
            "signal_time": datetime.now(timezone.utc).isoformat(),
            "candle_time": candles[-1]["timestamp"] if candles else None,
            "reason": "Collecting candles",
            "source": market[asset]["source"],
        }

        return

    closes = [c["close"] for c in candles]

    price = closes[-1]

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)

    rsi_value = rsi(closes)

    macd_line, macd_signal = macd(closes)

    alligator_data = alligator(candles)

    atr_value = atr(candles)

    if None in (
        ema9,
        ema21,
        rsi_value,
        macd_line,
        macd_signal,
        alligator_data,
    ):
        return

    score_call = 0
    score_put = 0

    reasons_call = []
    reasons_put = []

    # --------------------------------------------------------
    # EMA TREND
    # --------------------------------------------------------

    if ema9 > ema21:
        score_call += 1
        reasons_call.append("EMA bullish")

    elif ema9 < ema21:
        score_put += 1
        reasons_put.append("EMA bearish")

    # --------------------------------------------------------
    # ALLIGATOR
    # --------------------------------------------------------

    jaw = alligator_data["jaw"]
    teeth = alligator_data["teeth"]
    lips = alligator_data["lips"]

    if lips > teeth > jaw and price > lips:
        score_call += 2
        reasons_call.append("Alligator bullish")

    elif lips < teeth < jaw and price < lips:
        score_put += 2
        reasons_put.append("Alligator bearish")

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if macd_line > macd_signal:
        score_call += 1
        reasons_call.append("MACD bullish")

    elif macd_line < macd_signal:
        score_put += 1
        reasons_put.append("MACD bearish")

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if 52 <= rsi_value <= 70:
        score_call += 1
        reasons_call.append("RSI supports CALL")

    elif 30 <= rsi_value <= 48:
        score_put += 1
        reasons_put.append("RSI supports PUT")

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if len(closes) >= 4:

        momentum = closes[-1] - closes[-4]

        if momentum > 0:
            score_call += 1
            reasons_call.append("Positive momentum")

        elif momentum < 0:
            score_put += 1
            reasons_put.append("Negative momentum")

    # --------------------------------------------------------
    # FINAL DECISION
    # --------------------------------------------------------

    total = max(score_call, score_put)

    direction = "WAIT"
    confidence = 0
    reasons = ["No strong confluence"]

    if score_call >= 5 and score_call > score_put:
        direction = "CALL"
        confidence = min(99, 55 + (score_call * 7))
        reasons = reasons_call

    elif score_put >= 5 and score_put > score_call:
        direction = "PUT"
        confidence = min(99, 55 + (score_put * 7))
        reasons = reasons_put

    current_signal = {
        "asset": asset,
        "direction": direction,
        "confidence": confidence,
        "entry": price,
        "expiry_minutes": expiry_minutes,
        "signal_time": datetime.now(timezone.utc).isoformat(),
        "candle_time": candles[-1]["timestamp"],
        "reason": " + ".join(reasons),
        "source": market[asset]["source"],
        "ema9": round(ema9, 8),
        "ema21": round(ema21, 8),
        "rsi": round(rsi_value, 2),
        "macd": round(macd_line, 8),
        "atr": round(atr_value, 8) if atr_value else None,
    }

    if direction != "WAIT":
        stats["signals"] += 1


# ------------------------------------------------------------
# API
# ------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "online",
            "service": "Ryu V2",
            "source": market[selected_asset]["source"],
            "asset": selected_asset,
            "last_price": market[selected_asset]["last_price"],
            "ticks": stats["ticks"],
            "candles": stats["candles"],
        }
    )


@app.route("/api/state")
def state():
    with lock:
        data = market[selected_asset]

        return jsonify(
            {
                "status": "online",
                "asset": selected_asset,
                "timeframe": selected_timeframe,
                "expiry_minutes": expiry_minutes,
                "price": data["last_price"],
                "timestamp": data["last_timestamp"],
                "payout": data["payout"],
                "source": data["source"],
                "signal": current_signal,
                "stats": stats,
                "candles": list(data["candles"])[-80:],
            }
        )


@app.route("/api/assets")
def assets():
    return jsonify(ASSETS)


@app.route("/api/select", methods=["POST"])
def select_asset():
    global selected_asset
    global selected_timeframe

    payload = request.get_json(silent=True) or {}

    asset = payload.get("asset")

    timeframe = payload.get("timeframe")

    if asset:
        selected_asset = str(asset)

    if timeframe:
        try:
            timeframe = int(timeframe)

            if timeframe in TIMEFRAMES:
                selected_timeframe = timeframe

        except Exception:
            pass

    return jsonify(
        {
            "ok": True,
            "asset": selected_asset,
            "timeframe": selected_timeframe,
        }
    )


@app.route("/api/feed", methods=["POST"])
def feed():
    """
    Pocket Option connector posts normalized ticks here.

    Accepted JSON:

    {
        "asset": "EUR/USD",
        "price": 1.23456,
        "timestamp": 1234567890,
        "payout": 85
    }
    """

    payload = request.get_json(silent=True)

    if not payload:
        return jsonify(
            {
                "ok": False,
                "error": "JSON body required",
            }
        ), 400

    asset = payload.get("asset")
    price = payload.get("price")

    if not asset or price is None:
        return jsonify(
            {
                "ok": False,
                "error": "asset and price required",
            }
        ), 400

    accepted = add_tick(
        asset=asset,
        price=price,
        timestamp=payload.get("timestamp"),
        payout=payload.get("payout"),
    )

    return jsonify(
        {
            "ok": accepted,
            "asset": asset,
            "price": price,
        }
    )


# ------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------

HTML = r"""
<!DOCTYPE html>
<html>
<head>

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Ryu V2</title>

<style>

* {
    box-sizing:border-box;
}

body {
    margin:0;
    background:#06080d;
    color:#f5f7fa;
    font-family:Arial,Helvetica,sans-serif;
}

.header {
    padding:16px;
    background:#0b0f17;
    border-bottom:1px solid #1c2430;
    display:flex;
    justify-content:space-between;
    align-items:center;
}

.logo {
    font-size:24px;
    font-weight:900;
    letter-spacing:2px;
}

.live {
    color:#00ff88;
    font-weight:bold;
}

.nav {
    display:flex;
    gap:8px;
    padding:10px;
    overflow-x:auto;
    background:#090d14;
}

.nav button,
.filter button {
    background:#111722;
    color:white;
    border:1px solid #273142;
    padding:9px 14px;
    border-radius:8px;
}

.container {
    max-width:1100px;
    margin:auto;
    padding:12px;
}

.controls {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:10px;
    margin-bottom:12px;
}

select {
    width:100%;
    background:#101620;
    color:white;
    border:1px solid #293445;
    border-radius:8px;
    padding:12px;
}

.signal {
    background:#0c1119;
    border:1px solid #263142;
    border-radius:15px;
    padding:20px;
    text-align:center;
}

.signal-title {
    color:#8994a5;
    font-size:13px;
}

.direction {
    font-size:58px;
    font-weight:900;
    margin:10px;
}

.call {
    color:#00ff88;
}

.put {
    color:#ff3158;
}

.wait {
    color:#ffd447;
}

.confidence {
    font-size:20px;
    margin-bottom:10px;
}

.entry {
    font-size:28px;
    font-weight:bold;
}

.timer {
    margin:20px auto;
    width:160px;
    height:160px;
    border-radius:50%;
    border:5px solid #273142;
    display:flex;
    align-items:center;
    justify-content:center;
    flex-direction:column;
}

.timer-value {
    font-size:30px;
    font-weight:900;
}

.timer-label {
    font-size:11px;
    color:#7d8898;
}

.grid {
    display:grid;
    grid-template-columns:2fr 1fr;
    gap:12px;
    margin-top:12px;
}

.card {
    background:#0c1119;
    border:1px solid #202a39;
    border-radius:12px;
    padding:14px;
}

.card h3 {
    margin-top:0;
}

#chart {
    width:100%;
    height:320px;
    background:#070a0f;
    border-radius:10px;
}

.status {
    color:#8e99a9;
    font-size:13px;
}

.confluence div {
    padding:8px;
    border-bottom:1px solid #1a2230;
}

.footer {
    padding:20px;
    color:#687386;
    font-size:12px;
    text-align:center;
}

@media(max-width:700px) {

    .grid {
        grid-template-columns:1fr;
    }

    .controls {
        grid-template-columns:1fr;
    }

}

</style>

</head>

<body>

<div class="header">

    <div class="logo">🔥 RYU V2</div>

    <div class="live" id="connection">
        ● CONNECTING
    </div>

</div>

<div class="nav">

    <button>Signals</button>
    <button>Trades</button>
    <button>Performance</button>
    <button>Settings</button>

</div>

<div class="container">

    <div class="controls">

        <select id="asset"></select>

        <select id="timeframe">

            <option value="1">1 Minute</option>
            <option value="2">2 Minutes</option>
            <option value="3">3 Minutes</option>

        </select>

    </div>

    <div class="signal">

        <div class="signal-title">
            RYU V2 LIVE SIGNAL
        </div>

        <div id="direction" class="direction wait">
            WAIT
        </div>

        <div id="confidence" class="confidence">
            Confidence: 0%
        </div>

        <div class="entry">
            <span id="price">--</span>
        </div>

        <div class="timer">

            <div id="timer" class="timer-value">
                --:--
            </div>

            <div class="timer-label">
                SIGNAL CANDLE
            </div>

        </div>

        <div id="reason" class="status">
            Waiting for Pocket Option live feed...
        </div>

    </div>

    <div class="grid">

        <div class="card">

            <h3>Live Chart</h3>

            <canvas id="chart"></canvas>

        </div>

        <div class="card">

            <h3>Confluence</h3>

            <div class="confluence">

                <div>
                    EMA:
                    <span id="ema">--</span>
                </div>

                <div>
                    RSI:
                    <span id="rsi">--</span>
                </div>

                <div>
                    MACD:
                    <span id="macd">--</span>
                </div>

                <div>
                    ATR:
                    <span id="atr">--</span>
                </div>

                <div>
                    Payout:
                    <span id="payout">--</span>
                </div>

            </div>

        </div>

    </div>

    <div class="card" style="margin-top:12px">

        <h3>Feed Status</h3>

        <div id="feedstatus" class="status">
            Waiting...
        </div>

    </div>

</div>

<div class="footer">

    Ryu V2 • Signal analysis only • No automatic trade execution

</div>

<script>

let lastState = null;

async function loadAssets() {

    const response = await fetch("/api/assets");

    const assets = await response.json();

    const select = document.getElementById("asset");

    select.innerHTML = "";

    Object.keys(assets).forEach(category => {

        const group = document.createElement("optgroup");

        group.label = category;

        assets[category].forEach(asset => {

            const option = document.createElement("option");

            option.value = asset;
            option.textContent = asset;

            group.appendChild(option);

        });

        select.appendChild(group);

    });

}

async function selectMarket() {

    const asset =
        document.getElementById("asset").value;

    const timeframe =
        document.getElementById("timeframe").value;

    await fetch("/api/select", {

        method:"POST",

        headers:{
            "Content-Type":"application/json"
        },

        body:JSON.stringify({
            asset:asset,
            timeframe:Number(timeframe)
        })

    });

}

document
.getElementById("asset")
.addEventListener("change",selectMarket);

document
.getElementById("timeframe")
.addEventListener("change",selectMarket);


function formatPrice(price) {

    if (price === null || price === undefined)
        return "--";

    return Number(price).toFixed(6);

}


function updateTimer(state) {

    if (!state.timestamp) {

        document.getElementById("timer").textContent =
            "--:--";

        return;

    }

    const timeframe =
        Number(state.timeframe || 1);

    const now = Math.floor(Date.now() / 1000);

    const bucket =
        Math.floor(now / (timeframe * 60))
        * (timeframe * 60);

    const elapsed =
        now - bucket;

    const remaining =
        (timeframe * 60) - elapsed;

    const minutes =
        Math.floor(remaining / 60);

    const seconds =
        remaining % 60;

    document.getElementById("timer").textContent =
        String(minutes).padStart(2,"0")
        + ":"
        + String(seconds).padStart(2,"0");

}


function drawChart(candles) {

    const canvas =
        document.getElementById("chart");

    const ctx =
        canvas.getContext("2d");

    const width =
        canvas.clientWidth;

    const height =
        canvas.clientHeight;

    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0,0,width,height);

    if (!candles || candles.length < 2)
        return;

    const data =
        candles.slice(-50);

    const values =
        data.map(c => Number(c.close));

    const min =
        Math.min(...values);

    const max =
        Math.max(...values);

    const range =
        max - min || 1;

    ctx.beginPath();

    data.forEach((c,i) => {

        const x =
            (i / (data.length - 1))
            * width;

        const y =
            height -
            ((Number(c.close) - min) / range)
            * (height - 20)
            - 10;

        if (i === 0)
            ctx.moveTo(x,y);
        else
            ctx.lineTo(x,y);

    });

    ctx.strokeStyle = "#00ff88";

    ctx.lineWidth = 2;

    ctx.stroke();

}


async function update() {

    try {

        const response =
            await fetch("/api/state");

        const state =
            await response.json();

        lastState = state;

        document
            .getElementById("connection")
            .textContent =
            state.source === "pocket_option"
            ? "● POCKET OPTION LIVE"
            : "● WAITING FOR FEED";

        const signal =
            state.signal || {};

        const direction =
            signal.direction || "WAIT";

        const directionElement =
            document.getElementById("direction");

        directionElement.textContent =
            direction;

        directionElement.className =
            "direction " +
            direction.toLowerCase();

        document
            .getElementById("confidence")
            .textContent =
            "Confidence: " +
            (signal.confidence || 0) +
            "%";

        document
            .getElementById("price")
            .textContent =
            formatPrice(state.price);

        document
            .getElementById("reason")
            .textContent =
            signal.reason ||
            "Waiting...";

        document
            .getElementById("ema")
            .textContent =
            signal.ema9
            ? signal.ema9 + " / " + signal.ema21
            : "--";

        document
            .getElementById("rsi")
            .textContent =
            signal.rsi || "--";

        document
            .getElementById("macd")
            .textContent =
            signal.macd || "--";

        document
            .getElementById("atr")
            .textContent =
            signal.atr || "--";

        document
            .getElementById("payout")
            .textContent =
            state.payout
            ? state.payout + "%"
            : "--";

        document
            .getElementById("feedstatus")
            .textContent =
            "Asset: " +
            state.asset +
            " | Timeframe: " +
            state.timeframe +
            "m | Ticks: " +
            state.stats.ticks +
            " | Candles: " +
            state.stats.candles;

        drawChart(state.candles);

        updateTimer(state);

    } catch(error) {

        document
            .getElementById("connection")
            .textContent =
            "● OFFLINE";

    }

}


loadAssets().then(update);

setInterval(update,1000);

</script>

</body>
</html>
"""


# ------------------------------------------------------------
# STARTUP
# ------------------------------------------------------------

if __name__ == "__main__":

    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
