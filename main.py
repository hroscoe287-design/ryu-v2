from flask import Flask, jsonify
import os
import time

app = Flask(__name__)


@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Ryu V2</title>
        <style>
            body {
                margin: 0;
                background: #080b12;
                color: white;
                font-family: Arial, sans-serif;
                text-align: center;
            }

            .header {
                padding: 22px;
                background: #111722;
                border-bottom: 1px solid #252d3a;
            }

            .logo {
                font-size: 30px;
                font-weight: bold;
            }

            .red {
                color: #ff3030;
            }

            .online {
                display: inline-block;
                margin-top: 10px;
                padding: 7px 14px;
                border-radius: 20px;
                background: #123522;
                color: #49ff91;
                font-size: 13px;
                font-weight: bold;
            }

            .nav {
                display: flex;
                justify-content: center;
                gap: 8px;
                padding: 15px;
                flex-wrap: wrap;
            }

            .nav div {
                padding: 10px 16px;
                background: #151c28;
                border-radius: 10px;
                color: #aeb7c5;
            }

            .nav .active {
                background: #e52b35;
                color: white;
            }

            .container {
                max-width: 900px;
                margin: auto;
                padding: 15px;
            }

            .card {
                background: #111722;
                border: 1px solid #252d3a;
                border-radius: 20px;
                padding: 30px 20px;
                margin-top: 10px;
            }

            .ryu {
                font-size: 55px;
            }

            .signal {
                font-size: 55px;
                font-weight: 900;
                margin: 15px;
                color: #ffd43b;
            }

            .confidence {
                font-size: 20px;
                color: #c3cad5;
            }

            .expiry {
                margin-top: 12px;
                color: #8e99aa;
            }

            .grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
                margin-top: 15px;
            }

            .box {
                background: #111722;
                border: 1px solid #252d3a;
                border-radius: 14px;
                padding: 18px 8px;
            }

            .label {
                font-size: 11px;
                color: #7e8999;
            }

            .value {
                margin-top: 7px;
                font-size: 19px;
                font-weight: bold;
            }

            .section {
                background: #111722;
                border: 1px solid #252d3a;
                border-radius: 16px;
                margin-top: 15px;
                padding: 20px;
                text-align: left;
            }

            .section h2 {
                margin-top: 0;
            }

            .item {
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #202734;
            }

            .green {
                color: #49ff91;
            }

            .footer {
                padding: 25px;
                color: #596576;
                font-size: 11px;
            }

            @media (max-width: 600px) {
                .grid {
                    grid-template-columns: repeat(2, 1fr);
                }

                .signal {
                    font-size: 45px;
                }
            }
        </style>
    </head>

    <body>

        <div class="header">
            <div class="logo">
                🔥 RYU <span class="red">V2</span>
            </div>

            <div class="online">
                ● ONLINE
            </div>
        </div>

        <div class="nav">
            <div class="active">Signals</div>
            <div>Trades</div>
            <div>Performance</div>
            <div>Settings</div>
        </div>

        <div class="container">

            <div class="card">

                <div class="ryu">🥋🔥</div>

                <div class="signal">
                    WAIT
                </div>

                <div class="confidence">
                    Confidence: Waiting for live data
                </div>

                <div class="expiry">
                    Expiry: <b>5 MINUTES</b>
                </div>

            </div>

            <div class="grid">

                <div class="box">
                    <div class="label">MARKET</div>
                    <div class="value">OTC</div>
                </div>

                <div class="box">
                    <div class="label">TIMEFRAME</div>
                    <div class="value">1M</div>
                </div>

                <div class="box">
                    <div class="label">SIGNALS</div>
                    <div class="value">0</div>
                </div>

                <div class="box">
                    <div class="label">WIN RATE</div>
                    <div class="value">--</div>
                </div>

            </div>

            <div class="section">

                <h2>Ryu Confluence</h2>

                <div class="item">
                    <span>Alligator</span>
                    <span class="green">READY</span>
                </div>

                <div class="item">
                    <span>Moving Average</span>
                    <span class="green">READY</span>
                </div>

                <div class="item">
                    <span>MACD</span>
                    <span class="green">READY</span>
                </div>

                <div class="item">
                    <span>RSI</span>
                    <span class="green">READY</span>
                </div>

                <div class="item">
                    <span>Bollinger Bands</span>
                    <span class="green">READY</span>
                </div>

            </div>

            <div class="section">

                <h2>Live Market Feed</h2>

                <p>
                    Ryu V2 is online and waiting for market data.
                </p>

                <p>
                    Status:
                    <span class="green">
                        CONNECTOR READY
                    </span>
                </p>

            </div>

        </div>

        <div class="footer">
            Ryu V2 • Signal Only • No automatic trade execution
        </div>

    </body>
    </html>
    """


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "Ryu V2",
        "time": int(time.time())
    })


@app.route("/api/status")
def status():
    return jsonify({
        "ok": True,
        "bot": "Ryu V2",
        "status": "ONLINE",
        "expiry": "5 minutes",
        "signals": 0,
        "message": "Waiting for live market feed"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port
    )
