import os, random, time, threading
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string

app=Flask(__name__)
PORT=int(os.getenv('PORT','10000'))
TICK=float(os.getenv('TICK_SECONDS','1'))

ASSETS=[
('EUR/USD OTC','Forex','🇺🇸',1.08437,.00010,92),
('GBP/USD OTC','Forex','🇬🇧',1.26342,.00012,92),
('USD/JPY OTC','Forex','🇯🇵',149.623,.018,91),
('AUD/USD OTC','Forex','🇦🇺',.65831,.00010,91),
('EUR/GBP OTC','Forex','🇪🇺',.85741,.00008,88),
('USD/CHF OTC','Forex','🇨🇭',.88421,.00010,88),
('USDCAD OTC','Forex','🇨🇦',1.36122,.00011,87),
('EUR/JPY OTC','Forex','🇪🇺',162.742,.020,87),
('GBP/JPY OTC','Forex','🇬🇧',183.204,.025,87),
('AUD/JPY OTC','Forex','🇦🇺',98.421,.020,86),
('BTC/USDT OTC','Crypto','₿',62401.23,45,88),
('ETH/USDT OTC','Crypto','Ξ',2431.76,3,87),
('SOL/USDT OTC','Crypto','◎',142.88,.35,85),
('XRP/USDT OTC','Crypto','✕',.5482,.004,84),
('Apple OTC','Stocks','',218.42,.12,85),
('Tesla OTC','Stocks','◉',247.63,.18,84),
('Microsoft OTC','Stocks','▦',428.71,.15,83),
('NVIDIA OTC','Stocks','◈',139.52,.16,86),
('Amazon OTC','Stocks','◆',231.84,.14,84),
('Gold OTC','Commodities','◉',2674.83,.65,86),
('Silver OTC','Commodities','●',31.52,.025,84),
('Natural Gas OTC','Commodities','◆',3.42,.012,82),
('USOIL OTC','Oil & Gas','◉',68.24,.035,83),
('UKOIL OTC','Oil & Gas','🇬🇧',72.31,.035,82),
('NATGAS OTC','Oil & Gas','◉',3.42,.012,80)
]

market={}
lock=threading.Lock()

