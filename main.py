import os
import math
import random
import threading
import time
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# ============================================================
# RYU V2
# Self-contained Flask dashboard
# Render start command:
# gunicorn main:app
# ============================================================

EXPIRY_MINUTES = 5

# Pocket Option-style market organization.
# These are display/selection assets only. They are NOT a
# private Pocket Option OTC price feed.
ASSETS = {
    "Currency": [
        "EUR/USD OTC", "GBP/USD OTC", "USD/JPY OTC",
        "USD/CHF OTC", "AUD/USD OTC", "AUD/JPY OTC",
        "AUD/CAD OTC", "AUD/CHF OTC", "AUD/NZD OTC",
        "CAD/CHF OTC", "CAD/JPY OTC", "EUR/CHF OTC",
        "EUR/GBP OTC", "EUR/JPY OTC", "EUR/AUD OTC",
        "EUR/CAD OTC", "EUR/NZD OTC", "GBP/AUD OTC",
        "GBP/JPY OTC", "GBP/CAD OTC", "GBP/CHF OTC",
        "NZD/USD OTC", "NZD/JPY OTC", "USD/CAD OTC",
        "USD/SGD OTC", "USD/HKD OTC", "USD/MXN OTC",
        "USD/BRL OTC", "USD/INR OTC", "USD/IDR OTC",
        "USD/TRY OTC", "USD/ZAR OTC", "USD/RUB OTC",
        "USD/ARS OTC", "USD/CLP OTC", "USD/COP OTC",
        "USD/PKR OTC", "USD/BDT OTC", "USD/EGP OTC",
        "USD/THB OTC", "USD/VND OTC", "USD/MYR OTC",
        "EUR/RUB OTC", "EUR/TRY OTC", "EUR/HUF OTC",
        "QAR/CNY OTC", "AED/CNY OTC", "SAR/CNY OTC",
        "BHD/CNY OTC", "JOD/CNY OTC", "KES/USD OTC",
        "LBP/USD OTC", "MAD/USD OTC", "NGN/USD OTC",
        "TND/USD OTC", "YER/USD OTC"
    ],

    "Commodities": [
        "Gold OTC",
        "Silver OTC",
        "WTI Crude Oil OTC",
        "Brent Crude Oil OTC",
        "Natural Gas OTC",
        "Platinum spot OTC",
        "Palladium spot OTC"
    ],

    "Stocks": [
        "Apple OTC",
        "Microsoft OTC",
        "Tesla OTC",
        "Amazon OTC",
        "Advanced Micro Devices OTC",
        "Intel OTC",
        "NVIDIA OTC",
        "Netflix OTC",
        "Meta Platforms OTC",
        "FACEBOOK INC OTC",
        "Google OTC",
        "Alibaba OTC",
        "Coinbase Global OTC",
        "Palantir Technologies OTC",
        "Boeing Company OTC",
        "VISA OTC",
        "Mastercard OTC",
        "McDonald's OTC",
        "Johnson & Johnson OTC",
        "Pfizer Inc OTC",
        "ExxonMobil OTC",
        "Citigroup Inc OTC",
        "American Express OTC",
        "FedEx OTC",
        "GameStop Corp OTC",
        "Marathon Digital Holdings OTC",
        "Cisco OTC"
    ],

    "Cryptocurrencies": [
        "Bitcoin OTC",
        "Ethereum OTC",
        "Dogecoin OTC",
        "Polkadot OTC",
        "Polygon OTC",
        "Litecoin OTC",
        "Solana OTC",
        "Toncoin OTC",
        "BNB OTC",
        "TRON OTC",
        "Chainlink OTC",
        "Cardano OTC",
        "Avalanche OTC",
        "Dash OTC",
        "Bitcoin ETF OTC",
        "BCH/EUR OTC",
        "BCH/GBP OTC",
        "BCH/JPY OTC"
    ],

    "Indices": [
        "VIX OTC",
        "US 30 OTC",
        "US 500 OTC",
        "US Tech 100 OTC",
        "Germany 40 OTC",
        "UK 100 OTC",
        "France 40 OTC",
        "Japan 225 OTC"
    ]
}

# ------------------------------------------------------------
# Demo/live-looking market engine
# ------------------------------------------------------------

market_state = {}
state_lock = threading.Lock()


