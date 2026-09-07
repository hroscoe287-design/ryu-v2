from flask import Flask, render_template_string, jsonify
from datetime import datetime
import random

app = Flask(__name__)

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RYU V2</title>
<style>
*{box-sizing:border-box}
body{
    margin:0;
    background:#070b12;
    color:#f4f7fb;
    font-family:Arial,Helvetica,sans-serif;
}
.header{
    height:70px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 22px;
    border-bottom:1px solid #202733;
    background:#0b1018;
}
.logo{
    font-size:25px;
    font-weight:800;
    letter-spacing:2px;
}
.logo span{color:#31e981}
.status{
    font-size:12px;
    color:#31e981;
    display:flex;
    align-items:center;
    gap:7px;
}
.dot{
    width:8px;height:8px;border-radius:50%;
    background:#31e981;
}
.nav{
    display:flex;
    gap:7px;
    padding:14px 18px 0;
    background:#0b1018;
}
.nav button{
    border:0;
    background:transparent;
    color:#8490a1;
    padding:11px 15px;
    border-radius:8px 8px 0 0;
    font-weight:700;
}
.nav button.active{
    background:#111925;
    color:white;
}
.container{
    max-width:1200px;
    margin:auto;
    padding:20px;
}
.filters{
    display:flex;
    flex-wrap:wrap;
    gap:10px;
    margin-bottom:18px;
}
.filter{
    background:#101722;
    border:1px solid #26303e;
    color:#aab4c2;
    padding:10px 16px;
    border-radius:8px;
    font-weight:700;
}
.filter.active{
    color:white;
    border-color:#31e981;
}
.grid{
    display:grid;
    grid-template-columns:1.5fr 1fr;
    gap:18px;
}
.card{
    background:#0d141e;
    border:1px solid #202a37;
    border-radius:13px;
    padding:18px;
}
.card-title{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:15px;
}
.card-title h2{
    margin:0;
    font-size:17px;
}
.pair{
    color:#31e981;
    font-size:13px;
    font-weight:700;
}
.signal{
    text-align:center;
    padding:23px 10px;
    border-radius:12px;
    background:#111a25;
    margin-bottom:15px;
}
.signal .direction{
    font-size:40px;
    font-weight:900;
    margin:4px 0;
}
.call{color:#31e981}
.put{color:#ff5964}
.wait{color:#f5c84b}
.confidence{
    font-size:14px;
    color:#a8b2c0;
}
.confidence strong{color:white}
.chart{
    height:250px;
    position:relative;
    overflow:hidden;
    border-radius:10px;
    background:#080d14;
    border:1px solid #1d2631;
}
canvas{
    width:100%;
    height:100%;
}
.metrics{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:10px;
}
.metric{
    background:#111923;
    padding:14px;
    border-radius:9px;
}
.metric small{
    color:#778394;
    display:block;
    margin-bottom:5px;
}
.metric strong{
    font-size:18px;
}
.progress{
    height:7px;
    background:#202936;
    border-radius:20px;
    overflow:hidden;
    margin-top:9px;
}
.progress div{
    height:100%;
    background:#31e981;
}
.table{
    width:100%;
    border-collapse:collapse;
}
.table th,.table td{
    padding:12px 7px;
    border-bottom:1px solid #202936;
    text-align:left;
    font-size:13px;
}
.table th{color:#758194}
.win{color:#31e981}
.loss{color:#ff5964}
.footer{
    text-align:center;
    color:#586474;
    font-size:11px;
    padding:25px;
}
@media(max-width:800px){
    .grid{grid-template-columns:1fr}
    .container{padding:13px}
    .header{padding:0 15px}
}
</style>
</head>

<body>

<header class="header">
    <div class="logo">RYU <span>V2</span></div>
    <div class="status"><span class="dot"></span> SYSTEM ONLINE</div>
</header>

<nav class="nav">
    <button class="active" onclick="showTab('signals',this)">Signals</button>
    <button onclick="showTab('trades',this)">Trades</button>
    <button onclick="showTab('performance',this)">Performance</button>
    <button onclick="showTab('settings',this)">Settings</button>
</nav>

<main class="container">

<section id="signals">

<div class="filters">
    <button class="filter active">Forex</button>
    <button class="filter">Crypto</button>
    <button class="filter">Stocks</button>
    <button class="filter active">1m</button>
    <button class="filter">2m</button>
    <button class="filter">3m</button>
</div>

<div class="grid">

<div class="card">
    <div class="card-title">
        <h2>Current Signal</h2>
        <div class="pair">EUR/USD</div>
    </div>

    <div class="signal">
        <div class="confidence">RYU V2 ANALYSIS</div>
        <div class="direction call" id="direction">CALL</div>
        <div class="confidence">
            Confidence: <strong id="confidence">87%</strong>
        </div>
    </div>

    <div class="chart">
        <canvas id="chart"></canvas>
    </div>
</div>

<div class="card">
    <div class="card-title">
        <h2>Signal Details</h2>
    </div>

    <div class="metrics">
        <div class="metric">
            <small>Entry Price</small>
            <strong id="price">1.16742</strong>
        </div>

        <div class="metric">
            <small>Payout</small>
            <strong>87%</strong>
        </div>

        <div class="metric">
            <small>Timeframe</small>
            <strong>1 MIN</strong>
        </div>

        <div class="metric">
            <small>Signal Strength</small>
            <strong>HIGH</strong>
        </div>
    </div>

    <br>

    <div class="metric">
        <small>Confluence</small>
        <strong>Technical + Momentum + Trend</strong>
        <div class="progress">
            <div style="width:87%"></div>
        </div>
    </div>
</div>

</div>

<br>

<div class="card">
    <div class="card-title">
        <h2>Recent Signals</h2>
        <span class="pair">LIVE</span>
    </div>

    <table class="table">
        <thead>
            <tr>
                <th>Asset</th>
                <th>Direction</th>
                <th>Confidence</th>
                <th>Result</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>EUR/USD</td>
                <td class="win">CALL</td>
                <td>87%</td>
                <td class="win">ACTIVE</td>
            </tr>
            <tr>
                <td>GBP/USD</td>
                <td class="win">CALL</td>
                <td>82%</td>
                <td class="win">WIN</td>
            </tr>
            <tr>
                <td>BTC/USD</td>
                <td class="loss">PUT</td>
                <td>79%</td>
                <td class="loss">LOSS</td>
            </tr>
        </tbody>
    </table>
</div>

</section>

<section id="trades" style="display:none">
<div class="card">
    <div class="card-title"><h2>Trades</h2></div>
    <table class="table">
        <thead>
        <tr><th>Asset</th><th>Direction</th><th>Stake</th><th>Result</th></tr>
        </thead>
        <tbody>
        <tr><td>EUR/USD</td><td class="win">CALL</td><td>$10</td><td class="win">+$8.70</td></tr>
        <tr><td>GBP/USD</td><td class="win">CALL</td><td>$10</td><td class="win">+$8.20</td></tr>
        <tr><td>BTC/USD</td><td class="loss">PUT</td><td>$10</td><td class="loss">-$10.00</td></tr>
        </tbody>
    </table>
</div>
</section>

<section id="performance" style="display:none">
<div class="grid">
<div class="card">
<h2>Performance</h2>
<br>
<div class="metrics">
<div class="metric"><small>Total Trades</small><strong>124</strong></div>
<div class="metric"><small>Wins</small><strong class="win">91</strong></div>
<div class="metric"><small>Losses</small><strong class="loss">33</strong></div>
<div class="metric"><small>Win Rate</small><strong>73.4%</strong></div>
</div>
</div>
<div class="card">
<h2>Net Profit</h2>
<br>
<div style="font-size:35px;font-weight:900" class="win">+$482.60</div>
</div>
</div>
</section>

<section id="settings" style="display:none">
<div class="card">
<h2>RYU V2 Settings</h2>
<br>
<div class="metric">
<small>Minimum Confidence</small>
<strong>80%</strong>
</div>
<br>
<div class="metric">
<small>Signal Mode</small>
<strong>High Confidence Only</strong>
</div>
<br>
<div class="metric">
<small>Markets</small>
<strong>Forex • Crypto • Stocks</strong>
</div>
</div>
</section>

</main>

<div class="footer">RYU V2 • Trading Intelligence Dashboard</div>

<script>
function showTab(id,btn){
    document.querySelectorAll("main section").forEach(s=>s.style.display="none");
    document.getElementById(id).style.display="block";
    document.querySelectorAll(".nav button").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
}

const canvas=document.getElementById("chart");
const ctx=canvas.getContext("2d");

function drawChart(){
    const w=canvas.width=canvas.clientWidth*2;
    const h=canvas.height=canvas.clientHeight*2;
    ctx.clearRect(0,0,w,h);

    ctx.strokeStyle="#17212d";
    ctx.lineWidth=2;

    for(let i=1;i<6;i++){
        let y=(h/6)*i;
        ctx.beginPath();
        ctx.moveTo(0,y);
        ctx.lineTo(w,y);
        ctx.stroke();
    }

    let points=[];
    let value=h*.58;

    for(let i=0;i<55;i++){
        value += (Math.random()-.46)*h*.055;
        value=Math.max(h*.12,Math.min(h*.88,value));
        points.push([i*(w/54),value]);
    }

    ctx.beginPath();
    points.forEach((p,i)=>{
        if(i===0)ctx.moveTo(p[0],p[1]);
        else ctx.lineTo(p[0],p[1]);
    });

    ctx.strokeStyle="#31e981";
    ctx.lineWidth=5;
    ctx.stroke();
}

drawChart();
window.addEventListener("resize",drawChart);
</script>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "app": "RYU V2",
        "time": datetime.utcnow().isoformat()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
