from flask import Flask, render_template_string, jsonify
import os
import random
from datetime import datetime, timezone

app = Flask(__name__)

FOREX = [
    "AUD/CAD OTC", "AUD/CHF OTC", "AUD/JPY OTC", "AUD/NZD OTC",
    "AUD/USD OTC", "CAD/CHF OTC", "CAD/JPY OTC", "CHF/JPY OTC",
    "EUR/AUD OTC", "EUR/CAD OTC", "EUR/CHF OTC", "EUR/GBP OTC",
    "EUR/JPY OTC", "EUR/NZD OTC", "EUR/USD OTC",
    "GBP/AUD OTC", "GBP/CAD OTC", "GBP/CHF OTC", "GBP/JPY OTC",
    "GBP/NZD OTC", "GBP/USD OTC", "NZD/CAD OTC", "NZD/CHF OTC",
    "NZD/JPY OTC", "NZD/USD OTC", "USD/CAD OTC", "USD/CHF OTC",
    "USD/JPY OTC", "USD/SGD OTC", "USD/TRY OTC", "USD/ZAR OTC",
    "USD/MXN OTC", "USD/PLN OTC", "USD/NOK OTC", "USD/SEK OTC",
    "USD/HKD OTC", "USD/CNH OTC"
]

CRYPTO = [
    "BTC/USD OTC", "ETH/USD OTC", "LTC/USD OTC", "XRP/USD OTC",
    "BCH/USD OTC", "ADA/USD OTC", "SOL/USD OTC", "DOGE/USD OTC",
    "DOT/USD OTC", "LINK/USD OTC", "AVAX/USD OTC", "MATIC/USD OTC",
    "BNB/USD OTC", "TRX/USD OTC", "ATOM/USD OTC"
]

STOCKS = [
    "AAPL OTC", "TSLA OTC", "NVDA OTC", "AMZN OTC",
    "MSFT OTC", "META OTC", "GOOGL OTC", "NFLX OTC",
    "AMD OTC", "INTC OTC", "BA OTC", "DIS OTC",
    "COIN OTC", "PLTR OTC", "MCD OTC", "NKE OTC",
    "PFE OTC", "BABA OTC", "JPM OTC", "WMT OTC"
]

ASSETS = {
    "Forex": FOREX,
    "Crypto": CRYPTO,
    "Stocks": STOCKS
}

HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ryu V2</title>
<style>
*{box-sizing:border-box}
body{
 margin:0;
 background:#06140d;
 color:#fff;
 font-family:Arial,Helvetica,sans-serif
}
.header{
 background:linear-gradient(135deg,#062416,#0c4d29);
 border-bottom:1px solid #23834b;
 padding:16px
}
.brand{
 display:flex;
 align-items:center;
 gap:12px
}
.ryu{
 font-size:50px;
 filter:drop-shadow(0 0 12px #ff5b00)
}
.title{
 font-size:29px;
 font-weight:900;
 color:#4dff91
}
.sub{
 color:#9bcdb0;
 font-size:12px;
 margin-top:3px
}
.nav{
 display:flex;
 gap:7px;
 overflow-x:auto;
 padding:10px;
 background:#041009
}
.nav button{
 border:1px solid #225c3a;
 background:#0b2b1b;
 color:#bce5ca;
 padding:10px 15px;
 border-radius:8px;
 white-space:nowrap
}
.nav button.active{
 background:#18a957;
 color:#fff
}
.wrap{
 width:100%;
 max-width:1100px;
 margin:auto;
 padding:12px
}
.filters{
 display:grid;
 grid-template-columns:1fr 1fr 1fr;
 gap:8px;
 margin-bottom:12px
}
select{
 width:100%;
 padding:12px;
 background:#092519;
 border:1px solid #267448;
 border-radius:8px;
 color:#fff;
 font-size:14px
}
.card{
 background:#092117;
 border:1px solid #1b6039;
 border-radius:14px;
 padding:15px;
 margin-bottom:12px
}
.signalbox{
 text-align:center;
 background:radial-gradient(circle at center,#103d22,#071b11 70%)
}
.fireball{
 font-size:62px;
 line-height:1
}
.asset{
 color:#a8d7b9;
 margin-top:7px
}
.signal{
 font-size:43px;
 font-weight:900;
 margin:10px 0
}
.call{color:#3cff82}
.put{color:#ff5663}
.wait{color:#ffd45a}
.conf{
 font-size:19px;
 color:#bce9ca
}
.expiry{
 display:inline-block;
 margin-top:8px;
 padding:7px 12px;
 border-radius:20px;
 background:#123a24;
 color:#9bffb8;
 border:1px solid #287346
}
.grid{
 display:grid;
 grid-template-columns:repeat(4,1fr);
 gap:8px
}
.stat{
 background:#0c2c1b;
 border-radius:9px;
 padding:11px
}
.label{
 color:#7ea990;
 font-size:10px
}
.value{
 font-size:18px;
 font-weight:bold;
 margin-top:5px
}
.chart{
 height:270px;
 border:1px solid #1e7144;
 border-radius:10px;
 overflow:hidden;
 background:
 linear-gradient(rgba(67,255,145,.07) 1px,transparent 1px),
 linear-gradient(90deg,rgba(67,255,145,.07) 1px,transparent 1px);
 background-size:40px 40px
}
.chart svg{
 width:100%;
 height:100%
}
.row{
 display:flex;
 justify-content:space-between;
 gap:10px;
 padding:10px 0;
 border-bottom:1px solid #123b27
}
.badges{
 display:flex;
 flex-wrap:wrap;
 gap:7px
}
.badge{
 padding:7px 10px;
 border-radius:18px;
 background:#103821;
 border:1px solid #286d45;
 color:#91ffb0;
 font-size:12px
}
.online{
 color:#42ff8b;
 font-weight:bold
}
.footer{
 text-align:center;
 color:#658b73;
 font-size:11px;
 padding:18px
}
@media(max-width:700px){
 .filters{grid-template-columns:1fr}
 .grid{grid-template-columns:repeat(2,1fr)}
}
</style>
</head>

<body>

<div class="header">
 <div class="brand">
  <div class="ryu">🔥</div>
  <div>
   <div class="title">RYU V2</div>
   <div class="sub">AI MARKET SIGNAL COMMAND CENTER</div>
  </div>
 </div>
</div>

<div class="nav">
 <button class="active">Signals</button>
 <button>Trades</button>
 <button>Performance</button>
 <button>Settings</button>
</div>

<div class="wrap">

 <div class="filters">

  <select id="market">
   <option>Forex</option>
   <option>Crypto</option>
   <option>Stocks</option>
  </select>

  <select id="asset"></select>

  <select id="timeframe">
   <option value="1m">1 Minute</option>
   <option value="2m">2 Minutes</option>
   <option value="3m">3 Minutes</option>
  </select>

 </div>

 <div class="card signalbox">

  <div class="fireball">🔥</div>

  <div class="asset" id="assetName">USD/JPY OTC</div>

  <div id="signal" class="signal call">CALL ↑</div>

  <div id="confidence" class="conf">
   Confidence 87%
  </div>

  <div class="expiry">EXPIRY: 5 MINUTES</div>

 </div>

 <div class="card">
  <h3>Market Chart</h3>

  <div class="chart">
   <svg viewBox="0 0 1000 300" preserveAspectRatio="none">
    <polyline
     points="0,230 40,220 80,235 120,190 160,205
     200,170 240,180 280,140 320,155 360,120
     400,135 440,100 480,120 520,85 560,105
     600,75 640,95 680,60 720,80 760,48
     800,65 840,42 880,55 920,30 960,47 1000,25"
     fill="none"
     stroke="#39ff83"
     stroke-width="5"/>
   </svg>
  </div>
 </div>

 <div class="grid">

  <div class="stat">
   <div class="label">ENTRY PRICE</div>
   <div class="value" id="entry">158.421</div>
  </div>

  <div class="stat">
   <div class="label">PAYOUT</div>
   <div class="value">85%</div>
  </div>

  <div class="stat">
   <div class="label">CONFIDENCE</div>
   <div class="value" id="confidence2">87%</div>
  </div>

  <div class="stat">
   <div class="label">TIMEFRAME</div>
   <div class="value" id="tf">1 MIN</div>
  </div>

 </div>

 <div class="card">
  <h3>Ryu Confluence Engine</h3>

  <div class="badges">
   <span class="badge">Alligator ✓</span>
   <span class="badge">EMA Trend ✓</span>
   <span class="badge">MACD ✓</span>
   <span class="badge">RSI ✓</span>
   <span class="badge">Bollinger Bands ✓</span>
   <span class="badge">Momentum ✓</span>
   <span class="badge">Trend ✓</span>
   <span class="badge">Volatility ✓</span>
  </div>
 </div>

 <div class="card">

  <h3>Signal Details</h3>

  <div class="row">
   <span>Market</span>
   <strong id="marketText">Forex</strong>
  </div>

  <div class="row">
   <span>Asset</span>
   <strong id="assetText">USD/JPY OTC</strong>
  </div>

  <div class="row">
   <span>Signal Timeframe</span>
   <strong id="tfText">1 Minute</strong>
  </div>

  <div class="row">
   <span>Expiry</span>
   <strong>5 Minutes</strong>
  </div>

  <div class="row">
   <span>Engine</span>
   <strong>Ryu V2</strong>
  </div>

  <div class="row">
   <span>Status</span>
   <strong class="online">● ONLINE</strong>
  </div>

 </div>

</div>

<div class="footer">
 Ryu V2 • Dashboard Demo • Signal analysis only
</div>

<script>

const DATA = {
 Forex: __FOREX__,
 Crypto: __CRYPTO__,
 Stocks: __STOCKS__
};

const market = document.getElementById("market");
const asset = document.getElementById("asset");
const timeframe = document.getElementById("timeframe");

function loadAssets(){

 asset.innerHTML = "";

 DATA[market.value].forEach(function(name){
   const option = document.createElement("option");
   option.value = name;
   option.textContent = name;
   asset.appendChild(option);
 });

 update();
}

function update(){

 const name = asset.value;

 document.getElementById("assetName").textContent = name;
 document.getElementById("assetText").textContent = name;
 document.getElementById("marketText").textContent = market.value;
 document.getElementById("tfText").textContent = timeframe.options[timeframe.selectedIndex].text;
 document.getElementById("tf").textContent = timeframe.value.toUpperCase();

 const choices = [
  ["CALL ↑","call"],
  ["PUT ↓","put"],
  ["WAIT","wait"]
 ];

 const pick = choices[Math.floor(Math.random()*choices.length)];
 const signal = document.getElementById("signal");

 signal.textContent = pick[0];
 signal.className = "signal " + pick[1];

 const confidence = Math.floor(75 + Math.random()*18);

 document.getElementById("confidence").textContent =
   "Confidence " + confidence + "%";

 document.getElementById("confidence2").textContent =
   confidence + "%";

 document.getElementById("entry").textContent =
   (100 + Math.random()*100).toFixed(3);
}

market.addEventListener("change",loadAssets);
asset.addEventListener("change",update);
timeframe.addEventListener("change",update);

loadAssets();

</script>

</body>
</html>
"""

HTML = HTML.replace("__FOREX__", repr(FOREX))
HTML = HTML.replace("__CRYPTO__", repr(CRYPTO))
HTML = HTML.replace("__STOCKS__", repr(STOCKS))


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "service": "Ryu V2"
    })


@app.route("/api/assets")
def assets():
    return jsonify(ASSETS)


@app.route("/api/signal")
def api_signal():
    signal = random.choice(["CALL", "PUT", "WAIT"])

    return jsonify({
        "asset": "USD/JPY OTC",
        "signal": signal,
        "confidence": random.randint(75, 92),
        "timeframe": "1m",
        "expiry": "5 minutes",
        "status": "demo"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