def seed(p,s,n=70):
    out=[]
    now=int(time.time()//60)*60
    for i in range(n):
        d=random.uniform(-1,1)*s*1.8
        o=p
        c=max(.00001,p+d)
        h=max(o,c)+random.random()*s*1.2
        l=min(o,c)-random.random()*s*1.2
        out.append({'t':now-(n-i)*60,'o':o,'h':h,'l':l,'c':c})
        p=c
    return out

for name,cat,flag,p,s,pay in ASSETS:
    market[name]={
        'name':name,
        'category':cat,
        'flag':flag,
        'price':p,
        'step':s,
        'payout':pay,
        'candles':seed(p,s),
        'direction':'CALL',
        'confidence':pay
    }

def feed():
    while True:
        with lock:
            for m in market.values():
                old=m['price']
                s=m['step']

                new=max(
                    .00001,
                    old+
                    random.gauss(0,s*.75)+
                    (random.random()-.5)*s*.25
                )

                m['price']=new

                minute=int(time.time()//60)*60
                c=m['candles']

                if not c or c[-1]['t']!=minute:
                    c.append({
                        't':minute,
                        'o':old,
                        'h':max(old,new),
                        'l':min(old,new),
                        'c':new
                    })

                    if len(c)>90:
                        del c[:-90]

                else:
                    c[-1]['c']=new
                    c[-1]['h']=max(c[-1]['h'],new)
                    c[-1]['l']=min(c[-1]['l'],new)

                recent=c[-12:]

                if len(recent)>=5:
                    move=recent[-1]['c']-recent[0]['o']

                    m['direction']='CALL' if move>=0 else 'PUT'

                    m['confidence']=min(
                        99,
                        max(
                            71,
                            int(
                                m['payout']+
                                min(6,abs(move)/max(s,1e-9))-
                                random.randint(0,4)
                            )
                        )
                    )

        time.sleep(TICK)

threading.Thread(target=feed,daemon=True).start()

HTML=r'''
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">

<title>RYU V2</title>

<style>

:root{
--bg:#020711;
--p:#061426;
--l:#125485;
--g:#00ff99;
--r:#ff304f;
--b:#11aaff;
--y:#ffd34d;
--t:#e9f7ff;
--m:#7fa7c8
}

*{
box-sizing:border-box
}

body{
margin:0;
background:#01050b;
color:var(--t);
font:13px Arial,sans-serif
}

.app{
padding:8px
}

.top{
height:92px;
border:1px solid #164b78;
border-radius:10px;
background:linear-gradient(90deg,#02070f,#061b31,#02070f);
display:grid;
grid-template-columns:1.6fr 1fr 1.2fr;
align-items:center;
padding:8px 16px
}

.logo{
font-size:38px;
font-weight:900;
font-style:italic
}

.logo span{
color:#f21b39
}

.sub{
font-size:10px;
letter-spacing:3px;
margin-left:55px;
color:#a9cde8
}

.ryu{
text-align:center;
font-size:22px;
font-weight:900
}

.ryu b{
color:#ff203d
}

.statuses{
display:flex;
justify-content:flex-end;
gap:8px
}

.status{
border:1px solid #1b5c91;
border-radius:11px;
padding:8px 12px;
min-width:145px;
background:#031021
}

.dot{
display:inline-block;
width:11px;
height:11px;
border-radius:50%;
background:var(--g);
box-shadow:0 0 12px var(--g);
margin-right:5px
}

.status small{
display:block;
color:var(--m);
margin-left:18px
}

.grid{
display:grid;
grid-template-columns:275px minmax(500px,1fr) 325px;
gap:8px;
margin-top:8px
}

.panel{
border:1px solid var(--l);
background:linear-gradient(180deg,#061426,#020914);
border-radius:10px;
box-shadow:inset 0 0 20px #0064ff0f
}

.pad{
padding:10px
}

.tabs,.filters,.tfrow{
display:flex;
gap:5px;
flex-wrap:wrap
}

.tab,.chip,.tf{
border:1px solid #125485;
background:#051426;
color:#a9cde8;
border-radius:8px;
padding:8px 11px;
font-size:12px
}

.active{
color:#fff!important;
border-color:#08a8ff!important;
background:#073568!important
}

.search{
width:100%;
padding:11px;
border-radius:8px;
border:1px solid #165a91;
background:#020b17;
color:white;
margin:8px 0
}

.asset-list{
max-height:740px;
overflow:auto
}

.section{
color:#70caff;
font-weight:bold;
padding:9px 3px;
border-bottom:1px solid #123f61
}

.asset{
display:grid;
grid-template-columns:27px 1fr 48px 14px;
gap:4px;
align-items:center;
padding:8px 3px;
border-bottom:1px solid #145a3822;
cursor:pointer
}

.asset:hover,
.asset.sel{
background:#062744
}

.flag{
font-size:17px
}

.pay,
.g{
color:var(--g);
font-weight:bold
}

.star{
color:var(--y)
}

.head{
display:grid;
grid-template-columns:1fr 90px 130px 130px;
gap:10px;
align-items:center
}

.name{
font-size:16px;
font-weight:bold
}

.metric label{
font-size:10px;
color:var(--m)
}

.metric strong{
display:block;
color:var(--g);
font-size:17px
}

.tfrow{
margin:8px 0
}

.chart{
height:505px;
position:relative;
overflow:hidden;
background:#020a15;
border:1px solid #103d62;
border-radius:8px
}

canvas{
width:100%;
height:100%
}

.info{
position:absolute;
top:8px;
left:10px;
color:#a8d7f3;
line-height:1.7;
font-size:12px
}

.badge{
position:absolute;
right:18px;
top:48px;
border:2px solid var(--g);
border-radius:13px;
padding:10px 18px;
color:var(--g);
background:#001410e8;
box-shadow:0 0 20px #00ff9959;
font-weight:bold
}

.entry{
position:absolute;
right:15px;
top:118px;
border:1px solid var(--g);
border-radius:12px;
padding:10px 14px;
background:#001410dd
}

.bottom{
display:grid;
grid-template-columns:1fr 1fr 1fr;
gap:7px;
margin-top:7px
}

.card{
padding:10px;
border:1px solid #125485;
border-radius:9px;
background:#04101e;
min-height:105px
}

.card h4{
margin:0 0 8px;
color:#75caff;
font-size:12px
}

.check{
color:var(--g);
margin:5px 0;
font-size:11px
}

.right{
padding:12px
}

.title{
text-align:center;
font-size:28px;
font-weight:900;
color:var(--g)
}

.hero{
border:1px solid #1c6b50;
border-radius:10px;
padding:14px;
background:radial-gradient(circle,#063522,#03160f)
}

.big{
text-align:center;
font-size:30px;
font-weight:900;
color:var(--g)
}

.row{
display:flex;
justify-content:space-between;
padding:9px 3px;
border-bottom:1px solid #12364f;
font-size:12px
}

.timer{
font-size:26px;
color:var(--r);
font-weight:bold
}

.enter{
width:100%;
margin-top:12px;
padding:13px;
border:1px solid #00d986;
border-radius:8px;
background:#075238;
color:white;
font-weight:900;
font-size:16px
}

.activebox{
margin-top:12px;
padding:12px;
border:1px solid #126d55;
border-radius:10px;
text-align:center;
color:var(--g)
}

.histrow{
display:grid;
grid-template-columns:1.4fr .6fr .7fr .6fr;
padding:7px 0;
border-bottom:1px solid #11334f;
font-size:10px
}

.win{
color:var(--g)
}

.loss{
color:#ff536b
}

.footer{
height:48px;
margin-top:8px;
border:1px solid #173f63;
border-radius:9px;
display:flex;
align-items:center;
gap:25px;
padding:0 15px
}

.brand{
font-size:22px;
font-weight:900
}

.brand span{
color:#ff1837
}

@media(max-width:1100px){

.grid{
grid-template-columns:230px 1fr
}

.right{
grid-column:1/-1
}

.statuses{
display:none
}

.top{
grid-template-columns:1fr 1fr
}

}

@media(max-width:700px){

.grid{
grid-template-columns:1fr
}

.head{
grid-template-columns:1fr 1fr
}

.top{
height:auto;
grid-template-columns:1fr
}

.bottom{
grid-template-columns:1fr
}

.chart{
height:420px
}

}

</style>
</head>

<body>

<div class="app">

<header class="top">

<div>
<div class="logo">RYU <span>V2</span> 隆</div>
<div class="sub">AI TRADING ASSISTANT</div>
</div>

<div class="ryu">
🔥 RYU V2 <b>LIVE SIGNAL</b>
<br>
<small>NO LIMITS. JUST BETTER TRADES.</small>
</div>

<div class="statuses">

<div class="status">
<span class="dot"></span>
LIVE FEED
<small>DEMO STREAM</small>
</div>

<div class="status">
<span class="dot"></span>
MARKET STATUS
<small>OPEN • OTC</small>
</div>

</div>

</header>

<div class="grid">

<aside class="panel pad">

<div class="tabs">
<button class="tab active">ASSETS</button>
<button class="tab">WATCHLIST</button>
<button class="tab">FAVORITES</button>
</div>

<input
id="search"
class="search"
placeholder="⌕ Search assets..."
>

<div class="filters">

<button class="chip active" onclick="cat('All',this)">All</button>
<button class="chip" onclick="cat('Forex',this)">Forex</button>
<button class="chip" onclick="cat('Crypto',this)">Crypto</button>
<button class="chip" onclick="cat('Stocks',this)">Stocks</button>
<button class="chip" onclick="cat('Commodities',this)">Commodities</button>

</div>

<div id="assets" class="asset-list"></div>

</aside>

<main class="panel pad">

<div class="head">

<div class="name" id="nm"></div>

<div class="metric">
<label>PAYOUT</label>
<strong id="pay"></strong>
</div>

<div class="metric">
<label>LIVE PRICE</label>
<strong id="pr"></strong>
</div>

<div class="metric">
<label>CHANGE</label>
<strong id="chg">+0.00000</strong>
</div>

</div>

<div class="tfrow">

<button class="tf active">1m</button>
<button class="tf">2m</button>
<button class="tf">3m</button>
<button class="tf">5m</button>
<button class="tf">10m</button>
<button class="tf">15m</button>
<button class="tf">30m</button>
<button class="tf">1h</button>
<button class="tf">2h</button>
<button class="tf">4h</button>
<button class="tf">6h</button>
<button class="tf">12h</button>
<button class="tf">1D</button>
<button class="tf">1W</button>
<button class="tf">1M</button>

</div>

<div class="chart">

<canvas id="cv"></canvas>

<div id="info" class="info"></div>

<div id="badge" class="badge"></div>

<div class="entry">
ENTRY: <b id="entry"></b>
<br>
◷ EXPIRY: <b>5m</b>
</div>

</div>

<div class="bottom">

<div class="card">

<h4>SELECTED ASSET</h4>

<b id="ac"></b>

<div class="g" style="margin-top:7px">
Payout <b id="pc"></b>
</div>

</div>

<div class="card">

<h4>TIMEFRAME</h4>

<div class="tfrow">

<button class="tf active">1m</button>
<button class="tf">2m</button>
<button class="tf">3m</button>
<button class="tf active">5m</button>
<button class="tf">10m</button>
<button class="tf">15m</button>

</div>

</div>

<div class="card">

<h4>RECENT SIGNALS</h4>

<div class="histrow">
<span>EUR/USD OTC</span>
<b>5m</b>
<b class="win">CALL</b>
<b>LIVE</b>
</div>

<div class="histrow">
<span>GBP/JPY OTC</span>
<b>15m</b>
<b>PUT</b>
<b class="win">WIN</b>
</div>

<div class="histrow">
<span>BTC/USDT OTC</span>
<b>5m</b>
<b class="win">CALL</b>
<b class="win">WIN</b>
</div>

</div>

<div class="card">

<h4>TECHNICAL ANALYSIS</h4>

<div class="check">
✓ RSI (14) &nbsp; <b>62.4</b>
</div>

<div class="check">
✓ MACD &nbsp; <b>0.00032</b>
</div>

<div class="check">
✓ EMA (9/20/50) &nbsp; <b>Bullish</b>
</div>

<div class="check">
✓ ADX &nbsp; <b>28.7</b>
</div>

</div>

<div class="card">

<h4>CONFLUENCE</h4>

<div class="check">✓ Trend (Up)</div>
<div class="check">✓ Momentum (Strong)</div>
<div class="check">✓ Volume (High)</div>
<div class="check">✓ Volatility (Normal)</div>

</div>

<div class="card">

<h4>PRICE ACTION</h4>

<div class="check">
Signal Candle <b id="sp"></b>
</div>

<div class="check">
Next Candle <b id="np"></b>
</div>

</div>

</div>

</main>

<aside class="panel right">

<div class="title">RYU V2</div>

<div class="hero">

<div style="text-align:center">
LIVE SIGNAL
</div>

<div id="big" class="big">
↗ CALL
</div>

</div>

<div
style="margin-top:10px;font-weight:bold"
id="ra">
</div>

<small>
5m (Current Candle)
</small>

<div style="margin-top:8px">

<div class="row">
<span>⚡ ENTRY PRICE</span>
<b id="rp" class="g"></b>
</div>

<div class="row">
<span>◷ EXPIRY TIME</span>
<b class="g">5 minutes</b>
</div>

<div class="row">
<span>◉ CONFIDENCE</span>
<b id="conf" class="g"></b>
</div>

<div class="row">
<span>✦ PAYOUT</span>
<b id="rpay"></b>
</div>

<div class="row">
<span>◉ TIME REMAINING</span>
<span id="timer" class="timer">04:59</span>
</div>

<div class="row">
<span>◉ ENTRY CANDLE</span>
<b id="ct"></b>
</div>

</div>

<button class="enter" onclick="enterTrade()">
ENTER TRADE
</button>

<div id="trade" class="active
