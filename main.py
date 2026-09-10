import os
import math
import time
import threading
from collections import deque
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template_string


# ============================================================
# RYU V2
# SIMPLE RENDER BUILD
# SIGNAL DASHBOARD ONLY
# ============================================================

app = Flask(__name__)

PORT = int(os.environ.get("PORT", "10000"))

# Test expiry requested for Ryu V2.
EXPIRY_MINUTES = 5

# Supported display markets.
MARKETS = {
    "Forex": [
        "EUR/USD OTC",
        "GBP/USD OTC",
        "USD/JPY OTC",
        "AUD/USD OTC",
        "USD/CAD OTC",
        "USD/CHF OTC",
    ],
    "Crypto": [
        "BTC/USD OTC",
        "ETH/USD OTC",
        "SOL/USD OTC",
        "XRP/USD OTC",
    ],
    "Stocks": [
        "AAPL OTC",
        "TSLA OTC",
        "NVDA OTC",
        "AMZN OTC",
        "SPY OTC",
        "QQQ OTC",
    ],
}

# In-memory candle storage.
# A real connector can POST candles into /api/feed.
CANDLES = {}
LOCK = threading.Lock()

MAX_CANDLES = 300


# ============================================================
# HELPERS
# ============================================================

def now_utc():
    return datetime.now(timezone.utc)


def iso_now():
    return now_utc().isoformat()


def clamp(value, low, high):
    return max(low, min(high, value))


def safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def asset_category(asset):
    for category, assets in MARKETS.items():
        if asset in assets:
            return category
    return "Forex"


def ensure_asset(asset):
    if not asset:
        asset = MARKETS["Forex"][0]

    for assets in MARKETS.values():
        if asset in assets:
            return asset

    return MARKETS["Forex"][0]


def get_candles(asset):
    with LOCK:
        return list(CANDLES.get(asset, []))


def add_candle(asset, candle):
    required = ["time", "open", "high", "low", "close"]

    for key in required:
        if key not in candle:
            return False

    clean = {
        "time": candle["time"],
        "open": safe_float(candle["open"]),
        "high": safe_float(candle["high"]),
        "low": safe_float(candle["low"]),
        "close": safe_float(candle["close"]),
    }

    if any(clean[k] is None for k in ["open", "high", "low", "close"]):
        return False

    with LOCK:
        if asset not in CANDLES:
            CANDLES[asset] = deque(maxlen=MAX_CANDLES)

        CANDLES[asset].append(clean)

    return True


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values, period):
    if not values:
        return None

    period = max(1, int(period))

    if len(values) < period:
        return sum(values) / len(values)

    multiplier = 2 / (period + 1)
    result = sum(values[:period]) / period

    for value in values[period:]:
        result = (value - result) * multiplier + result

    return result


def rsi(values, period=14):
    if len(values) < period + 1:
        return 50.0

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
    return 100 - (100 / (1 + rs))


def macd(values):
    if len(values) < 26:
        return 0.0, 0.0, 0.0

    fast = ema(values, 12)
    slow = ema(values, 26)

    if fast is None or slow is None:
        return 0.0, 0.0, 0.0

    line = fast - slow

    # Approximation for a lightweight engine.
    signal = ema(values[-9:], 9)

    if signal is None:
        signal = 0.0

    histogram = line - signal

    return line, signal, histogram


def bollinger(values, period=20, multiplier=2):
    if len(values) < period:
        return None, None, None

    window = values[-period:]
    middle = sum(window) / period

    variance = sum((x - middle) ** 2 for x in window) / period
    deviation = math.sqrt(variance)

    upper = middle + multiplier * deviation
    lower = middle - multiplier * deviation

    return upper, middle, lower


# ============================================================
# RYU SIGNAL ENGINE
# ============================================================

