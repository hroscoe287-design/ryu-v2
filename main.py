import os
import json
import time
import logging
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("RYU_V2_FULL_UI")

app = FastAPI()

# -------------------------------------------------------------------
# ALL POCKETOPTION ASSET TIERS & INITIAL SYSTEM DATA
# -------------------------------------------------------------------
POCKETOPTION_ASSET_MARKET = {
    "FOREX": [
        {"id": "EUR/USD_OTC", "name": "EUR/USD OTC", "payout": "92%", "trend": "up"},
        {"id": "GBP/USD_OTC", "name": "GBP/USD OTC", "payout": "92%", "trend": "up"},
        {"id": "USD/JPY_OTC", "name": "USD/JPY OTC", "payout": "91%", "trend": "up"},
        {"id": "AUD/USD_OTC", "name": "AUD/USD OTC", "payout": "91%", "trend": "up"},
        {"id": "EUR/GBP_OTC", "name": "EUR/GBP OTC", "payout": "88%", "trend": "up"},
    ],
    "CRYPTO": [
        {"id": "BTC/USDT_OTC", "name": "BTC/USDT OTC", "payout": "88%", "trend": "up"},
        {"id": "ETH/USDT_OTC", "name": "ETH/USDT OTC", "payout": "87%", "trend": "up"},
        {"id": "SOL/USDT_OTC", "name": "SOL/USDT OTC", "payout": "85%", "trend": "down"},
    ],
    "STOCKS": [
        {"id": "AAPL_OTC", "name": "Apple OTC", "payout": "85%", "trend": "up"},
        {"id": "TSLA_OTC", "name": "Tesla OTC", "payout": "84%", "trend": "up"},
        {"id": "MSFT_OTC", "name": "Microsoft OTC", "payout": "83%", "trend": "up"},
    ],
    "COMMODITIES": [
        {"id": "XAU/USD_OTC", "name": "Gold OTC", "payout": "86%", "trend": "up"},
        {"id": "XAG/USD_OTC", "name": "Silver OTC", "payout": "84%", "trend": "up"},
    ],
    "OIL_GAS": [
        {"id": "USOIL_OTC", "name": "USOIL OTC", "payout": "83%", "trend": "up"},
        {"id": "UKOIL_OTC", "name": "UKOIL OTC", "payout": "82%", "trend": "down"},
    ]
}

