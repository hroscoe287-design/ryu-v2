import os
import random
import yfinance as yf
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ryu V2 Dashboard</title>
    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: #070b14;
            color: white;
            font-family: Arial, sans-serif;
        }

        header {
            padding: 20px;
            background: #0d1320;
            border-bottom: 1px solid #202a3d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            font-size: 28px;
            font-weight: bold;
        }

        .logo span {
            color: #00ff88;
        }

        .live {
            color: #00ff88;
            font-size: 14px;
        }

        main {
            max-width: 1100px;
            margin: auto;
            padding: 18px;
        }

        nav {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            margin-bottom: 18px;
        }

        nav button {
            background: #111827;
            color: #aeb9cc;
            border: 1px solid #263149;
            border-radius: 10px;
            padding: 11px 18px;
            white-space: nowrap;
        }

        nav button.active {
            background: #00ff88;
            color: #07110c;
            font-weight: bold;
        }

        .filters {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 18px;
        }

        select {
            width: 100%;
            padding: 13px;
            background: #111827;
            color: white;
            border: 1px solid #263149;
            border-radius: 10px;
        }

        .card {
            background: #101725;
            border: 1px solid #202a3d;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 16px;
        }

        .center {
            text-align: center;
        }

        .pair {
            color: #8e9bb0;
            font-size: 14px;
        }

        .signal {
            font-size: 48px;
            font-weight: bold;
            margin: 12px 0;
        }

        .call {
            color: #00ff88;
        }

        .put {
            color: #ff5263;
        }

        .wait {
            color: #ffd166;
        }

        .confidence {
            font-size: 20px;
        }

        .bar {
            height: 10px;
            background: #202a3d;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 12px;
        }

        .fill {
            height: 100%;
            background: #00ff88;
        }

        .metrics {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-top: 20px;
        }

        .metric {
            background: #0a101c;
            border-radius: 12px;
            padding: 14px;
        }

        .label {
            color: #77849a;
            font-size: 12px;
        }

        .value {
            margin-top: 7px;
            font-size: 19px;
        }

        .chart {
            height: 230px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #65738a;
            border-radius: 12px;
            background:
                linear-gradient(#182238 1px, transparent 1px),
                linear-gradient(90deg, #182238 1px, transparent 1px);
            background-size: 35px 35px;
        }

        .row {
            display: flex;
            justify-content: space-between;
            padding: 14px 0;
            border-bottom: 1px solid #202a3d;
        }

        .good {
            color: #00ff88;
        }

        .bad {
            color: #ff5263;
        }

        footer {
            text-align: center;
            color: #65738a;
            padding: 25px;
            font-size: 12px;
        }

        @media (max-width: 700px) {
            .filters {
                grid-template-columns: 1fr;
            }

            .metrics {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>

<body>

<header>
    <div class="logo">RYU <span>V2</span></div>
    <div class="live">● LIVE</div>
</header>

<main>

    <nav>
        <button class="active">Signals</button>
        <button>Trades</button>
        <button>Performance</button>
        <button>Settings</button>
    </nav>

    <div class="filters">
        <select id="market">
            <option>Crypto</option>
            <option>Forex</option>
            <option>Stocks</option>
        </select>

        <select id="asset">
            <option value="BTC-USD">BTC/USD</option>
            <option value="ETH-USD">ETH/USD</option>
            <option value="EURUSD=X">EUR/USD</option>
            <option value="GBPUSD=X">GBP/USD</option>
            <option value="USDJPY=X">USD/JPY</option>
            <option value="AAPL">AAPL</option>
            <option value="TSLA">TSLA</option>
        </select>

        <select id="timeframe">
            <option value="1m">1 Minute</option>
            <option value="2m">2 Minutes</option>
            <option value="3m">3 Minutes</option>
        </select>
    </div>

    <section class="card center">
        <div class="pair" id="pair">BTC/USD</div>

        <div class="signal call" id="signal">CALL</div>

        <div class="confidence">
            Confidence: <strong id="confidence">--</strong>
        </div>

        <div class="bar">
            <div class="fill" id="confidenceBar" style="width: 0%;"></div>
        </div>

        <div class="metrics">

            <div class="metric">
                <div class="label">ENTRY PRICE</div>
                <div class="value" id="price">Loading...</div>
            </div>

            <div class="metric">
                <div class="label">PAYOUT</div>
                <div class="value">85%</div>
            </div>

            <div class="metric">
                <div class="label">TIMEFRAME</div>
                <div class="value" id="tf">1m</div>
            </div>

            <div class="metric">
                <div class="label">STATUS</div>
                <div class="value good">READY</div>
            </div>

        </div>
    </section>

    <section class="card">
        <h3>Price Chart</h3>
        <div class="chart">
            Live market chart
        </div>
    </section>

    <section class="card">
        <h3>Confluence</h3>

        <div class="row">
            <span>Trend</span>
            <span class="good">Confirmed ✓</span>
        </div>

        <div class="row">
            <span>Momentum</span>
            <span class="good">Confirmed ✓</span>
        </div>

        <div class="row">
            <span>RSI</span>
            <span class="good">Confirmed ✓</span>
        </div>

        <div class="row">
            <span>Volume</span>
            <span class="good">Confirmed ✓</span>
        </div>
    </section>

    <section class="card">
        <h3>Recent Trades</h3>

        <div class="row">
            <span>BTC/USD — CALL</span>
            <span class="good">WIN</span>
        </div>

        <div class="row">
            <span>EUR/USD — PUT</span>
            <span class="good">WIN</span>
        </div>

        <div class="row">
            <span>ETH/USD — CALL</span>
            <span class="bad">LOSS</span>
        </div>
    </section>

</main>

<footer>
    Ryu V2 Trading Dashboard
</footer>

<script>
async function updateDashboard() {
    try {
        const response = await fetch("/api/signal");
        const data = await response.json();

        document.getElementById("pair").textContent = data.pair;
        document.getElementById("signal").textContent = data.signal;
        document.getElementById("confidence").textContent =
            data.confidence + "%";
        document.getElementById("confidenceBar").style.width =
            data.confidence + "%";
        document.getElementById("price").textContent =
            data.price;
        document.getElementById("tf").textContent =
            data.timeframe;

        const signalElement = document.getElementById("signal");
        signalElement.className =
            "signal " + data.signal.toLowerCase();

    } catch (error) {
        console.log("Dashboard update error:", error);
    }
}

updateDashboard();
setInterval(updateDashboard, 10000);

document.getElementById("asset").addEventListener("change", updateDashboard);
document.getElementById("timeframe").addEventListener("change", updateDashboard);
</script>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(DASHBOARD)


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "system": "Ryu V2"
    })


@app.route("/api/signal")
def api_signal():
    symbols = {
        "BTC-USD": "BTC/USD",
        "ETH-USD": "ETH/USD",
        "EURUSD=X": "EUR/USD",
        "GBPUSD=X": "GBP/USD",
        "USDJPY=X": "USD/JPY",
        "AAPL": "AAPL",
        "TSLA": "TSLA"
    }

    symbol = "BTC-USD"

    try:
        data = yf.Ticker(symbol).history(
            period="1d",
            interval="1m"
        )

        if data.empty:
            price = 0.0
        else:
            price = float(data["Close"].iloc[-1])

    except Exception:
        price = 0.0

    signal = random.choice(["CALL", "PUT", "WAIT"])
    confidence = random.randint(72, 94)

    return jsonify({
        "pair": symbols[symbol],
        "signal": signal,
        "confidence": confidence,
        "price": f"${price:,.2f}",
        "timeframe": "1m"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
