from flask import Flask, jsonify, request
from datetime import datetime, timezone
import random
import math

app = Flask(__name__)

# ============================================================
# RYU V2 - SIGNAL DASHBOARD
# Signal/demo dashboard only. No trades are placed.
# ============================================================

ASSETS = {
    "Forex": [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "USD/CAD",
        "USD/CHF",
        "NZD/USD",
    ],
    "Crypto": [
        "BTC/USD",
        "ETH/USD",
        "SOL/USD",
        "XRP/USD",
    ],
    "Stocks": [
        "AAPL",
        "TSLA",
        "NVDA",
        "AMZN",
        "META",
        "MSFT",
        "GOOGL",
    ],
}

TIMEFRAMES = ["1m", "2m", "3m"]

current_asset = "USD/JPY"
current_market = "Forex"
current_timeframe = "1m"


def make_candles(count=40):
    candles = []
    price = 100.0

    for i in range(count):
        movement = random.uniform(-1.2, 1.2)

        open_price = price
        close_price = max(1, price + movement)

        high_price = max(open_price, close_price) + random.uniform(0.1, 0.7)
        low_price = min(open_price, close_price) - random.uniform(0.1, 0.7)

        candles.append(
            {
                "time": i,
                "open": round(open_price, 4),
                "high": round(high_price, 4),
                "low": round(low_price, 4),
                "close": round(close_price, 4),
            }
        )

        price = close_price

    return candles


def calculate_signal():
    """
    Demo signal engine.

    This is intentionally conservative:
    - CALL
    - PUT
    - WAIT

    The dashboard does not place trades.
    """

    momentum = random.uniform(-1.0, 1.0)
    trend = random.uniform(-1.0, 1.0)
    volatility = random.uniform(0.0, 1.0)

    score = (momentum * 0.45) + (trend * 0.45) - (volatility * 0.10)

    if score >= 0.35:
        signal = "CALL"
    elif score <= -0.35:
        signal = "PUT"
    else:
        signal = "WAIT"

    confidence = 50 + abs(score) * 45
    confidence = min(95, max(50, confidence))

    if signal == "CALL":
        direction = "UP"
    elif signal == "PUT":
        direction = "DOWN"
    else:
        direction = "NEUTRAL"

    return {
        "signal": signal,
        "direction": direction,
        "confidence": round(confidence, 1),
        "score": round(score, 3),
    }


def get_price():
    base_prices = {
        "EUR/USD": 1.1650,
        "GBP/USD": 1.3500,
        "USD/JPY": 147.50,
        "AUD/USD": 0.6600,
        "USD/CAD": 1.3800,
        "USD/CHF": 0.7900,
        "NZD/USD": 0.5900,
        "BTC/USD": 113500.0,
        "ETH/USD": 4300.0,
        "SOL/USD": 210.0,
        "XRP/USD": 2.90,
        "AAPL": 238.0,
        "TSLA": 345.0,
        "NVDA": 180.0,
        "AMZN": 235.0,
        "META": 740.0,
        "MSFT": 510.0,
        "GOOGL": 240.0,
    }

    base = base_prices.get(current_asset, 100.0)

    variation = random.uniform(-0.0015, 0.0015)

    return round(base * (1 + variation), 6)


def confluence_items(signal):
    if signal == "CALL":
        return [
            ("Alligator Trend", True),
            ("Moving Average", True),
            ("MACD Momentum", True),
            ("Price Structure", True),
            ("Volatility Filter", random.choice([True, True, False])),
        ]

    if signal == "PUT":
        return [
            ("Alligator Trend", True),
            ("Moving Average", True),
            ("MACD Momentum", True),
            ("Price Structure", True),
            ("Volatility Filter", random.choice([True, True, False])),
        ]

    return [
        ("Alligator Trend", False),
        ("Moving Average", False),
        ("MACD Momentum", False),
        ("Price Structure", False),
        ("Volatility Filter", True),
    ]


