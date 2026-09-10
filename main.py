import os
import time
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string, request

try:
    import yfinance as yf
except Exception:
    yf = None

import pandas as pd
import numpy as np

app = Flask(__name__)

# ============================================================
# RYU V2 — LIVE MARKET SIGNAL DASHBOARD
# ============================================================
# Signals only. This build does NOT place Pocket Option trades.
# It uses available market data and calculates signals locally.
# ============================================================

PORT = int(os.environ.get("PORT", "10000"))
CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", "8"))

ASSETS = {
    # FOREX
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X",
    "USD/CHF": "CHF=X",
    "NZD/USD": "NZDUSD=X",

    # CRYPTO
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "SOL/USD": "SOL-USD",
    "XRP/USD": "XRP-USD",
    "DOGE/USD": "DOGE-USD",
    "ADA/USD": "ADA-USD",
    "BNB/USD": "BNB-USD",
    "AVAX/USD": "AVAX-USD",

    # STOCKS
    "AAPL": "AAPL",
    "TSLA": "TSLA",
    "NVDA": "NVDA",
    "AMZN": "AMZN",
    "MSFT": "MSFT",
    "META": "META",
    "GOOGL": "GOOGL",
    "NFLX": "NFLX",

    # ETFs
    "SPY": "SPY",
    "QQQ": "QQQ",
    "DIA": "DIA",
    "IWM": "IWM",
}

TIMEFRAMES = {
    "1m": "1m",
    "2m": "2m",
    "3m": "5m",
}

cache = {}
cache_lock = threading.Lock()


def now_utc():
    return datetime.now(timezone.utc)


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0).ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    loss = (-delta.clip(upper=0)).ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = gain / loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


def macd(series):
    fast = ema(series, 12)
    slow = ema(series, 26)

    line = fast - slow
    signal = ema(line, 9)
    histogram = line - signal

    return line, signal, histogram


def atr(df, period=14):
    high_low = df["High"] - df["Low"]

    high_close = (
        df["High"] - df["Close"].shift()
    ).abs()

    low_close = (
        df["Low"] - df["Close"].shift()
    ).abs()

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()


def alligator(df):
    median = (
        df["High"] + df["Low"]
    ) / 2

    jaw = median.rolling(13).mean().shift(8)
    teeth = median.rolling(8).mean().shift(5)
    lips = median.rolling(5).mean().shift(3)

    return jaw, teeth, lips


def bollinger(df, period=20, std_mult=2):
    middle = df["Close"].rolling(period).mean()
    std = df["Close"].rolling(period).std()

    upper = middle + std_mult * std
    lower = middle - std_mult * std

    return middle, upper, lower


def cci(df, period=20):
    typical_price = (
        df["High"] +
        df["Low"] +
        df["Close"]
    ) / 3

    mean = typical_price.rolling(period).mean()

    deviation = typical_price.rolling(period).apply(
        lambda x: np.mean(
            np.abs(x - np.mean(x))
        ),
        raw=True
    )

    return (
        (typical_price - mean) /
        (0.015 * deviation.replace(0, np.nan))
    )


def fetch_data(symbol, interval):

    key = f"{symbol}:{interval}"

    with cache_lock:
        cached = cache.get(key)

        if cached:
            if time.time() - cached["time"] < CACHE_SECONDS:
                return cached["df"].copy()

    if yf is None:
        raise RuntimeError(
            "yfinance is not installed"
        )

    df = yf.download(
        symbol,
        period="2d",
        interval=interval,
        progress=False,
        auto_adjust=False,
        threads=False,
    )

    if df is None or df.empty:
        raise RuntimeError(
            "No market data returned"
        )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            column[0]
            for column in df.columns
        ]

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in required:

        if column not in df.columns:

            if column == "Volume":
                df[column] = 0

            else:
                raise RuntimeError(
                    f"Missing {column}"
                )

    df = df[
        required
    ].dropna().copy()

    with cache_lock:
        cache[key] = {
            "time": time.time(),
            "df": df.copy()
        }

    return df


