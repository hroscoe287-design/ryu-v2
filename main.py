from flask import Flask, jsonify, render_template_string
import math
import time
from datetime import datetime, timezone

app = Flask(__name__)

ASSETS = {
    "Forex": [
        "EUR/USD OTC",
        "GBP/USD OTC",
        "USD/JPY OTC",
        "AUD/USD OTC",
        "USD/CAD OTC",
        "USD/CHF OTC",
        "NZD/USD OTC",
        "EUR/GBP OTC",
    ],
    "Crypto": [
        "BTC/USD OTC",
        "ETH/USD OTC",
        "SOL/USD OTC",
        "XRP/USD OTC",
        "LTC/USD OTC",
        "DOGE/USD OTC",
    ],
    "Stocks": [
        "AAPL OTC",
        "TSLA OTC",
        "NVDA OTC",
        "AMZN OTC",
        "META OTC",
        "MSFT OTC",
        "GOOGL OTC",
    ],
    "Commodities": [
        "Gold OTC",
        "Silver OTC",
        "Oil OTC",
        "Natural Gas OTC",
    ],
}

TIMEFRAMES = [
    "1m",
    "2m",
    "3m",
    "5m",
    "10m",
    "15m",
    "30m",
    "1h",
]

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ryu V2</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #07090d;
    color: #f5f7fb;
    font-family: Arial, Helvetica, sans-serif;
}

.header {
    background: #0d1118;
    border-bottom: 1px solid #252b35;
    padding: 14px;
}

.brand {
    display: flex;
    align-items: center;
    gap: 12px;
}

.logo {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: linear-gradient(135deg, #ff2b2b, #780000);
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 21px;
    font-weight: 900;
    box-shadow: 0 0 20px rgba(255, 30, 30, .35);
}

.brand h1 {
    margin: 0;
    font-size: 22px;
}

.brand span {
    color: #8994a4;
    font-size: 11px;
}

.live {
    margin-left: auto;
    color: #50ff9a;
    font-size: 12px;
}

.container {
    width: 100%;
    max-width: 1200px;
    margin: auto;
    padding: 14px;
}

.nav,
.filters,
.timeframes {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    margin-top: 12px;
}

button {
    border: 1px solid #303744;
    background: #121720;
    color: #aeb8c7;
    padding: 10px 14px;
    border-radius: 9px;
    white-space: nowrap;
    cursor: pointer;
}

button.active {
    background: #b20d0d;
    border-color: #ed2929;
    color: white;
}

.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 12px;
}

.card {
    background: #0e131b;
    border: 1px solid #242b36;
    border-radius: 14px;
    padding: 14px;
}

label {
    display: block;
    color: #8994a4;
    font-size: 11px;
    margin-bottom: 7px;
}

select {
    width: 100%;
    padding: 12px;
    background: #090d13;
    color: white;
    border: 1px solid #303744;
    border-radius: 9px;
}

.chart-card {
    margin-top: 12px;
    padding: 0;
    overflow: hidden;
}