@app.route("/")
def dashboard():
    return """
<!DOCTYPE html>
<html>
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
    background:
        radial-gradient(circle at top right, #3b0000 0%, transparent 35%),
        linear-gradient(135deg, #050505, #111111);
    color: white;
    font-family: Arial, Helvetica, sans-serif;
}

.header {
    padding: 18px;
    border-bottom: 1px solid #292929;
    background: rgba(5,5,5,.95);
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
    color: #ff3030;
}

.subtitle {
    color: #8d8d8d;
    font-size: 12px;
    margin-top: 4px;
}

.nav {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 12px;
    background: #090909;
    border-bottom: 1px solid #222;
}

.nav button {
    border: 1px solid #333;
    background: #151515;
    color: #aaa;
    padding: 10px 18px;
    border-radius: 9px;
    font-weight: bold;
}

.nav button.active {
    background: #d71920;
    color: white;
    border-color: #ff3a3a;
}

.container {
    max-width: 1200px;
    margin: auto;
    padding: 16px;
}

.filters {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 15px;
}

.filter-box {
    background: #121212;
    border: 1px solid #292929;
    border-radius: 12px;
    padding: 12px;
}

.filter-box label {
    display: block;
    color: #777;
    font-size: 11px;
    margin-bottom: 6px;
    text-transform: uppercase;
}

select {
    width: 100%;
    background: #090909;
    color: white;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 10px;
}

.grid {
    display: grid;
    grid-template-columns: 1.4fr .8fr;
    gap: 15px;
}

.card {
    background: rgba(18,18,18,.96);
    border: 1px solid #292929;
    border-radius: 15px;
    padding: 16px;
    box-shadow: 0 12px 35px rgba(0,0,0,.3);
}

.card-title {
    font-size: 13px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 14px;
}

.signal {
    text-align: center;
    padding: 25px 10px;
    border-radius: 14px;
    background: #0b0b0b;
    border: 1px solid #303030;
}

.signal-word {
    font-size: 52px;
    font-weight: 900;
}

.call {
    color: #16e47b;
}

.put {
    color: #ff3030;
}

.wait {
    color: #ffc400;
}

.confidence {
    font-size: 20px;
    margin-top: 6px;
}

.status {
    margin-top: 12px;
    font-size: 12px;
    color: #777;
}

.stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
}

.stat {
    background: #0c0c0c;
    border: 1px solid #282828;
    padding: 14px;
    border-radius: 10px;
}

.stat-name {
    color: #777;
    font-size: 11px;
}

.stat-value {
    font-size: 20px;
    font-weight: bold;
    margin-top: 5px;
}

.chart {
    height: 300px;
    display: flex;
    align-items: flex-end;
    gap: 4px;
    padding: 15px 5px;
    overflow: hidden;
    background:
        linear-gradient(#151515 1px, transparent 1px),
        linear-gradient(90deg, #151515 1px, transparent 1px);
    background-size: 40px 40px;
    border-radius: 10px;
}

.candle {
    width: 7px;
    min-width: 7px;
    background: #16e47b;
    border-radius: 2px;
    position: relative;
}

.candle.red {
    background: #ff3030;
}

.confluence {
    margin-top: 15px;
}

.conf-row {
    display: flex;
    justify-content: space-between;
    padding: 11px 0;
    border-bottom: 1px solid #222;
    font-size: 13px;
}

.yes {
    color: #16e47b;
}

.no {
    color: #ff3030;
}

.bottom {
    margin-top: 15px;
    text-align: center;
    color: #666;
    font-size: 11px;
    padding: 20px;
}

@media(max-width: 800px) {
    .filters {
        grid-template-columns: 1fr;
    }

    .grid {
        grid-template-columns: 1fr;
    }

    .signal-word {
        font-size: 44px;
    }
}
</style>
</head>

<body>

<div class="header">
    <div class="brand">RYU <span>V2</span></div>
    <div class="subtitle">
        AI SIGNAL ENGINE • DEMO MODE • SIGNALS ONLY
    </div>
</div>

<div class="nav">
    <button class="active">Signals</button>
    <button>Trades</button>
    <button>Performance</button>
    <button>Settings</button>
</div>

<div class="container">

    <div class="filters">

        <div class="filter-box">
            <label>Market</label>
            <select id="market">
                <option>Forex</option>
                <option>Crypto</option>
                <option>Stocks</option>
            </select>
        </div>

        <div class="filter-box">
            <label>Asset</label>
            <select id="asset">
                <option>USD/JPY</option>
                <option>EUR/USD</option>
                <option>GBP/USD</option>
                <option>BTC/USD</option>
                <option>ETH/USD</option>
                <option>TSLA</option>
                <option>NVDA</option>
                <option>AAPL</option>
            </select>
        </div>

        <div class="filter-box">
            <label>Signal Timeframe</label>
            <select id="timeframe">
                <option>1m</option>
                <option>2m</option>
                <option>3m</option>
            </select>
        </div>

    </div>

    <div class="grid">

        <div>

            <div class="card">
                <div class="card-title">
                    Live Market Chart
                </div>

                <div id="chart" class="chart"></div>
            </div>

            <br>

            <div class="card">
                <div class="card-title">
                    Ryu Confluence Engine
                </div>

                <div id="confluence"></div>
            </div>

        </div>

        <div>

            <div class="card">

                <div class="card-title">
                    Current Signal
                </div>

                <div class="signal">

                    <div id="signal"
                         class="signal-word wait">
                        WAIT
                    </div>

                    <div id="confidence"
                         class="confidence">
                        50%
                    </div>

                    <div class="status">
                        Waiting for market confirmation
                    </div>

                </div>

                <br>

                <div class="stats">

                    <div class="stat">
                        <div class="stat-name">
                            ENTRY
                        </div>
                        <div id="entry"
                             class="stat-value">
                            --
                        </div>
                    </div>

                    <div class="stat">
                        <div class="stat-name">
                            PAYOUT
                        </div>
                        <div class="stat-value">
                            Demo
                        </div>
                    </div>

                    <div class="stat">
                        <div class="stat-name">
                            EXPIRY
                        </div>
                        <div class="stat-value">
                            5 MIN
                        </div>
                    </div>

                    <div class="stat">
                        <div class="stat-name">
                            ASSET
                        </div>
                        <div id="assetDisplay"
                             class="stat-value">
                            USD/JPY
                        </div>
                    </div>

                </div>

            </div>

        </div>

    </div>

    <div class="bottom">
        RYU V2 • DEMO SIGNAL DASHBOARD • NO AUTOMATED TRADES
    </div>

</div>

<script>

let currentMarket = "Forex";
let currentAsset = "USD/JPY";
let currentTimeframe = "1m";

const marketAssets = {
    Forex: [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "USD/CAD",
        "USD/CHF",
        "NZD/USD"
    ],
    Crypto: [
        "BTC/USD",
        "ETH/USD",
        "SOL/USD",
        "XRP/USD"
    ],
    Stocks: [
        "AAPL",
        "TSLA",
        "NVDA",
        "AMZN",
        "META",
        "MSFT",
        "GOOGL"
    ]
};

function updateAssetList() {

    const market =
        document.getElementById("market").value;

    const assetSelect =
        document.getElementById("asset");

    assetSelect.innerHTML = "";

    marketAssets[market].forEach(function(asset) {

        const option =
            document.createElement("option");

        option.value = asset;
        option.textContent = asset;

        assetSelect.appendChild(option);
    });

    currentMarket = market;
    currentAsset = assetSelect.value;

    refresh();
}

function createChart() {

    const chart =
        document.getElementById("chart");

    chart.innerHTML = "";

    let value = 130;

    for (let i = 0; i < 42; i++) {

        value +=
            (Math.random() - .48) * 25;

        value =
            Math.max(30, Math.min(260, value));

        const candle =
            document.createElement("div");

        candle.className =
            "candle";

        if (Math.random() > .52) {
            candle.classList.add("red");
        }

        candle.style.height =
            Math.round(value) + "px";

        chart.appendChild(candle);
    }
}

function refresh() {

    currentAsset =
        document.getElementById("asset").value;

    currentTimeframe =
        document.getElementById("timeframe").value;

    fetch(
        "/api/signal?asset="
        + encodeURIComponent(currentAsset)
        + "&timeframe="
        + encodeURIComponent(currentTimeframe)
    )
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {

        const signal =
            document.getElementById("signal");

        signal.textContent =
            data.signal;

        signal.className =
            "signal-word "
            + data.signal.toLowerCase();

        document.getElementById(
            "confidence"
        ).textContent =
            data.confidence + "%";

        document.getElementById(
            "entry"
        ).textContent =
            data.entry;

        document.getElementById(
            "assetDisplay"
        ).textContent =
            data.asset;

        const confluence =
            document.getElementById(
                "confluence"
            );

        confluence.innerHTML = "";

        data.confluence.forEach(function(item) {

            const row =
                document.createElement("div");

            row.className =
                "conf-row";

            const name =
                document.createElement("span");

            name.textContent =
                item.name;

            const result =
                document.createElement("span");

            result.textContent =
                item.confirmed
                ? "CONFIRMED"
                : "NO CONFIRMATION";

            result.className =
                item.confirmed
                ? "yes"
                : "no";

            row.appendChild(name);
            row.appendChild(result);

            confluence.appendChild(row);
        });

        createChart();
    });
}

document
    .getElementById("market")
    .addEventListener(
        "change",
        updateAssetList
    );

document
    .getElementById("asset")
    .addEventListener(
        "change",
        refresh
    );

document
    .getElementById("timeframe")
    .addEventListener(
        "change",
        refresh
    );

createChart();
refresh();

setInterval(refresh, 15000);

</script>

</body>
</html>
"""


@app.route("/api/signal")
def api_signal():

    asset = request.args.get(
        "asset",
        current_asset
    )

    timeframe = request.args.get(
        "timeframe",
        current_timeframe
    )

    if timeframe not in TIMEFRAMES:
        timeframe = "1m"

    signal_data = calculate_signal()

    price = get_price()

    confluence = []

    for name, confirmed in confluence_items(
        signal_data["signal"]
    ):
        confluence.append(
            {
                "name": name,
                "confirmed": confirmed,
            }
        )

    return jsonify(
        {
            "status": "ok",
            "engine": "Ryu V2",
            "asset": asset,
            "timeframe": timeframe,
            "signal": signal_data["signal"],
            "direction": signal_data["direction"],
            "confidence": signal_data["confidence"],
            "entry": price,
            "expiry": "5 minutes",
            "payout": "Demo",
            "confluence": confluence,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )


@app.route("/health")
def health():

    return jsonify(
        {
            "status": "online",
            "service": "Ryu V2",
            "time": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )


@app.route("/api/status")
def api_status():

    return jsonify(
        {
            "status": "online",
            "dashboard": "Ryu V2",
            "signal_only": True,
            "trade_execution": False,
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
