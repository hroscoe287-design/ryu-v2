import os
import math
import random
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template_string

# ============================================================
# RYU V2
# COMPLETE SIGNAL DASHBOARD
# ============================================================
#
# SIGNAL ONLY.
# This application does NOT place Pocket Option trades.
#
# Render start command:
#     gunicorn main:app
#
# Optional environment variables:
#     RYU_NAME=RYU V2
#     RYU_DEMO=true
#     DEFAULT_PAYOUT=80
#     SIGNAL_THRESHOLD=68
# ============================================================

app = Flask(__name__)

RYU_NAME = os.getenv("RYU_NAME", "RYU V2")
DEMO_MODE = os.getenv("RYU_DEMO", "true").lower() not in (
    "false",
    "0",
    "no",
)

DEFAULT_PAYOUT = float(os.getenv("DEFAULT_PAYOUT", "80"))
SIGNAL_THRESHOLD = float(os.getenv("SIGNAL_THRESHOLD", "68"))

lock = threading.Lock()

market_data = defaultdict(lambda: deque(maxlen=240))
latest_signal = {}
trade_log = deque(maxlen=200)

feed_status = {
    "connected": False,
    "last_update": None,
    "source": "RYU Demo Market Engine" if DEMO_MODE else "Waiting for feed",
}


# ============================================================
# ASSETS
# ============================================================