def seed_price(asset):
    bases = {
        "EUR/USD": 1.1650,
        "GBP/USD": 1.3450,
        "USD/JPY": 147.5,
        "USD/CHF": 0.7950,
        "AUD/USD": 0.6600,
        "USD/CAD": 1.3850,
        "BTC": 110000.0,
        "ETH": 4300.0,
        "SOL": 210.0,
        "Gold": 3400.0,
        "Silver": 39.0,
        "Tesla": 340.0,
        "Apple": 238.0,
        "Amazon": 235.0,
        "Microsoft": 510.0,
        "NVIDIA": 175.0,
    }

    for key, value in bases.items():
        if key.lower() in asset.lower():
            return value

    return random.uniform(50, 500)


def get_state(asset):
    with state_lock:
        if asset not in market_state:
            p = seed_price(asset)
            market_state[asset] = {
                "price": p,
                "previous": p,
                "history": []
            }

        return market_state[asset]


def update_market(asset):
    state = get_state(asset)

    with state_lock:
        old = state["price"]

        # Small controlled movement for dashboard visualization.
        volatility = max(old * 0.00025, 0.00001)
        move = random.gauss(0, volatility)

        new_price = max(0.00001, old + move)

        state["previous"] = old
        state["price"] = new_price
        state["history"].append(new_price)

        if len(state["history"]) > 80:
            state["history"] = state["history"][-80:]

        return state


def calculate_signal(asset, timeframe):
    state = update_market(asset)

    history = state["history"]

    if len(history) < 10:
        history = [state["price"] + random.uniform(-1, 1)
                   for _ in range(20)]

    # Simple multi-confirmation demo engine.
    recent = history[-10:]

    fast = sum(recent[-3:]) / 3
    slow = sum(recent[-8:]) / 8

    momentum = recent[-1] - recent[-4]

    if fast > slow and momentum > 0:
        direction = "CALL"
    elif fast < slow and momentum < 0:
        direction = "PUT"
    else:
        direction = "WAIT"

    trend_score = 25 if fast > slow else 0
    momentum_score = 25 if momentum > 0 else 0

    # Simulated confirmations representing the Ryu checklist.
    alligator = random.randint(12, 25)
    macd = random.randint(10, 20)
    rsi = random.randint(8, 15)

    if direction == "CALL":
        confidence = min(
            98,
            45 + trend_score + momentum_score +
            alligator + macd + rsi
        )
    elif direction == "PUT":
        confidence = min(
            98,
            45 + trend_score + momentum_score +
            alligator + macd + rsi
        )
    else:
        confidence = random.randint(42, 61)

    # Don't call a weak setup a trade.
    if confidence < 72:
        direction = "WAIT"

    payout = random.choice([78, 80, 82, 85, 87, 90, 92])

    now = datetime.now()
    expiry = now + timedelta(minutes=EXPIRY_MINUTES)

    return {
        "asset": asset,
        "timeframe": timeframe,
        "direction": direction,
        "confidence": confidence,
        "payout": payout,
        "entry": state["price"],
        "signal_time": now.strftime("%H:%M:%S"),
        "expiry": expiry.strftime("%H:%M:%S"),
        "expiry_iso": expiry.isoformat(),
        "confluence": {
            "Alligator": alligator,
            "MACD": macd,
            "Momentum": momentum_score,
            "Trend": trend_score,
            "RSI": rsi
        },
        "history": history[-45:]
    }


# ------------------------------------------------------------
# HTML
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
    background:#07090d;
    color:#e9edf5;
    font-family:Arial,Helvetica,sans-serif;
}

.header {
    height:68px;
    background:#0d1118;
    border-bottom:1px solid #222936;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 18px;
    position:sticky;
    top:0;
    z-index:20;
}

.brand {
    display:flex;
    align-items:center;
    gap:12px;
}

