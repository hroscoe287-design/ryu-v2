import os
import math
import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)


# ============================================================
# RYU V2
# SIGNAL-ONLY DASHBOARD
# Does NOT place trades.
# ============================================================

ASSETS = {
    "Forex": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "JPY=X",
        "AUD/USD": "AUDUSD=X",
    },
    "Crypto": {
        "BTC/USDT": "BTC-USD",
        "ETH/USDT": "ETH-USD",
        "SOL/USDT": "SOL-USD",
        "XRP/USDT": "XRP-USD",
    },
    "Stocks": {
        "AAPL": "AAPL",
        "TSLA": "TSLA",
        "NVDA": "NVDA",
        "AMZN": "AMZN",
        "SPY": "SPY",
        "QQQ": "QQQ",
    },
}


def get_asset_symbol(asset):
    for group in ASSETS.values():
        if asset in group:
            return group[asset]
    return None


def get_market_data(asset, period="1d", interval="1m"):
    symbol = get_asset_symbol(asset)

    if not symbol:
        return None

    try:
        data = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
        )

        if data is None or data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close"]

        for column in required:
            if column not in data.columns:
                return None

        data = data.dropna(subset=required).copy()

        if len(data) < 20:
            return None

        return data

    except Exception:
        return None


def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()


def calculate_rsi(close, length=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


def calculate_macd(close):
    fast = ema(close, 12)
    slow = ema(close, 26)

    macd = fast - slow
    signal = ema(macd, 9)

    return macd, signal


def calculate_bollinger(close, length=20):
    middle = close.rolling(length).mean()
    std = close.rolling(length).std()

    upper = middle + (std * 2)
    lower = middle - (std * 2)

    return upper, middle, lower


def calculate_atr(data, length=14):
    high = data["High"]
    low = data["Low"]
    close = data["Close"]

    previous_close = close.shift(1)

    ranges = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )

    true_range = ranges.max(axis=1)

    return true_range.rolling(length).mean()


def generate_signal(data):
    close = data["Close"]

    current = float(close.iloc[-1])

    ema9 = ema(close, 9)
    ema21 = ema(close, 21)
    ema50 = ema(close, 50)

    rsi = calculate_rsi(close)

    macd, macd_signal = calculate_macd(close)

    upper, middle, lower = calculate_bollinger(close)

    atr = calculate_atr(data)

    score_call = 0
    score_put = 0

    confirmations = []

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if current > float(ema9.iloc[-1]):
        score_call += 1
        confirmations.append("Price above EMA 9")
    else:
        score_put += 1
        confirmations.append("Price below EMA 9")

    if float(ema9.iloc[-1]) > float(ema21.iloc[-1]):
        score_call += 1
        confirmations.append("EMA 9 above EMA 21")
    else:
        score_put += 1
        confirmations.append("EMA 9 below EMA 21")

    if float(ema21.iloc[-1]) > float(ema50.iloc[-1]):
        score_call += 1
        confirmations.append("EMA trend bullish")
    else:
        score_put += 1
        confirmations.append("EMA trend bearish")

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    current_rsi = float(rsi.iloc[-1])

    if 50 <= current_rsi <= 70:
        score_call += 1
        confirmations.append("RSI bullish")
    elif 30 <= current_rsi < 50:
        score_put += 1
        confirmations.append("RSI bearish")

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    current_macd = float(macd.iloc[-1])
    current_macd_signal = float(macd_signal.iloc[-1])

    if current_macd > current_macd_signal:
        score_call += 1
        confirmations.append("MACD bullish")
    else:
        score_put += 1
        confirmations.append("MACD bearish")

    # --------------------------------------------------------
    # BOLLINGER
    # --------------------------------------------------------

    current_upper = float(upper.iloc[-1])
    current_lower = float(lower.iloc[-1])

    if current > float(middle.iloc[-1]) and current < current_upper:
        score_call += 1
        confirmations.append("Bollinger bullish zone")

    elif current < float(middle.iloc[-1]) and current > current_lower:
        score_put += 1
        confirmations.append("Bollinger bearish zone")

    # --------------------------------------------------------
    # FINAL DECISION
    # --------------------------------------------------------

    total = max(score_call, score_put)

    if total < 4:
        direction = "WAIT"
    elif score_call > score_put:
        direction = "CALL"
    elif score_put > score_call:
        direction = "PUT"
    else:
        direction = "WAIT"

    confidence = int(
        min(
            98,
            max(
                50,
                50 + abs(score_call - score_put) * 8
            )
        )
    )

    if direction == "WAIT":
        confidence = min(confidence, 59)

    payout = 0

    # Demo/display payout estimate only.
    # Actual Pocket Option payout can differ.
    if direction != "WAIT":
        payout = random.choice([70, 75, 80, 85, 90])

    volatility = float(atr.iloc[-1]) if not math.isnan(float(atr.iloc[-1])) else 0

    return {
        "direction": direction,
        "confidence": confidence,
        "price": round(current, 6),
        "payout": payout,
        "score_call": score_call,
        "score_put": score_put,
        "rsi": round(current_rsi, 2),
        "atr": round(volatility, 6),
        "confirmations": confirmations[-6:],
    }