def resample_3m(df):

    result = df.resample("3min").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    })

    return result.dropna()


def calculate_signal(df, timeframe):

    if len(df) < 80:
        raise RuntimeError(
            "Not enough candles"
        )

    if timeframe == "3m":
        df = resample_3m(df)

    close = df["Close"]

    ema9 = ema(close, 9)
    ema21 = ema(close, 21)
    ema50 = ema(close, 50)

    macd_line, macd_signal, macd_hist = macd(
        close
    )

    rsi_value = rsi(close)

    atr_value = atr(df)

    jaw, teeth, lips = alligator(df)

    bb_middle, bb_upper, bb_lower = bollinger(df)

    cci_value = cci(df)

    price = float(close.iloc[-1])

    call_score = 0.0
    put_score = 0.0

    call_reasons = []
    put_reasons = []

    # ========================================================
    # EMA TREND
    # ========================================================

    if ema9.iloc[-1] > ema21.iloc[-1]:

        call_score += 1.0

        call_reasons.append(
            "EMA 9 > EMA 21"
        )

    elif ema9.iloc[-1] < ema21.iloc[-1]:

        put_score += 1.0

        put_reasons.append(
            "EMA 9 < EMA 21"
        )

    if price > ema50.iloc[-1]:

        call_score += 1.0

        call_reasons.append(
            "Price above EMA 50"
        )

    elif price < ema50.iloc[-1]:

        put_score += 1.0

        put_reasons.append(
            "Price below EMA 50"
        )

    # ========================================================
    # MACD
    # ========================================================

    if (
        macd_hist.iloc[-1] > 0
        and
        macd_hist.iloc[-1] >= macd_hist.iloc[-2]
    ):

        call_score += 1.25

        call_reasons.append(
            "MACD bullish"
        )

    elif (
        macd_hist.iloc[-1] < 0
        and
        macd_hist.iloc[-1] <= macd_hist.iloc[-2]
    ):

        put_score += 1.25

        put_reasons.append(
            "MACD bearish"
        )

    # ========================================================
    # RSI
    # ========================================================

    rsi_now = float(
        rsi_value.iloc[-1]
    )

    if 52 <= rsi_now <= 70:

        call_score += 0.9

        call_reasons.append(
            f"RSI {rsi_now:.1f} bullish zone"
        )

    elif 30 <= rsi_now <= 48:

        put_score += 0.9

        put_reasons.append(
            f"RSI {rsi_now:.1f} bearish zone"
        )

    # ========================================================
    # ALLIGATOR
    # ========================================================

    jaw_now = jaw.iloc[-1]
    teeth_now = teeth.iloc[-1]
    lips_now = lips.iloc[-1]

    if (
        pd.notna(jaw_now)
        and
        pd.notna(teeth_now)
        and
        pd.notna(lips_now)
    ):

        if lips_now > teeth_now > jaw_now:

            call_score += 1.5

            call_reasons.append(
                "Alligator bullish alignment"
            )

        elif lips_now < teeth_now < jaw_now:

            put_score += 1.5

            put_reasons.append(
                "Alligator bearish alignment"
            )

    # ========================================================
    # BOLLINGER
    # ========================================================

    if price > bb_middle.iloc[-1]:

        call_score += 0.5

        call_reasons.append(
            "Above Bollinger midline"
        )

    elif price < bb_middle.iloc[-1]:

        put_score += 0.5

        put_reasons.append(
            "Below Bollinger midline"
        )

    # ========================================================
    # CCI
    # ========================================================

    cci_now = float(
        cci_value.iloc[-1]
    ) if pd.notna(
        cci_value.iloc[-1]
    ) else 0

    if cci_now > 50:

        call_score += 0.75

        call_reasons.append(
            "CCI bullish"
        )

    elif cci_now < -50:

        put_score += 0.75

        put_reasons.append(
            "CCI bearish"
        )

    # ========================================================
    # FINAL DECISION
    # ========================================================

    edge = abs(
        call_score - put_score
    )

    if edge < 1.25:

        direction = "WAIT"

    elif call_score > put_score:

        direction = "CALL"

    else:

        direction = "PUT"

    best_score = max(
        call_score,
        put_score
    )

    confidence = (
        50 +
        (best_score / 8.4) * 48
    )

    conflict = min(
        call_score,
        put_score
    )

    confidence -= min(
        12,
        conflict * 1.8
    )

    if direction == "WAIT":
        confidence = min(
            confidence,
            58
        )

    confidence = round(
        max(
            50,
            min(
                98,
                confidence
            )
        ),
        1
    )

    if len(close) >= 2:

        previous = float(
            close.iloc[-2]
        )

        if previous != 0:

            change = (
                (price / previous) - 1
            ) * 100

        else:
            change = 0

    else:
        change = 0

    candle_time = df.index[-1]

    if hasattr(
        candle_time,
        "to_pydatetime"
    ):
        candle_time = (
            candle_time.to_pydatetime()
        )

    return {

        "direction": direction,

        "confidence": confidence,

        "price": round(
            price,
            8
        ),

        "entry": round(
            price,
            8
        ),

        "change": round(
            float(change),
            4
        ),

        "rsi": round(
            rsi_now,
            2
        ),

        "cci": round(
            cci_now,
            2
        ),

        "ema9": round(
            float(ema9.iloc[-1]),
            8
        ),

        "ema21": round(
            float(ema21.iloc[-1]),
            8
        ),

        "ema50": round(
            float(ema50.iloc[-1]),
            8
        ),

        "macd_hist": round(
            float(macd_hist.iloc[-1]),
            8
        ),

        "atr": round(
            float(atr_value.iloc[-1]),
            8
        ),

        "payout": None,

        "candle_time": str(
            candle_time
        ),

        "confluence": {

            "CALL": call_reasons,

            "PUT": put_reasons

        },

        "scores": {

            "CALL": round(
                call_score,
                2
            ),

            "PUT": round(
                put_score,
                2
            )

        }

    }


