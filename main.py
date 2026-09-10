import os
import math
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template_string

# ============================================================
# RYU V2
# SIGNAL-ONLY TRADING DASHBOARD
# ============================================================
#
# This app does NOT place trades.
#
# A live market-data connector can send candles/prices to:
#
# POST /api/feed
#
# Example JSON:
# {
#   "asset": "EUR/USD OTC",
#   "price": 1.08520,
#   "timestamp": 1757470000
# }
#
# ============================================================

app = Flask(__name__)

# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

MAX_CANDLES = 300

TIMEFRAMES = {
    "1m": 60,
    "2m": 120,
    "3m": 180,
}

# User requested 5-minute expiry for testing.
EXPIRY_MINUTES = 5

# ------------------------------------------------------------
# DATA STORAGE
# ------------------------------------------------------------

market_data = defaultdict(
    lambda: deque(maxlen=MAX_CANDLES)
)

latest_prices = {}

signals = deque(maxlen=100)

stats = {
    "signals": 0,
    "wins": 0,
    "losses": 0,
}

data_lock = threading.Lock()


# ------------------------------------------------------------
# INDICATORS
# ------------------------------------------------------------

def sma(values, period):
    if len(values) < period:
        return None

    return sum(values[-period:]) / period


def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    result
