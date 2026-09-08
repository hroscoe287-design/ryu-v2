import os
import json
import time
import threading
from datetime import datetime, timezone
from collections import deque

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

DERIV_WS = os.getenv("DERIV_WS", "wss://ws.derivws.com/websockets/v3")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1089")
DEFAULT_SYMBOL = os.getenv("DERIV_SYMBOL", "frxEURUSD")

SYMBOLS = {
    "EUR/USD": "frxEURUSD",
    "GBP/USD": "frxGBPUSD",
    "USD/JPY": "frxUSDJPY",
    "AUD/USD": "frxAUDUSD",
    "USD/CAD": "frxUSDCAD",
    "EUR/JPY": "frxEURJPY",
    "BTC/USD": "cryBTCUSD",
    "ETH/USD": "cryETHUSD",
}

state = {
    "symbol": DEFAULT_SYMBOL,
    "label": "EUR/USD",
    "timeframe": 1,
    "signal": "WAIT",
    "confidence": 0,
    "price": None,
    "entry": None,
    "payout": 0,
    "updated": None,
    "feed": "Deriv",
    "feed_status": "connecting",
    "ticks": 0,
    "history": [],
}

ticks = deque(maxlen=3000)
lock = threading.Lock()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def symbol_label(symbol):
    for label, code in SYMBOLS.items():
        if code == symbol:
            return label
    return symbol


def ema(values, period):
    if not values:
        return None

    k = 2 / (period + 1)
    value = values[0]

    for price in values[1:]:
        value = price * k + value * (1 - k)

    return value


def rsi(values, period=14):
    if len(values) < period + 1:
        return 50.0

    gains = []
    losses = []

    for old, new in zip(
        values[-period - 1:-1],
        values[-period:]
    ):
        change = new - old
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    if average_loss == 0:
        return 100.0

    rs = average_gain / average_loss
    return 100 - (100 / (1 + rs))


def make_signal(prices):
    if len(prices) < 30:
        return "WAIT", 0, ["Waiting for enough Deriv ticks"]

    fast = ema(prices[-60:], 9)
    slow = ema(prices[-60:], 21)
    current_rsi = rsi(prices)

    recent = prices[-8:]
    momentum = recent[-1] - recent[0]

    scale = max(abs(recent[0]) * 0.00005, 1e-12)

    score = 0
    reasons = []

    if fast > slow:
        score += 1
        reasons.append("EMA 9 above EMA 21")
    elif fast < slow:
        score -= 1
        reasons.append("EMA 9 below EMA 21")

    if current_rsi >= 55:
        score += 1
        reasons.append(
            f"RSI bullish ({current_rsi:.1f})"
        )
    elif current_rsi <= 45:
        score -= 1
        reasons.append(
            f"RSI bearish ({current_rsi:.1f})"
        )

    if momentum > scale:
        score += 1
        reasons.append("Short momentum up")
    elif momentum < -scale:
        score -= 1
        reasons.append("Short momentum down")

    if score >= 2:
        confidence = min(95, 60 + score * 9)
        return "CALL", confidence, reasons

    if score <= -2:
        confidence = min(95, 60 + abs(score) * 9)
        return "PUT", confidence, reasons

    return "WAIT", 50 + abs(score) * 3, reasons


def update_state(price):
    price = float(price)

    with lock:
        ticks.append(price)

        state["price"] = price
        state["updated"] = utc_now()
        state["ticks"] += 1

        signal, confidence, reasons = make_signal(
            list(ticks)
        )

        previous_signal = state["signal"]

        state["signal"] = signal
        state["confidence"] = int(confidence)

        if signal != "WAIT":
            state["entry"] = price
        else:
            state["entry"] = None

        if signal != previous_signal:
            state["last_signal"] = utc_now()

        state["history"].append({
            "time": state["updated"],
            "signal": signal,
            "confidence": int(confidence),
            "price": price,
            "reasons": reasons,
        })

        state["history"] = state["history"][-100:]