def get_asset_data(
    asset,
    timeframe
):

    if asset not in ASSETS:
        raise ValueError(
            "Unknown asset"
        )

    interval = TIMEFRAMES.get(
        timeframe,
        "1m"
    )

    df = fetch_data(
        ASSETS[asset],
        interval
    )

    signal = calculate_signal(
        df,
        timeframe
    )

    return signal, df


# ============================================================
# DASHBOARD
# ============================================================

HTML = r"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width,initial-scale=1">

<title>Ryu V2</title>

<style>

:root {

--bg:#07090d;
--panel:#10141b;
--panel2:#151a23;
--line:#252c37;
--text:#eef2f7;
--muted:#8993a3;
--green:#31e981;
--red:#ff4d61;
--gold:#ffc857;

}

* {
box-sizing:border-box;
}

body {

margin:0;

background:
radial-gradient(
circle at 50% -10%,
#202733 0,
#07090d 45%
);

font-family:Arial,sans-serif;

color:var(--text);

}

.wrap {

max-width:1250px;

margin:auto;

padding:16px;

}

.top {

display:flex;

align-items:center;

justify-content:space-between;

gap:12px;

margin-bottom:14px;

}

.brand {

display:flex;

align-items:center;

gap:12px;

}

.avatar {

width:52px;

height:52px;

border-radius:50%;

display:grid;

place-items:center;

background:
linear-gradient(
135deg,
#252c38,
#090b10
);

border:1px solid #3a4352;

font-size:28px;

}

h1 {

margin:0;

font-size:24px;

}

.sub {

color:var(--muted);

font-size:12px;

margin-top:3px;

}

