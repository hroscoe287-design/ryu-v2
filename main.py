import os
import threading
import time
from io import BytesIO

import yfinance as yf
import matplotlib.pyplot as plt
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================
# RYU V2 CONFIG
# =========================

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable is missing.")

# =========================
# RENDER HEALTH SERVER
# =========================

app = Flask(__name__)


@app.route("/")
def home():
    return "RYU V2 is online."


@app.route("/health")
def health():
    return "OK"


def run_server():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


# =========================
# MARKET SYMBOLS
# =========================

SYMBOLS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "DOGE": "DOGE-USD",
    "SOL": "SOL-USD",
    "XRP": "XRP-USD",

    "AAPL": "AAPL",
    "TSLA": "TSLA",
    "NVDA": "NVDA",
    "MSFT": "MSFT",
    "AMZN": "AMZN",
    "META": "META",
    "GOOGL": "GOOGL",

    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
}


def get_symbol(text):
    text = text.upper().strip()

    if text in SYMBOLS:
        return SYMBOLS[text]

    return text


# =========================
# PRICE DATA
# =========================

def get_price(symbol):
    ticker = yf.Ticker(symbol)

    data = ticker.history(
        period="1d",
        interval="5m",
        auto_adjust=False
    )

    if data.empty:
        return None

    price = float(data["Close"].dropna().iloc[-1])

    return price


# =========================
# CHART
# =========================

def create_chart(symbol):
    ticker = yf.Ticker(symbol)

    data = ticker.history(
        period="1d",
        interval="5m",
        auto_adjust=False
    )

    if data.empty:
        return None

    plt.figure(figsize=(10, 5))

    plt.plot(
        data.index,
        data["Close"],
        linewidth=2
    )

    plt.title(f"RYU V2 — {symbol}")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.grid(True)
    plt.xticks(rotation=30)
    plt.tight_layout()

    image = BytesIO()
    plt.savefig(image, format="png", dpi=150)
    plt.close()

    image.seek(0)

    return image


# =========================
# TELEGRAM COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🤖 RYU V2 IS ONLINE\n\n"
        "📊 Markets supported:\n"
        "• Crypto\n"
        "• Stocks\n"
        "• Forex\n\n"
        "Commands:\n\n"
        "/price BTC\n"
        "/price AAPL\n"
        "/price EURUSD\n\n"
        "/chart BTC\n"
        "/chart TSLA\n"
        "/chart EURUSD\n\n"
        "Examples:\n"
        "/price BTC\n"
        "/chart BTC"
    )

    await update.message.reply_text(message)


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Use:\n/price BTC\n/price AAPL\n/price EURUSD"
        )
        return

    requested = context.args[0].upper()
    symbol = get_symbol(requested)

    try:
        current = get_price(symbol)

        if current is None:
            await update.message.reply_text(
                f"❌ No market data found for {requested}."
            )
            return

        await update.message.reply_text(
            f"📈 RYU V2 PRICE\n\n"
            f"Asset: {requested}\n"
            f"Symbol: {symbol}\n"
            f"Price: {current:,.6f}"
        )

    except Exception as e:
        await update.message.reply_text(
            "❌ Could not retrieve market data."
        )
        print("PRICE ERROR:", e)


async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Use:\n/chart BTC\n/chart TSLA\n/chart EURUSD"
        )
        return

    requested = context.args[0].upper()
    symbol = get_symbol(requested)

    await update.message.reply_text(
        f"📊 Building live chart for {requested}..."
    )

    try:
        image = create_chart(symbol)

        if image is None:
            await update.message.reply_text(
                f"❌ No chart data found for {requested}."
            )
            return

        await update.message.reply_photo(
            photo=image,
            caption=f"📊 RYU V2 LIVE MARKET CHART\n{requested}"
        )

    except Exception as e:
        await update.message.reply_text(
            "❌ Chart generation failed."
        )
        print("CHART ERROR:", e)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 RYU V2 COMMANDS\n\n"
        "/start — Start RYU V2\n"
        "/price BTC — Current price\n"
        "/chart BTC — Market chart\n\n"
        "Stocks:\n"
        "AAPL, TSLA, NVDA, MSFT, AMZN, META, GOOGL\n\n"
        "Crypto:\n"
        "BTC, ETH, DOGE, SOL, XRP\n\n"
        "Forex:\n"
        "EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD"
    )


# =========================
# BOT STARTUP
# =========================

def start_bot():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("price", price)
    )

    application.add_handler(
        CommandHandler("chart", chart)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    print("RYU V2 TELEGRAM BOT STARTING...")

    application.run_polling(
        drop_pending_updates=True
    )


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    server_thread = threading.Thread(
        target=run_server,
        daemon=True
    )

    server_thread.start()

    time.sleep(2)

    start_bot()