def calculate_signal(asset, timeframe):
    candles = get_candles(asset)

    if not candles:
        return {
            "signal": "WAIT",
            "confidence": 0,
            "entry": None,
            "payout": 0,
            "confluence": ["Waiting for live market feed"],
            "reason": "No candle data received yet.",
            "expiry": EXPIRY_MINUTES,
            "timeframe": timeframe,
            "asset": asset,
            "generated_at": iso_now(),
        }

    closes = [c["close"] for c in candles]

    entry = closes[-1]

    if len(closes) < 20:
        return {
            "signal": "WAIT",
            "confidence": 0,
            "entry": entry,
            "payout": 0,
            "confluence": [
                "Collecting candles",
                "Minimum data not reached",
            ],
            "reason": "Ryu is waiting for enough market data.",
            "expiry": EXPIRY_MINUTES,
            "timeframe": timeframe,
            "asset": asset,
            "generated_at": iso_now(),
        }

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    rsi_value = rsi(closes, 14)
    macd_line, macd_signal, macd_hist = macd(closes)

    upper, middle, lower = bollinger(closes, 20, 2)

    # Lightweight Alligator-style calculation.
    jaw = sma(closes, 13)
    teeth = sma(closes, 8)
    lips = sma(closes, 5)

    score_call = 0
    score_put = 0
    confluence = []

    # EMA trend.
    if ema9 is not None and ema21 is not None:
        if ema9 > ema21:
            score_call += 2
            confluence.append("EMA bullish")
        elif ema9 < ema21:
            score_put += 2
            confluence.append("EMA bearish")

    # Alligator-style alignment.
    if jaw is not None and teeth is not None and lips is not None:
        if lips > teeth > jaw:
            score_call += 2
            confluence.append("Alligator bullish")
        elif lips < teeth < jaw:
            score_put += 2
            confluence.append("Alligator bearish")

    # RSI.
    if rsi_value >= 55:
        score_call += 1
        confluence.append("RSI bullish")
    elif rsi_value <= 45:
        score_put += 1
        confluence.append("RSI bearish")

    # MACD.
    if macd_hist > 0:
        score_call += 1
        confluence.append("MACD bullish")
    elif macd_hist < 0:
        score_put += 1
        confluence.append("MACD bearish")

    # Bollinger position.
    if upper is not None and lower is not None:
        if entry > middle:
            score_call += 1
            confluence.append("Price above BB midline")
        elif entry < middle:
            score_put += 1
            confluence.append("Price below BB midline")

    total = score_call + score_put

    if total == 0:
        confidence = 0
        direction = "WAIT"
    elif score_call >= score_put + 2:
        direction = "CALL"
        confidence = int(clamp(55 + score_call * 6, 55, 94))
    elif score_put >= score_call + 2:
        direction = "PUT"
        confidence = int(clamp(55 + score_put * 6, 55, 94))
    else:
        direction = "WAIT"
        confidence = int(clamp(50 + abs(score_call - score_put) * 5, 50, 69))

    # Don't claim a strong setup without enough confirmations.
    if direction != "WAIT" and confidence < 70:
        direction = "WAIT"

    if not confluence:
        confluence = ["No strong confluence"]

    return {
        "signal": direction,
        "confidence": confidence,
        "entry": round(entry, 8),
        "payout": 0,
        "confluence": confluence,
        "reason": (
            "Bullish confluence detected."
            if direction == "CALL"
            else "Bearish confluence detected."
            if direction == "PUT"
            else "Ryu is waiting for stronger confirmation."
        ),
        "expiry": EXPIRY_MINUTES,
        "timeframe": timeframe,
        "asset": asset,
        "generated_at": iso_now(),
        "indicators": {
            "ema9": round(ema9, 8) if ema9 is not None else None,
            "ema21": round(ema21, 8) if ema21 is not None else None,
            "rsi": round(rsi_value, 2),
            "macd": round(macd_line, 8),
            "macd_signal": round(macd_signal, 8),
            "macd_histogram": round(macd_hist, 8),
            "alligator_jaw": round(jaw, 8) if jaw is not None else None,
            "alligator_teeth": round(teeth, 8) if teeth is not None else None,
            "alligator_lips": round(lips, 8) if lips is not None else None,
        },
    }


# ============================================================
# DEMO DATA
# ============================================================

def seed_demo_data():
    """
    Creates a small synthetic chart so the dashboard is not blank
    immediately after deployment.

    This is NOT Pocket Option data.
    It is only visual/demo data until /api/feed receives candles.
    """

    base_values = {
        "EUR/USD OTC": 1.0850,
        "GBP/USD OTC": 1.2750,
        "USD/JPY OTC": 147.20,
        "AUD/USD OTC": 0.6520,
        "USD/CAD OTC": 1.3600,
        "USD/CHF OTC": 0.8750,
        "BTC/USD OTC": 105000.0,
        "ETH/USD OTC": 3900.0,
        "SOL/USD OTC": 220.0,
        "XRP/USD OTC": 2.40,
        "AAPL OTC": 230.0,
        "TSLA OTC": 330.0,
        "NVDA OTC": 175.0,
        "AMZN OTC": 230.0,
        "SPY OTC": 650.0,
        "QQQ OTC": 580.0,
    }

    for asset, base in base_values.items():
        value = base

        for i in range(60):
            wave = math.sin(i / 5) * base * 0.0007
            drift = math.sin(i / 13) * base * 0.00025

            previous = value
            close = previous + wave + drift

            high = max(previous, close) + abs(base) * 0.00025
            low = min(previous, close) - abs(base) * 0.00025

            add_candle(
                asset,
                {
                    "time": int(time.time()) - (60 - i) * 60,
                    "open": previous,
                    "high": high,
                    "low": low,
                    "close": close,
                },
            )

            value = close


seed_demo_data()


# ============================================================
# API ROUTES
# ============================================================

@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "name": "Ryu V2",
        "signal_only": True,
        "expiry_minutes": EXPIRY_MINUTES,
        "time": iso_now(),
    })


@app.route("/api/status")
def api_status():
    with LOCK:
        candle_count = sum(len(v) for v in CANDLES.values())

    return jsonify({
        "status": "online",
        "name": "Ryu V2",
        "signal_only": True,
        "expiry_minutes": EXPIRY_MINUTES,
        "assets": sum(len(v) for v in MARKETS.values()),
        "candle_count": candle_count,
        "time": iso_now(),
    })


@app.route("/api/signal")
def api_signal():
    asset = ensure_asset(request.args.get("asset"))
    timeframe = request.args.get("timeframe", "1m")

    if timeframe not in ("1m", "2m", "3m"):
        timeframe = "1m"

    result = calculate_signal(asset, timeframe)

    # Demo payout display.
    # Real payout should be supplied by the live connector.
    if result["payout"] == 0:
        result["payout"] = 85

    return jsonify(result)


@app.route("/api/chart")
def api_chart():
    asset = ensure_asset(request.args.get("