.chart-header {
    padding: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.price {
    font-size: 21px;
    font-weight: bold;
}

.chart {
    height: 320px;
    background:
        linear-gradient(#151b24 1px, transparent 1px),
        linear-gradient(90deg, #151b24 1px, transparent 1px);
    background-size: 50px 50px;
    overflow: hidden;
}

svg {
    width: 100%;
    height: 100%;
}

.signal-grid {
    display: grid;
    grid-template-columns: 1.05fr .95fr;
    gap: 12px;
    margin-top: 12px;
}

.signal-card {
    min-height: 250px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
}

.badge {
    width: 140px;
    height: 140px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 30px;
    font-weight: 900;
    border: 5px solid #777;
    margin: 12px;
}

.call {
    color: #55ff9b;
    background: #06331f;
    border-color: #20dc79;
}

.put {
    color: #ff6868;
    background: #390707;
    border-color: #ed3030;
}

.wait {
    color: #ffd45a;
    background: #332900;
    border-color: #d7a800;
}

.confidence {
    font-size: 24px;
    font-weight: bold;
}

.muted {
    color: #8d98a8;
}

.stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.stat {
    background: #090d13;
    border: 1px solid #252c37;
    border-radius: 10px;
    padding: 12px;
}

.stat span {
    color: #8994a4;
    font-size: 11px;
}

.stat strong {
    display: block;
    margin-top: 5px;
    font-size: 18px;
}

.countdown {
    color: #ff3e3e !important;
    font-size: 25px !important;
}

.confluence {
    margin-top: 12px;
}

.check {
    display: flex;
    justify-content: space-between;
    padding: 11px 0;
    border-bottom: 1px solid #202630;
    font-size: 13px;
}

.good {
    color: #55ef99;
}

.neutral {
    color: #ffd45a;
}

.note {
    margin-top: 12px;
    padding: 11px;
    border-radius: 9px;
    background: #15100a;
    border: 1px solid #4b3512;
    color: #d8c69a;
    font-size: 12px;
    line-height: 1.5;
}

@media (max-width: 760px) {
    .grid,
    .signal-grid {
        grid-template-columns: 1fr;
    }

    .chart {
        height: 270px;
    }
}
</style>
</head>

<body>

<header class="header">
    <div class="brand">
        <div class="logo">R</div>

        <div>
            <h1>RYU V2</h1>
            <span>AI SIGNAL COMMAND CENTER</span>
        </div>

        <div class="live">● LIVE DEMO</div>
    </div>

    <div class="nav">
        <button class="active">Signals</button>
        <button>Trades</button>
        <button>Performance</button>
        <button>Settings</button>
    </div>
</header>

<main class="container">

    <div class="filters">
        <button class="active" onclick="changeMarket('Forex', this)">
            Forex
        </button>

        <button onclick="changeMarket('Crypto', this)">
            Crypto
        </button>

        <button onclick="changeMarket('Stocks', this)">
            Stocks
        </button>

        <button onclick="changeMarket('Commodities', this)">
            Commodities
        </button>
    </div>

    <div class="grid">

        <div class="card">
            <label>ASSET</label>

            <select id="asset"></select>
        </div>

        <div class="card">
            <label>TIMEFRAME</label>

            <select id="timeframe">
                <option>1m</option>
                <option>2m</option>
                <option>3m</option>
                <option>5m</option>
                <option>10m</option>
                <option>15m</option>
                <option>30m</option>
                <option>1h</option>
            </select>
        </div>

    </div>

    <div class="timeframes">

        <button class="active" onclick="changeTimeframe('1m', this)">
            1m
        </button>

        <button onclick="changeTimeframe('2m', this)">
            2m
        </button>

        <button onclick="changeTimeframe('3m', this)">
            3m
        </button>

        <button onclick="changeTimeframe('5m', this)">
            5m
        </button>

        <button onclick="changeTimeframe('10m', this)">
            10m
        </button>

        <button onclick="changeTimeframe('15m', this)">
            15m
        </button>

        <button onclick="changeTimeframe('30m', this)">
            30m
        </button>

        <button onclick="changeTimeframe('1h', this)">
            1h
        </button>

    </div>

    <section class="card chart-card">

        <div class="chart-header">

            <div>
                <strong id="assetName">EUR/USD OTC</strong>
                <div class="muted">
                    Ryu V2 moving demo chart
                </div>
            </div>

            <div class="price" id="price">
                1.08420
            </div>

        </div>

        <div class="chart">
            <svg id="chart"
                 viewBox="0 0 1000 320"
                 preserveAspectRatio="none">
            </svg>
        </div>

    </section>

    <section class="signal-grid">

        <div class="card signal-card">

            <div class="muted">
                RYU V2 SIGNAL
            </div>

            <div id="signalBadge"
                 class="badge wait">
                WAIT
            </div>

            <div id="confidence"
                 class="confidence">
                --% CONFIDENCE
            </div>

            <div id="signalText"
                 class="muted">
                Scanning market conditions...
            </div>

        </div>

        <div class="card">

            <div class="muted">
                TRADE WINDOW
            </div>

            <br>

            <div class="stats">

                <div class="stat">
                    <span>ENTRY</span>
                    <strong id="entry">--</strong>
                </div>

                <div class="stat">
                    <span>PAYOUT</span>
                    <strong id="payout">--%</strong>
                </div>

                <div class="stat">
                    <span>EXPIRY</span>
                    <strong>5 MIN</strong>
                </div>

                <div class="stat">
                    <span>TIME TO ENTER</span>
                    <strong id="countdown"
                            class="countdown">
                        --s
                    </strong>
                </div>

            </div>

            <div class="note">
                Ryu V2 uses the selected chart timeframe for the setup.
                The demo expiry remains 5 minutes.
            </div>

        </div>

    </section>

    <section class="card confluence">

        <strong>RYU CONFLUENCE CHECKLIST</strong>

        <div class="check">
            <span>Alligator</span>
            <b id="alligator" class="neutral">SCANNING</b>
        </div>

        <div class="check">
            <span>Moving Average</span>
            <b id="movingAverage" class="neutral">SCANNING</b>
        </div>

        <div class="check">
            <span>MACD</span>
            <b id="macd" class="neutral">SCANNING</b>
        </div>

        <div class="check">
            <span>Momentum</span>
            <b id="momentum" class="neutral">SCANNING</b>
        </div>

        <div class="check">
            <span>Trend Structure</span>
            <b id="trend" class="neutral">SCANNING</b>
        </div>

    </section>

</main>

<script>
const ASSETS = {
    Forex: [
        "EUR/USD OTC",
        "GBP/USD OTC",
        "USD/JPY OTC",
        "AUD/USD OTC",
        "USD/CAD OTC",
        "USD/CHF OTC",
        "NZD/USD OTC",
        "EUR/GBP OTC"
    ],

    Crypto: [
        "BTC/USD OTC",
        "ETH/USD OTC",
        "SOL/USD OTC",
        "XRP/USD OTC",
        "LTC/USD OTC",
        "DOGE/USD OTC"
    ],

    Stocks: [
        "AAPL OTC",
        "TSLA OTC",
        "NVDA OTC",
        "AMZN OTC",
        "META OTC",
        "MSFT OTC",
        "GOOGL OTC"
    ],

    Commodities: [
        "Gold OTC",
        "Silver OTC",
        "Oil OTC",
        "Natural Gas OTC"
    ]
};

let currentMarket = "Forex";
let currentTimeframe = "1m";
let animationPhase = 0;

function simpleHash(text) {
    let hash = 0;

    for (let i = 0; i < text.length; i++) {
        hash = ((hash << 5) - hash) + text.charCodeAt(i);
        hash = hash | 0;
    }

    return Math.abs(hash);
}

function loadAssets() {

    const select = document.getElementById("asset");

    select.innerHTML = "";

    ASSETS[currentMarket].forEach(function(asset) {

        const option = document.createElement("option");

        option.value = asset;
        option.textContent = asset;

        select.appendChild(option);
    });

    updateDashboard();
}

function changeMarket(market, button) {

    currentMarket = market;

    document
        .querySelectorAll(".filters button")
        .forEach(function(item) {
            item.classList.remove("active");
        });

    button.classList.add("active");

    loadAssets();
}

function changeTimeframe(tf, button) {

    currentTimeframe = tf;

    document
        .querySelectorAll(".timeframes button")
        .forEach(function(item) {
            item.classList.remove("active");
        });

    button.classList.add("active");

    document.getElementById("timeframe").value = tf;

    updateDashboard();
}

document
    .getElementById("timeframe")
    .addEventListener("change",
