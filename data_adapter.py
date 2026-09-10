"""
Market data adapter + connection status for Ryu V2.
Swap MockAdapter for a real feed later (browser intercept or unofficial client).
"""

from __future__ import annotations
import time
import threading
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, List, Optional, Tuple
import random


class ConnectionStatus(Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    DISCONNECTED = "DISCONNECTED"


@dataclass
class Tick:
    timestamp: float          # unix seconds (server or local)
    price: float
    asset: str = "EURUSD_otc"


@dataclass
class Candle:
    open_time: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    is_closed: bool = False


@dataclass
class FeedHealth:
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_tick_age: float = float("inf")
    last_tick_ts: float = 0.0
    ticks_received: int = 0
    latency_ms: float = 0.0
    message: str = "No data yet"


class MarketDataAdapter(ABC):
    """Pluggable interface – implement this for any real source."""

    @abstractmethod
    def start(self) -> None: ...
    @abstractmethod
    def stop(self) -> None: ...
    @abstractmethod
    def get_latest_ticks(self, limit: int = 500) -> List[Tick]: ...
    @abstractmethod
    def get_health(self) -> FeedHealth: ...
    @abstractmethod
    def subscribe(self, asset: str) -> None: ...


class MockAdapter(MarketDataAdapter):
    """
    Realistic synthetic OTC-style tick generator.
    Use this to develop the dashboard and signal logic safely.
    Replace with a real adapter only after you accept the risks.
    """

    def __init__(
        self,
        asset: str = "EURUSD_otc",
        base_price: float = 1.08500,
        tick_interval: float = 0.4,          # ~2.5 ticks/sec
        live_threshold: float = 1.8,         # seconds
        delayed_threshold: float = 5.0,      # seconds
    ):
        self.asset = asset
        self.base_price = base_price
        self.tick_interval = tick_interval
        self.live_threshold = live_threshold
        self.delayed_threshold = delayed_threshold

        self._ticks: Deque[Tick] = deque(maxlen=5000)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_price = base_price
        self._start_time = time.time()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def subscribe(self, asset: str) -> None:
        self.asset = asset

    def get_latest_ticks(self, limit: int = 500) -> List[Tick]:
        with self._lock:
            return list(self._ticks)[-limit:]

    def get_health(self) -> FeedHealth:
        now = time.time()
        with self._lock:
            if not self._ticks:
                return FeedHealth(status=ConnectionStatus.DISCONNECTED, message="No ticks yet")

            last = self._ticks[-1]
            age = now - last.timestamp
            count = len(self._ticks)

        if age <= self.live_threshold:
            status = ConnectionStatus.LIVE
            msg = "Fresh data"
        elif age <= self.delayed_threshold:
            status = ConnectionStatus.DELAYED
            msg = f"Data delayed by {age:.1f}s"
        else:
            status = ConnectionStatus.DISCONNECTED
            msg = f"Stale / disconnected ({age:.1f}s)"

        return FeedHealth(
            status=status,
            last_tick_age=age,
            last_tick_ts=last.timestamp,
            ticks_received=count,
            latency_ms=age * 1000,
            message=msg,
        )

    def _run(self) -> None:
        while self._running:
            # mild random walk + occasional micro-jump (OTC-like behaviour)
            change = random.gauss(0, 0.00008)
            if random.random() < 0.03:
                change += random.choice([-1, 1]) * random.uniform(0.00015, 0.00035)

            self._last_price = max(0.5, self._last_price + change)
            tick = Tick(timestamp=time.time(), price=round(self._last_price, 5), asset=self.asset)

            with self._lock:
                self._ticks.append(tick)

            time.sleep(self.tick_interval + random.uniform(-0.05, 0.08))


def ticks_to_candles(ticks: List[Tick], period_seconds: int = 60) -> List[Candle]:
    """Build OHLCV candles from ticks. Last candle may still be forming."""
    if not ticks:
        return []

    candles: List[Candle] = []
    bucket: dict = {}

    for t in ticks:
        open_time = (int(t.timestamp) // period_seconds) * period_seconds
        if open_time not in bucket:
            bucket[open_time] = {
                "open": t.price,
                "high": t.price,
                "low": t.price,
                "close": t.price,
                "volume": 1.0,
            }
        else:
            b = bucket[open_time]
            b["high"] = max(b["high"], t.price)
            b["low"] = min(b["low"], t.price)
            b["close"] = t.price
            b["volume"] += 1.0

    now = time.time()
    for ot in sorted(bucket.keys()):
        b = bucket[ot]
        is_closed = (ot + period_seconds) <= now
        candles.append(
            Candle(
                open_time=ot,
                open=b["open"],
                high=b["high"],
                low=b["low"],
                close=b["close"],
                volume=b["volume"],
                is_closed=is_closed,
            )
        )
    return candles
