import os
import time
import math
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template_string

# ============================================================
# RYU V2 - POCKET OPTION LIVE SIGNAL DASHBOARD
# SIGNAL ONLY — DOES NOT PLACE TRADES
# ============================================================

app = Flask(__name__)

# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

EXPIRY_MINUTES = 5
MAX_CANDLES = 300

SUPPORTED_ASSETS = {
    "FOREX": [
        "EUR/USD OTC",
        "GBP/USD OTC",
        "USD/JPY OTC",
        "AUD/USD OTC",
        "USD/CAD OTC",
        "USD/CHF OTC",
    ],
    "CRYPTO": [
        "BTC/USD OTC",
        "ETH/USD OTC",
        "SOL/USD OTC",
        "XRP/USD OTC",
    ],
    "STOCKS": [
        "AAPL OTC",
        "TSLA OTC",
        "NVDA OTC",
        "AMZN OTC",
        "SPY OTC",
        "QQQ OTC",
    ],
}

TIMEFRAMES = ["1m", "2m", "3m"]

# ------------------------------------------------------------
# DATA STORAGE
# ------------------------------------------------------------

market_data = defaultdict(
    lambda: {
        "prices": deque(maxlen=MAX_CANDLES),
        "timestamps": deque(maxlen=MAX_CANDLES),
        "last_price": None,
        "updated": None,
    }
)

signals = deque(maxlen=100)
trade_history = deque(maxlen=500)

selected_asset = "EUR/USD OTC"
selected_timeframe = "1m"

lock = threading.Lock()


# ============================================================
# INDICATORS
# ============================================================

def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)
    result = sum(values[:period]) / period

    for price in values[period:]:
        result = (price - result) * multiplier + result

    return result


def rsi(values, period=14):
    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(-period, 0):
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
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def macd(values):
    fast = ema(values, 12)
    slow = ema(values, 26)

    if fast is None or slow is None:
        return None

    return fast - slow


def bollinger(values, period=20, deviation=2):
    if len(values) < period:
        return None, None, None

    middle = sma(values, period)

    variance = sum(
        (x - middle) ** 2
        for x in values[-period:]
    ) / period

    std = math.sqrt(variance)

    upper = middle + deviation * std
    lower = middle - deviation * std

    return upper, middle, lower


def alligator(values):
    """
    Simplified Alligator calculation.

    Jaw    = SMA 13
    Teeth  = SMA 8
    Lips   = SMA 5
    """

    jaw = sma(values, 13)
    teeth = sma(values, 8)
    lips = sma(values, 5)

    return jaw, teeth, lips


# ============================================================
# RYU SIGNAL ENGINE
# ============================================================

