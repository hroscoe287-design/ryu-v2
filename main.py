import os
import threading
import time
from io import BytesIO

import yfinance as yf
import matplotlib.pyplot as plt
from flask import Flask, jsonify, render_template_string
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# =========================
# RYU V2 CONFIG
# =========================

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")

app = Flask(__name__)

# =========================
# DASHBOARD
# =========================

DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RYU V2</title>

<style>
* { box-sizing:border-box; }

body {
    margin:0;
    background:#070b12;
    color:#fff;
    font-family:Arial,Helvetica,sans-serif;
}

.header {
    padding:18px;
    background:#0d131f;
    border-bottom:1px solid #202938;
    position:sticky;
    top:0;
    z-index:5;
}

.brand {
    font-size:28px;
    font-weight:800;
}

.status {
    color:#28d17c;
    font-size:12px;
    margin-top:5px;
}

.nav {
    display:flex;
    gap:8px;
    padding:12px;
    background:#0a0f18;
    overflow-x:auto;
}

.nav button,
.filter button {
    border:1px solid #293346;
    background:#151c29;
    color:#cbd3df;
    padding:10px 15px;
    border-radius:9px;
    white-space:nowrap;
}

.nav button:first-child {
    background:#273247;
    color:white;
}

.container {
    max-width:1000px;
    margin:auto;
    padding:15px;
}

.filters {
    display:flex;
    gap:8px;
    overflow-x:auto;
    margin-bottom:15px;
}

.card {
    background:#101722;
    border:1px solid #222c3d;
    border-radius:16px;
    padding:18px;
    margin-bottom:15px;
}

.card-title {
    color:#8793a7;
    font-size:12px;
    text-transform:uppercase;
    letter-spacing:1px;
}

.pair {
    font-size:25px;
    font-weight:800;
    margin-top:5px;
}

.price {
    font-size:18px;
    color:#b7c1cf;
    margin-top:4px;
}

.signal-box {
    text-align:center;
    padding:22px 10px;
}

.signal {
    font-size:48px;
    font-weight:900;
    margin:8px;
}

.wait { color:#f4b942; }
.call { color:#28d17c; }
.put { color:#ff4d5d; }

.confidence {
    font-size:17px;
    color:#cbd3df;
}

.chart {
    height:210px;
    margin-top:15px;
    background:
      linear-gradient(#182130 1px, transparent 1px),
      linear-gradient(90deg,#182130 1px,transparent 1px);
    background-size:40px 40px;
    border-radius:10px;
    position:relative;
    overflow:hidden;
}

.line {
    position:absolute;
    left:0;
    right:0;
    top:50%;
    height:2px;
    background:#28d17c;
    transform:rotate(-5deg);
    box-shadow:
      70px -18px 0 -0.