def deriv_loop():
    try:
        import websocket
    except Exception:
        with lock:
            state["feed_status"] = (
                "websocket package missing"
            )
        return

    while True:
        try:
            url = (
                f"{DERIV_WS}"
                f"?app_id={DERIV_APP_ID}"
            )

            with lock:
                state["feed_status"] = "connecting"

            ws = websocket.create_connection(
                url,
                timeout=20
            )

            ws.send(json.dumps({
                "ticks": state["symbol"],
                "subscribe": 1
            }))

            with lock:
                state["feed_status"] = "live"

            while True:
                raw = ws.recv()
                message = json.loads(raw)

                if "error" in message:
                    raise RuntimeError(
                        message["error"].get(
                            "message",
                            "Deriv error"
                        )
                    )

                if "tick" in message:
                    update_state(
                        message["tick"]["quote"]
                    )

        except Exception as error:
            with lock:
                state["feed_status"] = (
                    "reconnecting: "
                    + str(error)[:80]
                )

            time.sleep(3)


def change_symbol(symbol):
    with lock:
        state["symbol"] = symbol
        state["label"] = symbol_label(symbol)
        state["feed_status"] = "reconnecting"


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "RYU V2",
        "feed": state["feed"],
        "feed_status": state["feed_status"],
        "time": utc_now(),
    })


@app.route("/api/state")
def api_state():
    with lock:
        return jsonify(state)


@app.route("/api/history")
def api_history():
    with lock:
        return jsonify(state["history"])


@app.route("/api/symbol/<path:name>", methods=["POST"])
def api_symbol(name):
    code = SYMBOLS.get(name)

    if not code:
        return jsonify({
            "error": "Unsupported symbol"
        }), 400

    change_symbol(code)

    return jsonify({
        "ok": True,
        "symbol": code,
        "label": name,
    })


HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport"
content="width=device-width,initial-scale=1">

<title>RYU V2</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #07111f;
    color: #eaf2ff;
    font-family: Arial, sans-serif;
}

.app {
    max-width: 1200px;
    margin: auto;
    padding: 18px;
}

.top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 18px;
}

.brand {
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 2px;
}

.sub {
    color: #8293aa;
    font-size: 12px;
}

.status {
    padding: 8px 12px;
    border: 1px solid #233650;
    border-radius: 20px;
    font-size: 12px;
}

.nav,
.filters {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
}

button {
    background: #101e31;
    color: #b9c9dc;
    border: 1px solid #253b58;
    padding: 10px 14px;
    border-radius: 9px;
}

button.active {
    background: #17304d;
    color: white;
}

.grid {
    display: grid;
    grid-template-columns: 1.5fr .8fr;
    gap: 14px;
}

.card {
    background: #0b1728;
    border: 1px solid #1d314b;
    border-radius: 14px;
    padding: 16px;
}

.price {
    font-size: 34px;
    font-weight: 800;
    margin: 8px 0;
}

.muted {
    color: #8293aa;
}

.signal {
    font-size: 52px;
    font-weight: 950;
    margin: 10px 0;
}

.call {
    color: #4ee39b;
}

.put {
    color: #ff687d;
}

.wait {
    color: #f2c75c;
}

.conf {
    font-size: 20px;
}

.meter {
    height: 8px;
    background: #1a2940;
    border-radius: 10px;
    overflow: hidden;
    margin: 10px 0 16px;
}

.fill {
    height: 100%;
    background: #4ee39b;
    width: 0%;
}

.rows {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}

.row {
    background: #0e1d30;
    border-radius: 10px;
    padding: 12px;
}

