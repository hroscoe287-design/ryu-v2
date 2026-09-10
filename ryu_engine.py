"""
Ryu V2 signal engine with hard stale-data gate.
Keep your own logic – this shows the required pattern.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from data_adapter import (
    MarketDataAdapter,
    ConnectionStatus,
    ticks_to_candles,
    Candle,
    FeedHealth,
)
from indicators import rsi, stochastic, bollinger, dual_ema, macd


@dataclass
class Signal:
    direction: str          # "CALL" | "PUT" | "NONE"
    confidence: float       # 0–1
    reason: str
    timestamp: float
    status: ConnectionStatus


class RyuEngine:
    def __init__(
        self,
        adapter: MarketDataAdapter,
        candle_period: int = 60,
        min_candles: int = 30,
    ):
        self.adapter = adapter
        self.candle_period = candle_period
        self.min_candles = min_candles

    def get_health(self) -> FeedHealth:
        return self.adapter.get_health()

    def get_candles(self) -> List[Candle]:
        ticks = self.adapter.get_latest_ticks(limit=2000)
        return ticks_to_candles(ticks, self.candle_period)

    def generate_signal(self) -> Signal:
        health = self.get_health()
        now = health.last_tick_ts or 0.0

        # === HARD GATE – never signal on non-LIVE data ===
        if health.status != ConnectionStatus.LIVE:
            return Signal(
                direction="NONE",
                confidence=0.0,
                reason=f"Data not LIVE ({health.status.value}: {health.message})",
                timestamp=now,
                status=health.status,
            )

        candles = self.get_candles()
        if len(candles) < self.min_candles:
            return Signal(
                direction="NONE",
                confidence=0.0,
                reason=f"Not enough candles ({len(candles)})",
                timestamp=now,
                status=health.status,
            )

        # --- indicators ---
        r = rsi(candles, 14)
        k, d = stochastic(candles, 14, 3)
        upper, mid, lower = bollinger(candles, 20, 2.0)
        ema_fast, ema_slow = dual_ema(candles, 9, 21)
        macd_line, signal_line, hist = macd(candles)

        # latest values (skip NaNs)
        def last_valid(arr):
            for v in reversed(arr):
                if v == v:  # not NaN
                    return float(v)
            return None

        rsi_v = last_valid(r)
        k_v = last_valid(k)
        d_v = last_valid(d)
        ema_f = last_valid(ema_fast)
        ema_s = last_valid(ema_slow)
        hist_v = last_valid(hist)
        close = candles[-1].close
        mid_v = last_valid(mid)

        if None in (rsi_v, k_v, d_v, ema_f, ema_s, hist_v, mid_v):
            return Signal("NONE", 0.0, "Indicators not ready", now, health.status)

        # Simple confluence (tune to your style)
        bullish_votes = 0
        bearish_votes = 0
        reasons = []

        # RSI
        if rsi_v < 30:
            bullish_votes += 1
            reasons.append("RSI oversold")
        elif rsi_v > 70:
            bearish_votes += 1
            reasons.append("RSI overbought")

        # Stochastic
        if k_v < 20 and d_v < 20:
            bullish_votes += 1
            reasons.append("Stoch oversold")
        elif k_v > 80 and d_v > 80:
            bearish_votes += 1
            reasons.append("Stoch overbought")

        # EMA trend
        if ema_f > ema_s and close > ema_f:
            bullish_votes += 1
            reasons.append("EMA bullish")
        elif ema_f < ema_s and close < ema_f:
            bearish_votes += 1
            reasons.append("EMA bearish")

        # MACD histogram
        if hist_v > 0:
            bullish_votes += 1
            reasons.append("MACD hist +")
        else:
            bearish_votes += 1
            reasons.append("MACD hist -")

        # Bollinger position
        if close < lower[-1] if lower[-1] == lower[-1] else False:
            bullish_votes += 1
            reasons.append("Below lower BB")
        elif close > upper[-1] if upper[-1] == upper[-1] else False:
            bearish_votes += 1
            reasons.append("Above upper BB")

        total = bullish_votes + bearish_votes
        if total == 0:
            return Signal("NONE", 0.0, "No clear confluence", now, health.status)

        if bullish_votes >= 3 and bullish_votes > bearish_votes:
            conf = bullish_votes / 5.0
            return Signal("CALL", min(conf, 1.0), " | ".join(reasons), now, health.status)
        if bearish_votes >= 3 and bearish_votes > bullish_votes:
            conf = bearish_votes / 5.0
            return Signal("PUT", min(conf, 1.0), " | ".join(reasons), now, health.status)

        return Signal("NONE", 0.0, "Mixed signals", now, health.status)
