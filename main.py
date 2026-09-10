import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

APP_NAME = "RYU V2"
EXPIRY = "5 minutes"

MARKETS = {
    "Forex": [
        "EUR/USD OTC",
        "GBP/USD OTC",
        "USD/JPY OTC",
        "AUD/USD OTC",
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
    ],
}

state = {
    "asset": "EUR/USD OTC",
    "timeframe": "1m",
    "signal": "WAIT",
    "confidence": 0,
    "payout": 80,
    "price": 0,
    "feed": False,
    "updated": "Waiting for feed",
    "candles": [],
}


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def make_signal():
    candles = state["candles"]

    if len(candles) < 5:
        return "WAIT", 0

    try:
        closes = [float(c["close"]) for c in candles[-30:]]
    except (KeyError, TypeError, ValueError):
        return "WAIT", 0

    if len(closes) < 5:
        return "WAIT", 0

    short = sum(closes[-5:]) / 5
    long = sum(closes) / len(closes)
    momentum = closes[-1] - closes[-4]

    if short > long and momentum > 0:
        confidence = min(95, 60 + int(abs(momentum) / max(closes[-1], 1) * 10000))
        return "CALL", confidence

    if short < long and momentum < 0:
        confidence = min(95, 60 + int(abs(momentum) / max(closes[-1], 1) * 10000))
        return "PUT", confidence

    return "WAIT", 35


PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RYU V2</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #070b12;
    color: #ffffff;
    font-family: Arial, sans-serif;
}

.header {
    background: #0c121c;
    border-bottom: 1px solid #263447;
    padding: 18px;
}

.logo {
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 3px;
}

.subtitle {
    color: #8d9bad;
    font-size: 12px;
    margin-top: 5px;
}

.fire {
    font-size: 30px;
}

.nav {
    display: flex;
    gap: 8px;
    margin-top: 15px;
    overflow-x: auto;
}

.nav span {
    padding: 10px 14px;
    background: #121b29;
    border: 1px solid #28374b;
    border-radius: 10px;
    font-size: 13px;
    white-space: nowrap;
}

.nav .active {
    background: #20334b;
    color: white;
}

.container {
    max-width: 1200px;
    margin: auto;
    padding: 15px;
}

.controls {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
}

.card {
    background: #0d141f;
    border: 1px solid #1e2b3d;
    border-radius: 15px;
    padding: 15px;
}

label {
    display: block;
    color: #8290a2;
    font-size: 11px;
    text-transform: uppercase;
    margin-bottom: 7px;
}

select {
    width: 100%;
    padding: 12px;
    border-radius: 10px;
    border: 1px solid #304158;
    background: #111a27;
    color: white;
}

.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.signal-card {
    min-height: 230px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.signal {
    font-size: 55px;
    font-weight: 1000;
    margin: 12px;
}

.call {
    color: #39e58c;
}

.put {
    color: #ff5964;
}

.wait {
    color: #ffc857;
}

.confidence {
    font-size: 17px;
    font-weight: bold;
}

.progress {
    width: 80%;
    height: 10px;
    background: #182536;
    border-radius: 20px;
    margin-top: 12px;
    overflow: hidden;
}

.progress-bar {
    height: 100%;
    width: 0%;
    background: #39e58c;
}

.row {
    display: flex;
    justify-content: space-between;
    padding: 11px 0;
    border-bottom: 1px solid #1b2737;
}

.big {
    font-size: 22px;
    font-weight: bold;
}

.status {
    display: flex;
    align-items: center;
    gap: 9px;
}

.dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #ff5964;
}

.dot.live {
    background: #39e58c;
}

.chart-card {
    grid-column: 1 / -1;
}

.chart {
    width: 100%;
    height: 280px;
    background: #080d14;
    border-radius: 12px;
    margin-top: 12px;
}

@media (max-width: 700px) {
    .grid {
        grid-template-columns: 1fr;
    }

    .chart-card {
        grid-column: auto;
    }
}
</style>
</head>

<body>

<div class="header">
    <div class="logo">
        <span class="fire">🔥</span> RYU V2
    </div>

    <div class="subtitle">
        SIGNAL ENGINE • 5 MINUTE EXPIRY • SIGNALS ONLY
    </div>

    <div class="nav">
        <span class="active">Signals</span>
        <span>Trades</span>
        <span>Performance</span>
        <span>Settings</span>
    </div>
</div>

<div class="container">

    <div class="controls">

        <div class="card">
            <label>Market</label>
            <select id="asset"></select>
        </div>

        <div class="card">
            <label>Signal Timeframe</label>

            <select id="timeframe">
                <option value="1m">1 Minute</option>
                <option value="2m">2 Minutes</option>
                <option value="3m">3 Minutes</option>
            </select>
        </div>

    </div>

    <div class="grid">

        <div class="card signal-card">

            <label>RYU SIGNAL</label>

            <div id="signal" class="signal wait">
                WAIT
            </div>

            <div id="confidence" class="confidence">
                Confidence: 0%
            </div>

            <div class="progress">
                <div id="progress" class="progress-bar"></div>
            </div>

        </div>

        <div class="card">

            <label>Trade Setup</label>

            <div class="row">
                <span>Asset</span>
                <b id="setupAsset">EUR/USD OTC</b>
            </div>

            <div class="row">
                <span>Entry</span>
                <b id="entry">—</b>
            </div>

            <div class="row">
                <span>Payout</span>
                <b id="payout">80%</b>
            </div>

            <div class="row">
                <span>Expiry</span>
                <b>5 Minutes</b>
            </div>

        </div>

        <div class="card chart-card">

            <div class="status">
                <span id="dot" class="dot"></span>
                <b id="feedStatus">WAITING FOR LIVE FEED</b>
            </div>

            <div class="chart">
                <canvas id="chart"></canvas>
            </div>

        </div>

        <div class="card">

            <label>Confluence</label>

            <div class="row">
                <span>Trend</span>
                <b id="trend">WAIT</b>
            </div>

            <div class="row">