.v {
    font-weight: 800;
    margin-top: 4px;
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

td,
th {
    padding: 10px;
    border-bottom: 1px solid #1c3049;
    text-align: left;
}

.chart {
    height: 280px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #53677f;
    border: 1px dashed #27405d;
    border-radius: 10px;
    margin-top: 12px;
}

@media(max-width:800px) {

    .grid {
        grid-template-columns: 1fr;
    }

    .signal {
        font-size: 44px;
    }
}

</style>
</head>

<body>

<div class="app">

<div class="top">

<div>
<div class="brand">RYU V2</div>
<div class="sub">
LIVE SIGNAL ENGINE • DERIV FEED
</div>
</div>

<div id="status" class="status">
CONNECTING
</div>

</div>


<div class="nav">

<button class="active">
Signals
</button>

<button>
Trades
</button>

<button>
Performance
</button>

<button>
Settings
</button>

</div>


<div class="filters">

<button class="active">
Forex
</button>

<button>
Crypto
</button>

<button>
Stocks
</button>

<button class="active">
1m
</button>

<button>
2m
</button>

<button>
3m
</button>

</div>


<div class="grid">

<div class="card">

<div class="muted">
MARKET
</div>

<h2 id="pair">
EUR/USD
</h2>

<div class="price" id="price">
—
</div>

<div class="muted">
Live Deriv quote
</div>

<div class="chart" id="chart">
Waiting for live ticks...
</div>

</div>


<div class="card">

<div class="muted">
CURRENT SIGNAL
</div>

<div id="signal"
class="signal wait">
WAIT
</div>

<div class="conf">
Confidence:
<b id="confidence">
0%
</b>
</div>

<div class="meter">
<div id="fill"
class="fill">
</div>
</div>


<div class="rows">

<div class="row">
<div class="muted">
ENTRY
</div>
<div class="v" id="entry">
—
</div>
</div>

<div class="row">
<div class="muted">
PAYOUT
</div>
<div class="v" id="payout">
—
</div>
</div>

<div class="row">
<div class="muted">
TIMEFRAME
</div>
<div class="v">
1 MIN
</div>
</div>

<div class="row">
<div class="muted">
FEED
</div>
<div class="v" id="feed">
Deriv
</div>
</div>

</div>

</div>

</div>


<div class="card"
style="margin-top:14px">

<h3>
Recent Signals
</h3>

<table>

<thead>

<tr>
<th>Time</th>
<th>Signal</th>
<th>Confidence</th>
<th>Price</th>
</tr>

</thead>

<tbody id="history">
</tbody>

</table>

</div>

</div>


<script>

async function refresh() {

    try {

        const response =
            await fetch("/api/state");

        const data =
            await response.json();

        document.getElementById("pair")
            .textContent = data.label;

        document.getElementById("price")
            .textContent =
            data.price == null
            ? "—"
            : Number(data.price).toFixed(5);

        const signal =
            document.getElementById("signal");

        signal.textContent =
            data.signal;

        signal.className =
            "signal " +
            data.signal.toLowerCase();

        document.getElementById(
            "confidence"
        ).textContent =
            data.confidence + "%";

        document.getElementById(
            "fill"
        ).style.width =
            data.confidence + "%";

        document.getElementById(
            "entry"
        ).textContent =
            data.entry == null
            ? "—"
            : Number(data.entry).toFixed(5);

        document.getElementById(
            "payout"
        ).textContent =
            data.payout
            ? data.payout + "%"
            : "—";

        document.getElementById(
            "feed"
        ).textContent =
            data.feed +
            " • " +
            data.feed_status;

        document.getElementById(
            "status"
        ).textContent =
            data.feed_status.toUpperCase();

        const history =
            document.getElementById(
                "history"
            );

        history.innerHTML =
            data.history
            .slice()
            .reverse()
            .slice(0, 12)
            .map(item => {

                return `
                <tr>
                    <td>
                    ${new Date(
                        item.time
                    ).toLocaleTimeString()}
                    </td>

                    <td>
                    <b>
                    ${item.signal}
                    </b>
                    </td>

                    <td>
                    ${item.confidence}%
                    </td>

                    <td>
                    ${Number(
                        item.price
                    ).toFixed(5)}
                    </td>
                </tr>
                `;

            })
            .join("");

        document.getElementById(
            "chart"
        ).textContent =
            data.ticks +
            " live ticks received • last update " +
            (
                data.updated
                ? new Date(
                    data.updated
                  ).toLocaleTimeString()
                : "—"
            );

    } catch (error) {

        document.getElementById(
            "status"
        ).textContent =
            "OFFLINE";

    }

}

setInterval(refresh, 1000);

refresh();

</script>

</body>
</html>
"""


if __name__ == "__main__":

    threading.Thread(
        target=deriv_loop,
        daemon=True
    ).start()

    port = int(
        os.getenv("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port
)