def fallback_signal(asset):
    return {
        "direction": "WAIT",
        "confidence": 50,
        "price": 0,
        "payout": 0,
        "score_call": 0,
        "score_put": 0,
        "rsi": 50,
        "atr": 0,
        "confirmations": [
            "Market data unavailable",
            "Waiting for data",
        ],
    }


def make_chart(data):
    if data is None or data.empty:
        return []

    recent = data.tail(40)

    result = []

    for index, row in recent.iterrows():
        try:
            timestamp = str(index)

            if hasattr(index, "strftime"):
                timestamp = index.strftime("%H:%M")

            result.append(
                {
                    "time": timestamp,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                }
            )

        except Exception:
            continue

    return result


# ============================================================
# DASHBOARD HTML
# ============================================================

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>Ryu V2</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background:
        radial-gradient(circle at top, #241111 0%, #090909 45%, #030303 100%);
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
}

.header {
    padding: 18px;
    border-bottom: 1px solid #333;
    background: rgba(0,0,0,.8);
    position: sticky;
    top: 0;
    z-index: 10;
}

.brand {
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 2px;
}

.brand span {
    color: #ff3131;
}

.status {
    color: #00ff7f;
    font-size: 12px;
    margin-top: 5px;
}

.nav {
    display: flex;
    gap: 8px;
    margin-top: 15px;
    overflow-x: auto;
}

.nav button,
.filter button {
    background: #151515;
    color: white;
    border: 1px solid #444;
    border-radius: 8px;
    padding: 10px 14px;
    cursor: pointer;
}

.nav button.active,
.filter button.active {
    background: #b90000;
    border-color: #ff3333;
}

.container {
    max-width: 1200px;
    margin: auto;
    padding: 15px;
}

.filters {
    display: grid;
    gap: 10px;
    margin-bottom: 15px;
}

.filter {
    display: flex;
    gap: 7px;
    overflow-x: auto;
}

select {
    width: 100%;
    padding: 13px;
    background: #111;
    color: white;
    border: 1px solid #444;
    border-radius: 8px;
}

.grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 15px;
}

.card {
    background: rgba(16,16,16,.94);
    border: 1px solid #333;
    border-radius: 15px;
    padding: 18px;
    box-shadow: 0 8px 30px rgba(0,0,0,.4);
}

.signal-card {
    text-align: center;
}

.signal {
    font-size: 48px;
    font-weight: 900;
    margin: 15px 0;
}

.call {
    color: #00ff88;
}

.put {
    color: #ff3030;
}

.wait {
    color: #ffd43b;
}

.confidence {
    font-size: 22px;
    font-weight: bold;
}

.metric-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-top: 15px;
}

.metric {
    background: #0d0d0d;
    border: 1px solid #292929;
    border-radius: 10px;
    padding: 12px;
}

.metric small {
    color: #888;
    display: block;
}

.metric strong {
    font-size: 18px;
}

.chart {
    width: 100%;
    height: 260px;
    background: #080808;
    border-radius: 10px;
    border: 1px solid #292929;
    overflow: hidden;
}

svg {
    width: 100%;
    height: 100%;
}

.confluence {
    margin-top: 10px;
}

.confirm {
    padding: 9px;
    margin-top: 6px;
    background: #101010;
    border-left: 3px solid #ff3030;
    border-radius: 5px;
    font-size: 13px;
}

.footer {
    text-align: center;
    color: #666;
    padding: 30px 10px;
    font-size: 12px;
}

@media (min-width: 800px) {

    .grid {
        grid-template-columns: 1fr 1fr;
    }

    .signal-card {
        grid-row: span 2;
    }

}

</style>
</head>

<body>

<div class="header">

    <div class="brand">
        RYU <span>V2</span>
    </div>

    <div class="status">
        ● SIGNAL