.status {

font-size:12px;

color:var(--green);

border:1px solid #275a43;

border-radius:999px;

padding:8px 11px;

}

nav {

display:flex;

gap:8px;

overflow:auto;

margin-bottom:14px;

}

nav button,
.filter button {

background:var(--panel);

color:var(--muted);

border:1px solid var(--line);

padding:10px 14px;

border-radius:9px;

}

button.active {

color:white;

border-color:#566173;

}

.grid {

display:grid;

grid-template-columns:
300px 1fr;

gap:14px;

}

.panel {

background:
rgba(16,20,27,.92);

border:1px solid var(--line);

border-radius:14px;

padding:14px;

}

label {

display:block;

color:var(--muted);

font-size:12px;

margin:0 0 7px;

}

.select {

width:100%;

background:#0a0d12;

color:white;

border:1px solid var(--line);

padding:11px;

border-radius:9px;

margin-bottom:12px;

}

.filter {

display:flex;

gap:7px;

flex-wrap:wrap;

margin-bottom:12px;

}

.filter button {

padding:8px 11px;

}

.signal {

display:grid;

grid-template-columns:
1fr auto;

gap:12px;

align-items:center;

}

.signalword {

font-size:42px;

font-weight:900;

letter-spacing:1px;

}

.call {

color:var(--green);

}

.put {

color:var(--red);

}

.wait {

color:var(--gold);

}

.confidence {

font-size:16px;

color:var(--muted);

}

.chartbox {

height:390px;

background:#090c11;

border:1px solid var(--line);

border-radius:10px;

padding:10px;

overflow:hidden;

}

canvas {

width:100%;

height:100%;

}

.stats {

display:grid;

grid-template-columns:
repeat(4,1fr);

gap:8px;

margin-top:12px;

}

.stat {

background:var(--panel2);

border-radius:10px;

padding:11px;

}

.stat small {

display:block;

color:var(--muted);

font-size:11px;

}

.stat b {

font-size:16px;

}

.cards {

display:grid;

grid-template-columns:
1fr 1fr;

gap:12px;

margin-top:12px;

}

ul {

margin:8px 0;

padding-left:19px;

color:#cbd2dc;

font-size:13px;

line-height:1.6;

}

.footer {

margin-top:12px;

color:#667080;

font-size:11px;

}

@media(max-width:850px) {

.grid {

grid-template-columns:1fr;

}

.stats {

grid-template-columns:
repeat(2,1fr);

}

.chartbox {

height:300px;

}

}

</style>

</head>

<body>

<div class="wrap">

<div class="top">

<div class="brand">

<div class="avatar">
🥋
</div>

<div>

<h1>RYU V2</h1>

<div class="sub">
LIVE CONFLUENCE SIGNAL ENGINE
</div>

</div>

</div>

<div
class="status"
id="status">

● ENGINE ONLINE

</div>

</div>


<nav>

<button class="active">
Signals
</button>

<button onclick="alert(
'Trades journal is ready for integration with your own trade entries.'
)">
Trades
</button>

<button onclick="alert(
'Performance tracking is available after trade results are entered.'
)">
Performance
</button>

<button onclick="alert(
'Ryu V2 uses local indicator calculations and does not expose private Pocket Option credentials.'
)">
Settings
</button>

</nav>


<div class="grid">


<div class="panel">

<label>
MARKET TYPE
</label>

<div
class="filter"
id="types">

<button
class="active"
onclick="setType('All',this)">
All
</button>

<button
onclick="setType('Forex',this)">
Forex
</button>

<button
onclick="setType('Crypto',this)">
Crypto
</button>

<button
onclick="setType('Stocks',this)">
Stocks
</button>

<button
onclick="setType('ETF',this)">
ETF
</button>

</div>


<label>
ASSET
</label>

<select
id="asset"
class="select">
</select>


<label>
TIMEFRAME
</label>

<div
class="filter"
id="tf">

<button
class="active"
onclick="setTF('1m',this)">
1m
</button>

