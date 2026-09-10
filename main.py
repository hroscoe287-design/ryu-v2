import os
import math
import time
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

try:
    import yfinance as yf
except Exception:
    yf = None

try:
    import pandas as pd
    import numpy as np
except Exception:
    pd = None
    np = None


# ============================================================
# RYU V2 - PRODUCTION DASHBOARD
# ============================================================

app = Flask(__name__)

APP_NAME = "RYU V2"
VERSION = "2.0 Production"

# ------------------------------------------------------------
# Asset universe
# ------------------------------------------------------------

ASSETS = {
    "FOREX": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "JPY=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "CAD=X",
        "USD/CHF": "CHF=X",
        "NZD/USD": "NZDUSD=X",
        "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X",
        "GBP/JPY": "GBPJPY=X",
    },
    "CRYPTO": {
        "BTC/USD": "BTC-USD",
        "ETH/USD": "ETH-USD",
        "SOL/USD": "SOL-USD",
        "XRP/USD": "XRP-USD",
        "DOGE/USD": "DOGE-USD",
        "ADA/USD": "ADA-USD",
        "AVAX/USD": "AVAX-USD",
        "LINK/USD": "LINK-USD",
        "LTC/USD": "LTC-USD",
        "BCH/USD": "BCH-USD",
        "DOT/USD": "DOT-USD",
        "SHIB/USD": "SHIB-USD",
    },
    "STOCKS": {
        "AAPL": "AAPL",
        "TSLA": "TSLA",
        "NVDA": "NVDA",
        "AMZN": "AMZN",
        "MSFT": "MSFT",
        "META": "META",
        "GOOGL": "GOOGL",
        "NFLX": "NFLX",
        "AMD": "AMD",
        "INTC": "INTC",
        "COIN": "COIN",
        "PLTR": "PLTR",
    },
    "ETFs": {
        "SPY": "SPY",
        "QQQ": "QQQ",
        "IWM": "IWM",
        "DIA": "DIA",
        "GLD": "GLD",
        "SLV": "SLV",
    },
}

# ------------------------------------------------------------
# Runtime configuration
# ------------------------------------------------------------

CONFIG = {
    "category": "FOREX",
    "symbol": "EUR/USD",
    "timeframe": "1m",
    "expiry": 5,
    "payout": 80,
    "minimum_confidence": 65,
}

STATE = {
    "last_signal": None,
    "last_update": None,
    "history": [],
}

STATE_LOCK = threading.Lock()


# ============================================================
# INDICATORS
# ============================================================

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def sma(series, period):
    return series.rolling(period).mean()


def rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    value = 100 - (100 / (1 + rs))

    return value.fillna(50)


def macd(series):
    fast = ema(series, 12)
    slow = ema(series, 26)

    line = fast - slow
    signal = ema(line, 9)
    histogram = line - signal

    return line, signal, histogram


def bollinger(series, period=20, deviations=2):
    middle = sma(series, period)
    std = series.rolling(period).std()

    upper = middle + deviations * std
    lower = middle - deviations * std

    return middle, upper, lower


def atr(df, period=14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    previous_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - previous_close).abs()
    tr3 = (low - previous_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return true_range.ewm(alpha=1 / period, adjust=False).mean()


def stochastic(df, period=14):
   
