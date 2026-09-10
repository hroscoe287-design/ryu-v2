import os
import random
import time
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

PORT = int(os.environ.get("PORT", "10000"))
TICK_SECONDS = float(os.environ.get("TICK_SECONDS", "1"))

ASSETS = [
    ("EUR/USD OTC", "Forex", "🇺🇸", 1.08437, 0.00010, 92),
    ("GBP/USD OTC", "Forex", "🇬🇧", 1.26342, 0.00012, 92),
    ("USD/JPY OTC", "Forex", "🇯🇵", 149.623, 0.018, 91),
    ("AUD/USD OTC", "Forex", "🇦🇺", 0.65831, 0.00010, 91),
    ("EUR/GBP OTC", "Forex", "🇪🇺", 0.85741, 0.00008, 88),
    ("USD/CHF OTC", "Forex", "🇨🇭", 0.88421, 0.00010, 88),
    ("USDCAD OTC", "Forex", "🇨🇦", 1.36122, 0.00011, 87),
    ("EUR/JPY OTC", "Forex", "🇪🇺", 162.742, 0.020, 87),
    ("GBP/JPY OTC", "Forex", "🇬🇧", 183.204, 0.025, 87),
    ("AUD/JPY OTC", "Forex", "🇦🇺", 98.421, 0.020, 86),

    ("BTC/USDT OTC", "Crypto", "₿", 62401.23, 45, 88),
    ("ETH/USDT OTC", "Crypto", "Ξ", 2431.76, 3, 87),
    ("SOL/USDT OTC", "Crypto", "◎", 142.88, 0.35, 85),
    ("XRP/USDT OTC", "Crypto", "✕", 0.5482, 0.004, 84),

    ("Apple OTC", "Stocks", "", 218.42, 0.12, 85),
    ("Tesla OTC", "Stocks", "◉", 247.63, 0.18, 84),
    ("Microsoft OTC", "Stocks", "▦", 428.71, 0.15, 83),
    ("NVIDIA OTC", "Stocks", "◈", 139.52, 0.16, 86),
    ("Amazon OTC", "Stocks", "◆", 231.84, 0.14, 84),

    ("Gold OTC", "Commodities", "◉", 2674.83, 0.65, 86),
    ("Silver OTC", "Commodities", "●", 31.52, 0.025, 84),
    ("Natural Gas OTC", "Commodities", "◆", 3.42, 0.012, 82),

    ("USOIL OTC", "Oil & Gas", "◉", 68.24, 0.035, 83),
    ("UKOIL OTC", "Oil & Gas", "🇬🇧", 72.31, 0.035, 82),
    ("NATGAS OTC", "Oil & Gas", "◉", 3.42, 0.012, 80),
]


def make_candles(price, step, count=70):
    candles = []
    base_time = int(time.time() // 60) * 60
    p = price

    for i in range(count):
        move = random.uniform(-1.0, 1.0) * step * 1.8

        o = p
        c = max(0.00001, p + move)
        h = max(o, c) + random.random() * step
        l = min(o, c) - random.random() * step

        candles.append({
            "t": base_time - (count - i) * 60,
            "o": o,
            "h": h,
            "l": l,
            "c": c
        })

        p = c

    return candles


market = {}

for name, category, flag, price, step, payout in ASSETS:
    market[name] = {
        "name": name,
        "category": category,
        "flag": flag,
        "price": price,
        "step": step,
        "payout": payout,
        "direction": "CALL",
        "confidence": payout,
        "candles": make_candles(price, step)
    }


lock = threading.Lock()


def update_feed():
    while True:

        with lock:

            for item in market.values():

                old = item["price"]
                step = item["step"]

                new = max(
                    0.00001,
                    old + random.gauss(0, step * 0.65)
                )

                item["price"] = new

                minute = int(time.time() // 60) * 60
                candles = item["candles"]

                if not candles or candles[-1]["t"] != minute:

                    candles.append({
                        "t": minute,
                        "o": old,
                        "h": max(old, new),
                        "l": min(old, new),
                        "c": new
                    })

                    if len(candles) > 90:
                        del candles[:-90]

                else:

                    candle = candles[-1]

                    candle["c"] = new
                    candle["h"] = max(candle["h"], new)
                    candle["l"] = min(candle["l"], new)

                recent = candles[-10:]

                if len(recent) >= 5:
