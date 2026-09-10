import os
import time
import math
import random
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string

try:
    import yfinance as yf
except Exception:
    yf = None


app = Flask(__name__)


# ============================================================
# RYU V2 CONFIG
# ============================================================

APP_NAME = "RYU V2"

# User requested trading signal timeframes.
TIMEFRAMES = ["1m", "2m", "3m"]

# Demo expiry requested by user.
EXPIRY_MINUTES = 5

# Markets displayed in the selector.
MARKETS = {
    "FOREX": [
        ("EUR/USD", "