def generate_signal(asset, timeframe):
    data = market_data[asset]
    prices = list(data["prices"])

    if len(prices) < 35:
        return {
            "signal": "WAIT",
            "confidence": 0,
            "reason": "Waiting for market data",
            "asset": asset,
            "timeframe": timeframe,
        }

    current = prices[-1]

    fast = ema(prices, 9)
    slow = ema(prices, 21)
    momentum = macd(prices)
    rsi_value = rsi(prices)

    upper, middle, lower = bollinger(prices)

    jaw, teeth, lips = alligator(prices)

    call_score = 0
    put_score = 0
    reasons = []

    # --------------------------------------------------------
    # EMA TREND
    # --------------------------------------------------------

    if fast > slow:
        call_score += 2
        reasons.append("EMA bullish")
    elif fast < slow:
        put_score += 2
        reasons.append("EMA bearish")

    # --------------------------------------------------------
    # ALLIGATOR
    # --------------------------------------------------------

    if lips > teeth > jaw:
        call_score += 2
        reasons.append("Alligator bullish")

    elif lips < teeth < jaw:
        put_score += 2
        reasons.append("Alligator bearish")

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if momentum > 0:
        call_score += 1
        reasons.append("MACD positive")

    elif momentum < 0:
        put_score += 1
        reasons.append("MACD negative")

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if rsi_value is not None:

        if 52 <= rsi_value <= 70:
            call_score += 1
            reasons.append("RSI bullish")

        elif 30 <= rsi_value <= 48:
            put_score += 1
            reasons.append("RSI bearish")

    # --------------------------------------------------------
    # BOLLINGER
    # --------------------------------------------------------

    if upper and lower:

        if current > middle:
            call_score += 1
            reasons.append("Above Bollinger midline")

        elif current < middle:
            put_score += 1
            reasons.append("Below Bollinger midline")

    # --------------------------------------------------------
    # FINAL DECISION
    # --------------------------------------------------------

    total = call_score + put_score

    if total < 5:
        direction = "WAIT"
        confidence = min(69, 45 + total * 4)

    elif call_score > put_score:
        direction = "CALL"
        confidence = min(
            99,
            55 + call_score * 7
        )

    elif put_score > call_score:
        direction = "PUT"
        confidence = min(
            99,
            55 + put_score * 7
        )

    else:
        direction = "WAIT"
        confidence = 50

    # --------------------------------------------------------
    # PAYOUT ESTIMATE
    # --------------------------------------------------------

    payout = {
        "EUR/USD OTC": 82,
        "GBP/USD OTC": 59,
        "USD/JPY OTC": 85,
        "AUD/USD OTC": 78,
        "USD/CAD OTC": 76,
        "USD/CHF OTC": 74,
        "BTC/USD OTC": 49,
        "ETH/USD OTC": 48,
        "SOL/USD OTC": 47,
        "XRP/USD OTC": 47,
    }.get(asset, 70)

    signal = {
        "id": int(time.time() * 1000),
        "asset": asset,
        "timeframe": timeframe,
        "signal": direction,
        "confidence": confidence,
        "payout": payout,
        "entry_price": current,
        "expiry_minutes": EXPIRY_MINUTES,
        "reason": ", ".join(reasons[-5:]),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    return signal


# ============================================================
# FEED API
# ============================================================

@app.route("/api/feed", methods=["POST"])
def receive_feed():

    try:
        payload = request.get_json(force=True)

        asset = payload.get("asset")
        price = payload.get("price")
        timestamp = payload.get(
            "timestamp",
            time.time()
        )

        if not asset or price is None:
            return jsonify({
                "ok": False,
                "error": "asset and price required"
            }), 400

        price = float(price)

        with lock:
            market_data[asset]["prices"].append(price)
            market_data[asset]["timestamps"].append(timestamp)
            market_data[asset]["last_price"] = price
            market_data[asset]["updated"] = time.time()

        return jsonify({
            "ok": True,
            "asset": asset,
            "price": price
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# ============================================================
# SIGNAL API
# ============================================================

@app.route("/api/signal")
def api_signal():

    asset = request.args.get(
        "asset",
        selected_asset
    )

    timeframe = request.args.get(
        "timeframe",
        selected_timeframe
    )

    with lock:
        signal = generate_signal(
            asset,
            timeframe
        )

    return jsonify(signal)


# ============================================================
# MARKET DATA API
# ============================================================

@app.route("/api/market")
def api_market():

    asset = request.args.get(
        "asset",
        selected_asset
    )

    data = market_data[asset]

    return jsonify({
        "asset": asset,
        "price": data["last_price"],
        "prices": list(data["prices"]),
        "timestamps": list(data["timestamps"]),
        "updated": data["updated"],
    })


# ============================================================
# TRADE LOG API
# ============================================================

@app.route("/api/trades")
def api_trades():

    return jsonify({
        "trades": list(trade_history)
    })


@app.route("/api/trade", methods=["POST"])
def add_trade():

    payload = request.get_json(force=True)

    trade = {
        "id": int(time.time() * 1000),
        "asset": payload.get("asset"),
        "direction": payload.get("direction"),
        "stake": payload.get("stake"),
        "payout": payload.get("payout"),
        "result": payload.get("result"),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    trade_history.appendleft(trade)

    return jsonify({
        "ok": True,
        "trade": trade
    })


# ============================================================
# STATUS
# ============================================================

@app.route("/api/status")
def status():

    active_assets = 0

    for asset, data in market_data.items():

        if data["last_price"] is not None:
            active_assets += 1

    return jsonify({
        "status": "online",
        "engine": "Ryu V2",
        "mode": "SIGNAL ONLY",
        "expiry_minutes": EXPIRY_MINUTES,
        "active_assets": active_assets,
        "server_time": datetime.now(
            timezone.utc
        ).isoformat(),
    })


# ============================================================
# DASHBOARD
# ============================================================

HTML = r"""
<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
content="width=device-width, initial-scale=1">

<title>Ryu V2</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #080808;
    color: white;
    font-family: Arial, sans-serif;
}

.header {
    padding: 18px;
    background: #111;
    border-bottom: 1px solid #292929;
}

.logo {
    font-size: 28px;
    font-weight: bold;
    color: #ff3b30;
}

.subtitle {
    color: #aaa;
    font-size: 12px;
}

.nav {
    display: flex;
    overflow-x: auto;
    background: #101010;
    border-bottom: 1px solid #292929;
}

.nav button {
    flex: 1;
    min-width: 100px;
    padding: 15px;
    background: transparent;
    border: 0;
    color: #aaa;
    font-weight: bold;
}

.nav button.active {
    color: white;
    border-bottom: 2px solid #ff3b30;
}

.container {
    padding: 15px;
    max-width: 1100px;
    margin: auto;
}

.filters {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 15px;
}

select,
.filter {
    background: #151