<button
onclick="setTF('2m',this)">
2m
</button>

<button
onclick="setTF('3m',this)">
3m
</button>

</div>


<label>
TEST EXPIRY
</label>

<select class="select">

<option>
5 minutes
</option>

</select>


<div class="footer">

The 5-minute expiry is a separate test
setting; it does not downgrade the
signal timeframe.

</div>

</div>


<div class="panel">


<div class="signal">

<div>

<div class="sub">
CURRENT RYU SIGNAL
</div>

<div
id="direction"
class="signalword wait">
WAIT
</div>

<div
id="conf"
class="confidence">
Confidence: --
</div>

</div>


<div style="text-align:right">

<div class="sub">
ENTRY
</div>

<div
id="entry"
style="font-size:20px">
--
</div>

<div
id="move"
class="sub">
--
</div>

</div>

</div>


<div class="chartbox">

<canvas
id="chart">
</canvas>

</div>


<div class="stats">

<div class="stat">

<small>
RSI
</small>

<b id="rsi">
--
</b>

</div>


<div class="stat">

<small>
CCI
</small>

<b id="cci">
--
</b>

</div>


<div class="stat">

<small>
MACD HIST
</small>

<b id="macd">
--
</b>

</div>


<div class="stat">

<small>
PAYOUT
</small>

<b id="payout">
--
</b>

</div>

</div>


<div class="cards">


<div class="panel">

<div class="sub">
CALL CONFLUENCE
</div>

<ul id="call">
</ul>

</div>


<div class="panel">

<div class="sub">
PUT CONFLUENCE
</div>

<ul id="put">
</ul>

</div>


</div>


<div
class="footer"
id="updated">

Waiting for market data…

</div>

</div>

</div>

</div>


<script>

const assets =
{{ assets|tojson }};

let currentType = "All";

let currentTF = "1m";

const select =
document.getElementById("asset");


function typeFor(name) {

if (

[
"EUR/USD",
"GBP/USD",
"USD/JPY",
"AUD/USD",
"USD/CAD",
"USD/CHF",
"NZD/USD"
].includes(name)

)

return "Forex";


if (name.includes("/USD"))
return "Crypto";


if (
["SPY","QQQ","DIA","IWM"]
.includes(name)
)

return "ETF";


return "Stocks";

}


function populate() {

select.innerHTML = "";

Object.keys(assets)

.filter(
x =>
currentType === "All"
||
typeFor(x) === currentType
)

.forEach(x => {

let option =
document.createElement("option");

option.value = x;

option.textContent = x;

select.appendChild(option);

});

load();

}


function setType(x,b) {

currentType = x;

document
.querySelectorAll("#types button")
.forEach(
z =>
z.classList.remove("active")
);

b.classList.add("active");

populate();

}


function setTF(x,b) {

currentTF = x;

document
.querySelectorAll("#tf button")
.forEach(
z =>
z.classList.remove("active")
);

b.classList.add("active");

load();

}


select.onchange = load;


function fmt(v) {

if (
v === null ||
v === undefined ||
Number.isNaN(Number(v))
)

return "--";

let n = Number(v);

return Math.abs(n) >= 100
? n.toFixed(2)
: n.toFixed(6);

}


async function load() {

const asset =
select.value;

if (!asset)
return;

document
.getElementById("status")
.textContent =
"● UPDATING";


try {

const response =
await fetch(
`/api/signal?asset=${
encodeURIComponent(asset)
}&timeframe=${currentTF}`
);

const data =
await response.json();


if (!response.ok)
throw new Error(
data.error ||
"Data error"
);


const direction =
document.getElementById(
"direction"
);

direction.textContent =
data.direction;

direction.className =
"signalword "
+
data.direction.toLowerCase();


document.getElementById(
"conf"
).textContent =
"Confidence: "
+
data.confidence
+
"%";


document.getElementById(
"entry"