class RyuFullInterfaceEngine:
    def __init__(self):
        self.active_asset = "EUR/USD_OTC"
        self.active_payout = "92%"
        self.candles = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'timestamp'])
        self.active_connections: list[WebSocket] = []
        self.historical_trades = [
            {"asset": "EUR/USD OTC", "dir": "CALL", "res": "WIN", "payout": "92%", "time": "14:12"},
            {"asset": "GBP/JPY OTC", "dir": "PUT", "res": "WIN", "payout": "92%", "time": "13:58"},
            {"asset": "BTC/USDT Asset", "dir": "CALL", "res": "WIN", "payout": "88%", "time": "13:42"},
            {"asset": "XAU/USD OTC", "dir": "PUT", "res": "LOSS", "payout": "86%", "time": "13:28"},
        ]

    def compute_all_indicators(self, base_price: float) -> dict:
        """Processes math functions for the full technical dashboard stack."""
        now = time.time()
        # Seed running dataframes
        if len(self.candles) < 30:
            prices = base_price + np.random.normal(0, 0.0002, 40).cumsum()
            self.candles = pd.DataFrame({
                'close': prices, 'high': prices + 0.0001, 'low': prices - 0.0001, 'open': prices,
                'timestamp': [now - (i * 60) for i in range(40)][::-1]
            })
        
        # Append latest tick
        new_row = pd.DataFrame([{'open': base_price, 'high': base_price+0.00005, 'low': base_price-0.00005, 'close': base_price, 'timestamp': now}])
        self.candles = pd.concat([self.candles, new_row], ignore_index=True).iloc[-50:]
        df = self.candles.copy().reset_index(drop=True)

        # Technical Indicators Calculations
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # Alligator
        df['alligator_jaw'] = df['close'].ewm(alpha=1/13, adjust=False).mean().shift(8)
        df['alligator_teeth'] = df['close'].ewm(alpha=1/8, adjust=False).mean().shift(5)
        df['alligator_lips'] = df['close'].ewm(alpha=1/5, adjust=False).mean().shift(3)

        # Oscillators (RSI & MACD)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)

        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd_line'] = ema_12 - ema_26
        df['macd_sig'] = df['macd_line'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd_line'] - df['macd_sig']

        latest = df.iloc[-1].fillna(base_price).to_dict()
        
        # Confluence Bias Check
        signal = "HOLD"
        confidence = "45%"
        if base_price > latest.get('ema_9', base_price) and latest.get('macd_line', 0) > latest.get('macd_sig', 0):
            signal = "CALL"
            confidence = "92%"
        elif base_price < latest.get('ema_9', base_price) and latest.get('macd_line', 0) < latest.get('macd_sig', 0):
            signal = "PUT"
            confidence = "91%"

        return {
            "price": round(base_price, 5),
            "signal": signal,
            "confidence": confidence,
            "ema9": round(latest.get('ema_9', base_price), 5),
            "ema20": round(latest.get('ema_20', base_price), 5),
            "ema50": round(latest.get('ema_50', base_price), 5),
            "jaw": round(latest.get('alligator_jaw', base_price), 5),
            "teeth": round(latest.get('alligator_teeth', base_price), 5),
            "lips": round(latest.get('alligator_lips', base_price), 5),
            "rsi": round(latest.get('rsi', 50), 2),
            "macd": round(latest.get('macd_line', 0), 6),
            "macdsig": round(latest.get('macd_sig', 0), 6),
            "candles": df[['timestamp', 'open', 'high', 'low', 'close', 'ema_9', 'ema_20', 'ema_50']].tail(30).to_dict(orient="records")
        }

interface_engine = RyuFullInterfaceEngine()

async def po_feed_simulator():
    """Background data pipeline mapping metrics out to connected sockets."""
    current_price = 1.08437
    while True:
        try:
            await asyncio.sleep(1)
            current_price += np.random.normal(0, 0.00008)
            metrics = interface_engine.compute_all_indicators(current_price)
            
            payload = {
                "asset": interface_engine.active_asset,
                "payout": interface_engine.active_payout,
                "metrics": metrics,
                "market_list": POCKETOPTION_ASSET_MARKET,
                "trades": interface_engine.historical_trades
            }
            
            # Broadcast metrics directly to client session states
            for ws in interface_engine.active_connections:
                try:
                    await ws.send_text(json.dumps(payload))
                except:
                    interface_engine.active_connections.remove(ws)
        except Exception as e:
            await asyncio.sleep(2)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(po_feed_simulator())

@app.websocket("/ws/telemetry")
async def telemetry_socket(websocket: WebSocket):
    await websocket.accept()
    interface_engine.active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "change_asset":
                interface_engine.active_asset = msg.get("asset")
                interface_engine.active_payout = msg.get("payout")
    except:
        interface_engine.active_connections.remove(websocket)

# -------------------------------------------------------------------
# THE FRONT-END USER INTERFACE SPECIFICATIONS (RYU V2 STYLED)
# -------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>RYU V2 AI TRADING ASSISTANT</title>
        <style>
            :root {
                --bg-deep: #050814; --panel-bg: #090e1f; --panel-border: #141b34;
                --text-glow: #00ffcc; --neon-red: #ff2a5f; --neon-blue: #0099ff;
            }
            body {
                background-color: var(--bg-deep); color: #ffffff; font-family: 'Segoe UI', sans-serif;
                margin: 0; padding: 10px; overflow: hidden; height: 100vh; box-sizing: border-box;
            }
            .dashboard-layout {
                display: grid; grid-template-columns: 280px 1fr 320px; gap: 10px; height: 100%;
            }
            .panel {
                background: var(--panel-bg); border: 1px solid var(--panel-border);
                border-radius: 8px; padding: 12px; display: flex; flex-direction: column; overflow: hidden;
            }
            .header-banner {
                display: flex; justify-content: space-between; align-items: center; padding: 5px 10px;
                border-bottom: 2px solid var(--neon-blue); margin-bottom: 8px;
            }
            .header-banner h1 { margin: 0; font-size: 20px; color: #fff; font-style: italic; font-weight: 900; }
            .header-banner h1 span { color: var(--neon-red); }
            
            /* Sidebar Lists */
            .asset-scroll-box { flex: 1; overflow-y: auto; font-size: 12px; }
            .category-title { color: #5a6e9c; font-weight: bold; margin: 10px 0 4px 0; text-transform: uppercase; font-size: 11px; }
            .asset-item {
                display: flex; justify-content: space-between; padding: 6px 8px; margin-bottom: 2px;
                background: #0d142c; border-radius: 4px; cursor: pointer; border: 1px solid transparent;
            }
