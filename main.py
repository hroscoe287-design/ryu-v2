from flask import Flask, render_template, jsonify, request
import os
import random
import time
from datetime import datetime

app = Flask(__name__)


# ---------------------------------------------------------
# RYU V2 ASSETS
# ---------------------------------------------------------

ASSETS = {
    "Forex": [
        "EUR/USD OTC",
        "GBP/USD OTC",
        "USD/JPY OTC",
        "AUD/USD OTC",
        "USD/CAD OTC",
        "USD/CHF OTC",
        "NZD/USD OTC",
    ],

    "Crypto": [
        "BTC/USD OTC",
        "ETH/USD OTC",
        "SOL/USD OTC",
        "XRP/USD OTC",
        "LTC/USD OTC",
        "DOGE/USD OTC",
    ],

    "Stocks": [
        "AAPL OTC",
        "TSLA OTC",
        "NVDA OTC",
        "AMZN OTC",
        "META OTC",
        "MSFT OTC",
        "GOOGL OTC",
    ],

    "Commodities": [
        "GOLD OTC",
        "SILVER OTC",
        "PLATINUM OTC",
        "COPPER OTC",
    ],

    "Indices": [
        "SP500 OTC",
        "NASDAQ OTC",
        "DOW JONES OTC",
        "RUSSELL 2000 OTC",
    ],
}


TIMEFRAMES = [
    "1m",
    "2m",
    "3m",
    "5m",
    "10m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "12h",
    "1D",
    "1W",
    "1M",
]


# ---------------------------------------------------------
# DEMO PRICES
# ---------------------------------------------------------

BASE_PRICES = {
    "EUR/USD OTC": 1.08420,
    "GBP/USD OTC": 1.26840,
    "USD/JPY OTC": 147.820,
    "AUD/USD OTC": 0.65240,
    "USD/CAD OTC": 1.35820,
    "USD/CHF OTC": 0.87920,
    "NZD/USD OTC": 0.61120,

    "BTC/USD OTC": 105420.00,
    "ETH/USD OTC": 3850.00,
    "SOL/USD OTC": 218.40,
    "XRP/USD OTC": 2.410,
    "LTC/USD OTC": 112.40,
    "DOGE/USD OTC": 0.2140,

    "AAPL OTC": 237.40,
    "TSLA OTC": 348.20,
    "NVDA OTC": 177.80,
    "AMZN OTC": 231.40,
    "META OTC": 742.10,
    "MSFT OTC": 511.20,
    "GOOGL OTC": 241.80,

    "GOLD OTC": 3650.00,
    "SILVER OTC": 42.10,
    "PLATINUM OTC": 1390.00,
    "COPPER OTC": 4.58