ASSETS = {
    "Forex": [
        "EUR/USD OTC",
        "GBP/USD OTC",
        "USD/JPY OTC",
        "AUD/USD OTC",
        "USD/CAD OTC",
        "USD/CHF OTC",
        "EUR/GBP OTC",
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


# ============================================================
# HELPERS
# ============================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def seed_prices(asset):
    prices = {
        "BTC/USD OTC": 65000.0,
        "ETH/USD OTC": 3200.0,
        "SOL/USD OTC": 145.0,
        "XRP/USD OTC": 0.62,

        "EUR/USD OTC": 1.1050,
        "GBP/USD OTC": 1.3100,
        "USD/JPY OTC": 147.5,
        "AUD/USD OTC": 0.6650,
        "USD/CAD OTC": 1.3600,
        "USD/CHF OTC": 0.8850,
        "EUR/GBP OTC": 0.8440,

        "AAPL OTC": 225.0,
        "TSLA OTC": 245.0,
        "NVDA OTC": 180.0,
        "AMZN OTC": 230.0,
        "SPY OTC": 650.0,
        "QQQ OTC": 575.0,
    }

    return prices.get(asset, 100.0)


def make_demo_candle(asset, previous=None):
    if previous is None:
        previous = seed_prices(asset)

    volatility = max(previous * 0.0009, 0.00005)

    change = random.gauss(0, volatility)

    close = max(previous + change, 0.00001)

    high = max(previous, close) + abs(
        random.gauss(0, volatility * 0.55)
    )

    low = min(previous, close) - abs(
        random.gauss(0, volatility * 0.55)
    )

    return {
        "time": int(time.time()),
        "open": previous,
        "high": high,
        "low": max(low, 0.000001),
        "close": close,
    }


# ============================================================
# INDICATORS
# ============================================================

def sma(values, period):
    if not values:
        return 0.0

    sample = values[-period:]

    return sum(sample) / len(sample)


def ema(values, period):
    if not values:
        return 0.0

    multiplier = 2 / (period + 1)

    result = values[0]

    for value in values[1:]:
        result = (
            value * multiplier
            + result * (1 - multiplier)
        )

    return result


def rsi(values, period=14):
    if len(values) < 2:
        return 50.0

    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    recent = changes[-period:]

    gains = sum(
        max(change, 0)
        for change in recent
    ) / max(len(recent), 1)

    losses = sum(
        max(-change, 0)
        for change in recent
    ) / max(len(recent), 1)

    if losses == 0:
        return 100.0

    relative_strength = gains / losses

    return 100 - (
        100 / (1 + relative_strength)
    )


def macd_values(values):
    fast = ema(values, 12)
    slow = ema(values, 26)

    macd = fast - slow

    recent = values[-35:] if len(values) >= 35 else values

    signal = ema(recent, 9)

    return macd, signal


def bollinger(values, period=20):
    if not values:
        return 0.0, 0.0, 0.0

    sample = values[-period:]

    middle = sum(sample) / len(sample)

    variance = sum(
        (value - middle) ** 2
        for value in sample
    ) / len(sample)

    deviation = math.sqrt(variance)

    lower = middle - (2 * deviation)
    upper = middle + (2 * deviation)

    return lower, middle, upper


def alligator(values):
    """
    Lightweight Williams Alligator-style lines.

    Jaw   = 13
    Teeth = 8
    Lips  = 5
    """

    jaw = sma(values, 13)
    teeth = sma(values, 8)
    lips = sma(values, 5)

    return jaw, teeth, lips


# ============================================================
# RYU SIGNAL ENGINE
# ============================================================

def analyze(asset, timeframe):
    with lock:
        candles = list(market_data[asset])

    closes = [
        candle["close"]
        for candle in candles
    ]

    if len(closes) < 12:
        return {
            "direction": "WAIT",
            "confidence": 50,
            "entry": (
                closes[-1]
                if closes
                else seed_prices(asset)
            ),
            "reason": "Building market history",
            "confluence": [
                "Waiting for more candles"
            ],
            "timeframe": timeframe,
            "expiry": "5m",
            "payout": DEFAULT_PAYOUT,
        }

    price = closes[-1]

    fast_ma = sma(closes, 5)
    slow_ma = sma(closes, 20)

    current_rsi = rsi(closes)

    macd, macd_signal = macd_values(closes)

    bb_low, bb_mid, bb_high = bollinger(closes)

    jaw, teeth, lips = alligator(closes)

    call_score = 0
    put_score = 0

    call_reasons = []
    put_reasons = []

    # --------------------------------------------------------
    # PRICE / FAST MA
    # --------------------------------------------------------

    if price > fast_ma:
        call_score += 1
        call_reasons.append(
            "Price above fast MA"
        )
    else:
        put_score += 1
        put_reasons.append(
            "Price below fast MA"
        )

    # --------------------------------------------------------
    # MOVING AVERAGE TREND
    # --------------------------------------------------------

    if fast_ma > slow_ma:
        call_score += 1
        call_reasons.append(
            "MA trend bullish"
        )
    else:
        put_score += 1
        put_reasons.append(
            "MA trend bearish"
        )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if macd > macd_signal:
        call_score += 1
        call_reasons.append(
            "MACD bullish"
        )
    else:
        put_score += 1
        put_reasons.append(
            "MACD bearish"
        )

    # --------------------------------------------------------
    # ALLIGATOR
    # --------------------------------------------------------

    if lips > teeth > jaw:
        call_score += 2
        call_reasons.append(
            "Alligator aligned bullish"
        )

    elif lips < teeth < jaw:
        put_score += 2
        put_reasons.append(
            "Alligator aligned bearish"
        )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if current_rsi < 35:
        call_score += 1
        call_reasons.append(
            "RSI recovering from low"
        )

    elif current_rsi > 65:
        put_score += 1
        put_reasons.append(
            "RSI cooling from high"
        )

    # --------------------------------------------------------
    # BOLLINGER
    # --------------------------------------------------------

    if price <= bb_low:
        call_score += 1
        call_reasons.append(
            "Near lower Bollinger band"
        )

    elif price >= bb_high:
        put_score += 1
        put_reasons.append(
            "Near upper Bollinger band"
        )

    # --------------------------------------------------------
    # FINAL DIRECTION
    # --------------------------------------------------------

    if call_score > put_score:
        direction = "CALL"
        strength = call_score
        reasons = call_reasons

    elif put_score > call_score:
        direction = "PUT"
        strength = put_score
        reasons = put_reasons

    else:
        direction = "WAIT"
        strength = 0
        reasons = [
            "Confluence is mixed"
        ]

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence = min(
        97,
        55 + int((strength / 8) * 42)
    )

    if confidence < SIGNAL_THRESHOLD:
        direction = "WAIT"
        reasons = [
            "Setup below Ryu confidence threshold"
        ]

    return {
        "direction": direction,
        "confidence": confidence,
        "entry": price,
        "reason": " • ".join(reasons[:3]),
        "confluence": reasons[:6],

        "rsi": round(current_rsi, 1),

        "ma_fast": fast_ma,
        "ma_slow": slow_ma,

        "macd": macd,
        "macd_signal": macd_signal,

        "bb_low": bb_low,
        "bb_mid": bb_mid,
        "bb_high": bb_high,

        "alligator": {
            "jaw": jaw,
            "teeth": teeth,
            "lips": lips,
        },

        "timeframe": timeframe,

        # USER REQUESTED EXPIRY
        "expiry": "5m",

        "payout": DEFAULT_PAYOUT,
    }


# ============================================================
# DEMO MARKET ENGINE
# ============================================================

def demo_worker():
    while True:

        try:

            for category in ASSETS.values():

                for asset in category:

                    with lock:

                        if market_data[asset]:

                            previous = (
                                market_data[asset][-1]["close"]
                            )

                        else:

                            previous = seed_prices(asset)

                        candle = make_demo_candle(
                            asset,
                            previous
                        )

                        market_data[asset].append(
                            candle
                        )

                        feed_status[
                            "last_update"
                        ] = now_iso()

                        feed_status[
                            "connected"
                        ] = True

                        feed_status[
                            "source"
                        ] = "RYU Demo Market Engine"

                    signal = analyze(
                        asset,
                        "1m"
                    )

                    with lock:
                        latest_signal[asset] = signal

            time.sleep(2)

        except Exception:
            time.sleep(2)


if DEMO_MODE:

    threading.Thread(
        target=demo_worker,
        daemon=True
    ).start()


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def index():

    return render_template_string(
        PAGE,
        ryu_name=RYU_NAME
    )


@app.get("/api/health")
def health():

    return jsonify({
        "ok": True,
        "name": RYU_NAME,
        "demo_mode": DEMO_MODE,
        "feed": feed_status,
        "time": now_iso(),
    })


@app.get("/api/assets")
def assets():

    return jsonify
