"""Common short-term binary / OTC indicators."""

from __future__ import annotations
from typing import List, Optional, Tuple
import numpy as np
from data_adapter import Candle


def _closes(candles: List[Candle]) -> np.ndarray:
    return np.array([c.close for c in candles], dtype=float)


def ema(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) < period:
        return np.full_like(values, np.nan)
    alpha = 2 / (period + 1)
    out = np.empty_like(values)
    out[:] = np.nan
    out[period - 1] = np.mean(values[:period])
    for i in range(period, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def rsi(candles: List[Candle], period: int = 14) -> np.ndarray:
    closes = _closes(candles)
    if len(closes) < period + 1:
        return np.full(len(closes), np.nan)
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.empty(len(deltas))
    avg_loss = np.empty(len(deltas))
    avg_gain[:period] = np.nan
    avg_loss[:period] = np.nan
    avg_gain[period - 1] = np.mean(gains[:period])
    avg_loss[period - 1] = np.mean(losses[:period])
    for i in range(period, len(deltas)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period
    rs = avg_gain / (avg_loss + 1e-10)
    rsi_vals = 100 - (100 / (1 + rs))
    out = np.full(len(closes), np.nan)
    out[1:] = rsi_vals
    return out


def stochastic(candles: List[Candle], k_period: int = 14, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    if len(candles) < k_period:
        n = len(candles)
        return np.full(n, np.nan), np.full(n, np.nan)
    highs = np.array([c.high for c in candles])
    lows = np.array([c.low for c in candles])
    closes = _closes(candles)
    k = np.full(len(candles), np.nan)
    for i in range(k_period - 1, len(candles)):
        highest = np.max(highs[i - k_period + 1 : i + 1])
        lowest = np.min(lows[i - k_period + 1 : i + 1])
        k[i] = 100 * (closes[i] - lowest) / (highest - lowest + 1e-10)
    d = ema(k, d_period)  # simple smoothing
    return k, d


def bollinger(candles: List[Candle], period: int = 20, std_mult: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    closes = _closes(candles)
    mid = ema(closes, period)  # or SMA – EMA reacts a bit faster
    if len(closes) < period:
        n = len(closes)
        return np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    std = np.full(len(closes), np.nan)
    for i in range(period - 1, len(closes)):
        std[i] = np.std(closes[i - period + 1 : i + 1])
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


def macd(candles: List[Candle], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    closes = _closes(candles)
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def dual_ema(candles: List[Candle], fast: int = 9, slow: int = 21) -> Tuple[np.ndarray, np.ndarray]:
    closes = _closes(candles)
    return ema(closes, fast), ema(closes, slow)