.logo {
    width:42px;
    height:42px;
    border-radius:50%;
    background:linear-gradient(135deg,#e21b23,#ff6a00);
    display:flex;
    align-items:center;
    justify-content:center;
    font-weight:900;
    font-size:18px;
    box-shadow:0 0 18px rgba(255,70,0,.35);
}

.brand h1 {
    margin:0;
    font-size:21px;
}

.brand small {
    color:#7d8798;
}

.status {
    display:flex;
    align-items:center;
    gap:7px;
    font-size:12px;
    color:#71e6a1;
}

.status-dot {
    width:8px;
    height:8px;
    border-radius:50%;
    background:#39e77b;
    box-shadow:0 0 12px #39e77b;
}

.tabs {
    display:flex;
    gap:5px;
    background:#0a0d12;
    border-bottom:1px solid #202632;
    padding:8px 12px;
    overflow:auto;
}

.tab {
    border:0;
    background:#111620;
    color:#8994a6;
    padding:10px 18px;
    border-radius:8px;
    cursor:pointer;
    white-space:nowrap;
}

.tab.active {
    background:#202938;
    color:#fff;
}

.layout {
    display:grid;
    grid-template-columns:270px 1fr 300px;
    gap:12px;
    padding:12px;
}

.panel {
    background:#0d1219;
    border:1px solid #202734;
    border-radius:12px;
    overflow:hidden;
}

.panel-title {
    padding:13px 15px;
    font-size:13px;
    font-weight:bold;
    border-bottom:1px solid #202734;
    color:#b8c1d0;
}

.market-tools {
    padding:12px;
}

select, button {
    font:inherit;
}

select {
    width:100%;
    background:#111722;
    border:1px solid #2a3444;
    color:#fff;
    border-radius:8px;
    padding:11px;
    outline:none;
}

.category {
    margin-top:12px;
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:6px;
}

.category button {
    background:#111722;
    border:1px solid #252e3d;
    color:#8e99aa;
    padding:8px 5px;
    border-radius:7px;
    cursor:pointer;
    font-size:11px;
}

.category button.active {
    color:#fff;
    border-color:#e54242;
    background:#241316;
}

.asset-list {
    max-height:510px;
    overflow:auto;
    padding:7px;
}

.asset {
    width:100%;
    text-align:left;
    border:0;
    background:transparent;
    color:#b9c2d0;
    padding:9px;
    border-radius:7px;
    cursor:pointer;
    font-size:12px;
}

.asset:hover,
.asset.selected {
    background:#1b2330;
    color:#fff;
}

.main {
    min-width:0;
}

.signal-card {
    background:#0d1219;
    border:1px solid #202734;
    border-radius:12px;
    padding:16px;
}

.asset-head {
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:12px;
}

.asset-name {
    font-size:18px;
    font-weight:bold;
}

.badge {
    font-size:11px;
    padding:5px 9px;
    border-radius:20px;
    background:#151c27;
    color:#8f9bad;
}

.timeframes {
    display:flex;
    gap:6px;
    margin-bottom:12px;
}

.timeframes button {
    flex:1;
    background:#111722;
    border:1px solid #293241;
    color:#8994a5;
    padding:9px;
    border-radius:7px;
    cursor:pointer;
}

.timeframes button.active {
    background:#273141;
    color:#fff;
}

.chart {
    height:390px;
    position:relative;
    background:#080b10;
    border:1px solid #1e2734;
    border-radius:9px;
    overflow:hidden;
}

canvas {
    width:100%;
    height:100%;
}

.signal-overlay {
    position:absolute;
    top:14px;
    left:14px;
    padding:8px 12px;
    border-radius:8px;
    background:rgba(7,10,15,.9);
    border:1px solid #283241;
}

.signal {
    font-size:27px;
    font-weight:900;
    letter-spacing:1px;
}

.call {
    color:#38e987;
}

.put {
    color:#ff4e59;
}

.wait {
    color:#f2bd55;
}

.metrics {
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:8px;
    margin-top:10px;
}

.metric {
    background:#101620;
    border:1px solid #222c39;
    border-radius:8px;
    padding:11px;
}

.metric small {
    display:block;
    color:#727e90;
    font-size:10px;
    margin-bottom:5px;
}

.metric strong {
    font-size:15px;
}

.entry-box {
    margin-top:10px;
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:10px;
}

.entry {
    background:#101620;
    border:1px solid #222c39;
    padding:12px;
    border-radius:8px;
}

.entry small {
    color:#778397;
}

.entry strong {
    display:block;
    margin-top:4px;
    font-size:17px;
}

.countdown {
    margin-top:10px;
    border-radius:9px;
    padding:13px;
    text-align:center;
    background:#151b25;
    border:1px solid #293445;
}

.countdown.hot {
    animation:pulse .8s infinite alternate;
    border-color:#e83d48;
}

@keyframes pulse {
    from {box-shadow:0 0 0 rgba(255,50,50,0)}
    to {box-shadow:0 0 25px rgba(255,50,50,.35)}
}

.right-card {
    padding:14px;
}

.confidence {
    text-align:center;
    font-size:40px;
    font-weight:900;
    margin:15px 0;
}

.bar {
    height:8px;
    border-radius:20px;
    background:#171e29;
    overflow:hidden;
}

.bar-fill {
    height:100%;
    width:0%;
    background:#39e77b;
    transition:.5s;
}

.check {
    display:flex;
    justify-content:space-between;
    padding:10px 0;
    border-bottom:1px solid #1c2430;
    font-size:12px;
}

.check span:last-child {
    color:#65e39a;
}

.note {
    color:#687486;
    font-size:10px;
    line-height:1.5;
    padding:12px;
}

@media(max-width:1050px) {
    .layout {
        grid-template-columns:220px 1fr;
    }

    .right {
        grid-column:1/-1;
    }
}

@media(max-width:700px) {
    .layout {
        display:block;
        padding:7px;
    }

    .left,
    .right {
        margin-bottom:8px;
    }

    .asset-list {
        max-height:220px;
    }

    .chart {
        height:300px;
    }

    .metrics {
        grid-template-columns:1fr 1fr;
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
            <small>AI MARKET SIGNAL ENGINE</small>
        </div>
    </div>

    <div class="status">
        <span class="status-dot"></span>
        ENGINE ONLINE
    </div>
</header>

<nav class="tabs">
    <button class="tab active">Signals</button>
    <button class="tab">Trades</button>
    <button class="tab">Performance</button>
    <button class="tab">Settings</button>
</nav>

<div class="layout">

    <!-- LEFT -->
    <section class="panel left">

        <div class="panel-title">
            MARKET SELECTION
        </div>

        <div class="market-tools">

            <select id="categorySelect">
                {% for category in categories %}
                <option value="{{ category }}">{{ category }}</option>
                {% endfor %}
            </select>

            <div class="category">
                {% for category in categories %}
                <button onclick="chooseCategory('{{ category }}')"
                        class="{% if loop.first %}active{% endif %}">
                    {{ category }}
                </button>
                {% endfor %}
            </div>

        </div>

        <div id="assetList" class="asset-list"></div>

    </section>

    <!-- CENTER -->
    <main class="main">

        <div class="signal-card">

            <div class="asset-head">
                <div>
                    <div id="assetName" class="asset-name">
                        EUR/USD OTC
                    </div>
                    <small id="engineText">
                        Ryu multi-confirmation engine
                    </small>
                </div>

                <div class="badge">
                    OTC MARKET
                </div>
            </div>

            <div class="timeframes">
                <button onclick="setTimeframe('1m')" id="tf1">1 MIN</button>
                <button onclick="setTimeframe('2m')" id="tf2">2 MIN</button>
                <button onclick="setTimeframe('3m')" id="tf3">3 MIN</button>
            </div>

            <div class="chart">
                <canvas id="chartCanvas"></canvas>

                <div class="signal-overlay">
                    <div id="signal" class="signal wait">WAIT</div>
                    <small id="confidenceSmall">
                        Scanning market...
                    </small>
                </div>
            </div>

            <div class="metrics">

                <div class="metric">
                    <small>SIGNAL</small>
                    <strong id="signalMetric">WAIT</strong>
                </div>

                <div class="metric">
                    <small>CONFIDENCE</small>
                    <strong id="confidenceMetric">--</strong>
                </div>

                <div class="metric">
                    <small>PAYOUT</small>
                    <strong id="payoutMetric">--</strong>
                </div>

                <div class="metric">
                    <small>TIMEFRAME</small>
                    <strong id="timeframeMetric">1m</strong>
                </div>

            </div>

            <div class="entry-box">

                <div class="entry">
                    <small>ENTRY PRICE</small>
                    <strong id="entryPrice">--</strong>
                </div>

                <div class="entry">
                    <small>EXPIRY</small>
                    <strong id="expiryTime">--</strong>
                </div>

            </div>

            <div id="countdown" class="countdown">
                WAITING FOR RYU SETUP
            </div>

        </div>

    </main>

    <!-- RIGHT -->
    <aside class="panel right">

        <div class="panel-title">
            RYU CONFLUENCE
        </div>

        <div class="right-card">

            <div class="confidence">
                <span id="bigConfidence">--</span>
                <small style="font-size:14px;color:#687486">%</small>
            </div>

            <div class="bar">
                <div id="confidenceBar" class="bar-fill"></div>
            </div>

            <div class="check">
                <span>Alligator</span>
                <span id="alligator">--</span>
            </div>

            <div class="check">
                <span>MACD</span>
                <span id="macd">--</span>
            </div>

            <div class="check">
                <span>Momentum</span>
                <span id="momentum">--</span>
            </div>

            <div class="check">
                <span>Trend</span>
                <span id="trend">--</span>
            </div>

            <div class="check">
                <span>RSI</span>
                <span id="rsi">--</span>
            </div>

            <div class="note">
                Ryu waits for multiple confirmations instead of
                forcing a CALL or PUT on every candle.
            </div>

        </div>

    </aside>

</div>

<script>

const DATA = {{ assets|tojson }};

let category = "Currency";
let asset = "EUR/USD OTC";
let timeframe = "1m";
let currentData = null;
let countdownTimer = null;

const canvas = document.getElementById("chartCanvas");
const ctx = canvas.getContext("2d");

function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();

    const ratio = window.devicePixelRatio || 1;

    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;

    ctx.setTransform(ratio,0,0,ratio,0,0);

    drawChart(
        currentData ? currentData.history : []
    );
}

window.addEventListener("resize", resizeCanvas);


function chooseCategory(name) {

    category = name;

    document.querySelectorAll(".category button")
        .forEach(b => b.classList.remove("active"));

    [...document.querySelectorAll(".category button")]
        .find(b => b.innerText === name)
        ?.classList.add("active");

    document.getElementById("categorySelect").value = name;

    renderAssets();
}


document.getElementById("categorySelect")
    .addEventListener("change", function() {
        chooseCategory(this.value);
    });


function renderAssets() {

    const list = document.getElementById("assetList");

    list.innerHTML = "";

    DATA[category].forEach(item => {

        const b = document.createElement("button");

        b.className =
            "asset" +
            (item === asset ? " selected" : "");

        b.innerText = item;

        b.onclick = () => {

            asset = item;

            renderAssets();
            refreshSignal();
        };

        list.appendChild(b);
    });
}


function setTimeframe(tf) {

    timeframe = tf;

    document
        .querySelectorAll(".timeframes button")
        .forEach(b => b.classList.remove("active"));

    document.getElementById(
        "tf" + tf.substring(0,1)
    ).classList.add("active");

    document.getElementById(
        "timeframeMetric"
    ).innerText = tf;

    refreshSignal();
}


function formatPrice(price) {

    if (price >= 10000)
        return price.toFixed(2);

    if (price >= 100)
        return price.toFixed(3);

    if (price >= 10)
        return price.toFixed(4);

    return price.toFixed(5);
}


function refreshSignal() {

    fetch(
        "/api/signal?asset=" +
        encodeURIComponent(asset) +
        "&timeframe=" +
        encodeURIComponent(timeframe)
    )
    .then(r => r.json())
    .then(data => {

        currentData = data;

        document.getElementById("assetName")
            .innerText = data.asset;

        document.getElementById("signal")
            .innerText = data.direction;

        document.getElementById("signalMetric")
            .innerText = data.direction;

        document.getElementById("confidenceMetric")
            .innerText = data.confidence + "%";

        document.getElementById("confidenceSmall")
            .innerText =
            data.confidence + "% confidence";

        document.getElementById("payoutMetric")
            .innerText = data.payout + "%";

        document.getElementById("timeframeMetric")
            .innerText = data.timeframe;

        document.getElementById("entryPrice")
            .innerText = formatPrice(data.entry);

        document.getElementById("expiryTime")
            .innerText = data.expiry;

        document.getElementById("bigConfidence")
            .innerText = data.confidence;

        document.getElementById("confidenceBar")
            .style.width = data.confidence + "%";

        document.getElementById("alligator")
            .innerText =
            data.confluence.Alligator + "/25";

        document.getElementById("macd")
            .innerText =
            data.confluence.MACD + "/20";

        document.getElementById("momentum")
            .innerText =
            data.confluence.Momentum + "/25";

        document.getElementById("trend")
            .innerText =
            data.confluence.Trend + "/25";

        document.getElementById("rsi")
            .innerText =
            data.confluence.RSI + "/15";

        const signalEl =
            document.getElementById("signal");

        signalEl.className =
            "signal " +
            (
                data.direction === "CALL"
                ? "call"
                : data.direction === "PUT"
                ? "put"
                : "wait"
            );

        drawChart(data.history);

        startCountdown(data.expiry_iso);

    })
    .catch(err => {

        console.log(err);

        document.getElementById("signal")
            .innerText = "WAIT";

        document.getElementById("signal")
            .className = "signal wait";

    });
}


function drawChart(values) {

    if (!values || values.length < 2)
        return;

    const rect = canvas.getBoundingClientRect();

    const w = rect.width;
    const h = rect.height;

    ctx.clearRect(0,0,w,h);

    // Grid
    ctx.strokeStyle = "#151c25";
    ctx.lineWidth = 1;

    for(let x=0; x<w; x+=50) {

        ctx.beginPath();
        ctx.moveTo(x,0);
        ctx.lineTo(x,h);
        ctx.stroke();
    }

    for(let y=0; y<h; y+=45) {

        ctx.beginPath();
        ctx.moveTo(0,y);
        ctx.lineTo(w,y);
        ctx.stroke();
    }

    const min =
        Math.min(...values);

    const max =
        Math.max(...values);

    const range =
        Math.max(max-min,0.0000001);

    ctx.beginPath();

    values.forEach((v,i) => {

        const x =
            (i/(values.length-1))*w;

        const y =
            h -
            ((v-min)/range)*(h-30) -
            15;

        if(i === 0)
            ctx.moveTo(x,y);
        else
            ctx.lineTo(x,y);

    });

    ctx.strokeStyle = "#e8edf5";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Entry marker
    const last = values[values.length-1];

    const ly =
        h -
        ((last-min)/range)*(h-30) -
        15;

    ctx.beginPath();
    ctx.arc(w-3,ly,5,0,Math.PI*2);
    ctx.fillStyle = "#39e77b";
    ctx.fill();

}


function startCountdown(expiryIso) {

    if(countdownTimer)
        clearInterval(countdownTimer);

    const box =
        document.getElementById("countdown");

    function tick() {

        const target =
            new Date(expiryIso).getTime();

        const now =
            Date.now();

        let seconds =
            Math.max(0,
                Math.floor((target-now)/1000)
            );

        const minutes =
            Math.floor(seconds/60);

        seconds =
            seconds % 60;

        box.innerText =
            "EXPIRY IN  " +
            minutes +
            ":" +
            String(seconds).padStart(2,"0");

        if(seconds <= 20 && minutes === 0)
            box.classList.add("hot");
        else
            box.classList.remove("hot");

        if(
            target-now <= 0
        ) {

            box.innerText =
                "EXPIRY REACHED — SCANNING NEXT SETUP";

            setTimeout(
                refreshSignal,
                1000
            );

            clearInterval(countdownTimer);
        }
    }

    tick();

    countdownTimer =
        setInterval(tick,1000);
}


// Initial UI
renderAssets();

setTimeframe("1m");

resizeCanvas();

refreshSignal();

// Refresh the chart without changing the selected asset.
setInterval(
    refreshSignal,
    12000
);

</script>

</body>
</html>
"""


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------

@app.route("/")
def home():

    return render_template_string(
        HTML,
        categories=list(ASSETS.keys()),
        assets=ASSETS
    )


@app.route("/api/assets")
def api_assets():

    return jsonify(ASSETS)


@app.route("/api/signal")
def api_signal():

    asset = request.args.get(
        "asset",
        "EUR/USD OTC"
    )

    timeframe = request.args.get(
        "timeframe",
        "1m"
    )

    valid_timeframes = {
        "1m",
        "2m",
        "3m"
    }

    if timeframe not in valid_timeframes:
        timeframe = "1m"

    all_assets = []

    for values in ASSETS.values():
        all_assets.extend(values)

    if asset not in all_assets:
        asset = "EUR/USD OTC"

    return jsonify(
        calculate_signal(
            asset,
            timeframe
        )
    )


@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "service": "Ryu V2",
        "engine": "running",
        "expiry_minutes": EXPIRY_MINUTES,
        "time": datetime.now().isoformat()
    })


# ------------------------------------------------------------
# Local execution
# ------------------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
        )
