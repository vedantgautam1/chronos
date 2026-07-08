"""Phase 1 — the Bar schema: the one definition of what a bar is.

A "bar" (or candle) summarizes trading over one time window:
the price it opened at, the highest and lowest prices reached,
the price it closed at, and how much was traded (volume).

Every later phase — ingestion, storage, validation, access — agrees
on this exact shape. If data doesn't fit this model, it's invalid.

Decision (recorded in HANDOFF.md): prices are float64, not Decimal.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class Timeframe(str, Enum):
    """The fixed set of bar sizes Oceanus supports.

    The value (e.g. "1h") is the exchange's own notation, so it can be
    passed straight to ccxt later.
    """

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def duration(self) -> timedelta:
        """How long one bar of this timeframe lasts."""
        return _DURATIONS[self]


_DURATIONS = {
    Timeframe.M1: timedelta(minutes=1),
    Timeframe.M5: timedelta(minutes=5),
    Timeframe.M15: timedelta(minutes=15),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.D1: timedelta(days=1),
}


# Column names for a table (DataFrame) of bars, in canonical order.
# symbol and timeframe are not columns: a table always holds bars for
# exactly one (symbol, timeframe) pair, carried alongside the table.
BAR_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "is_final"]


@dataclass(frozen=True)  # frozen = immutable: a Bar can never be edited after creation
class Bar:
    """One completed or still-forming price bar.

    Raises ValueError at creation time if the data is impossible,
    so an invalid Bar simply cannot exist.
    """

    symbol: str  # canonical form, e.g. "BTC/USDT"
    timeframe: Timeframe
    open_time: datetime  # when the bar's window OPENED; must be timezone-aware UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_final: bool  # False = the bar's window hasn't closed yet (still forming)

    def __post_init__(self) -> None:
        # Timestamps must be timezone-aware UTC. A "naive" timestamp
        # (no timezone attached) is ambiguous and therefore invalid.
        if self.open_time.tzinfo is None:
            raise ValueError(f"open_time is naive (no timezone): {self.open_time}")
        if self.open_time.utcoffset() != timedelta(0):
            raise ValueError(f"open_time is not UTC: {self.open_time}")

        # Prices must be positive, ordered sanely, and volume can't be negative.
        for name in ("open", "high", "low", "close"):
            price = getattr(self, name)
            if not price > 0:
                raise ValueError(f"{name} must be > 0, got {price}")
        if self.low > self.high:
            raise ValueError(f"low ({self.low}) > high ({self.high})")
        if not (self.low <= self.open <= self.high):
            raise ValueError(
                f"open ({self.open}) outside [low, high] = [{self.low}, {self.high}]"
            )
        if not (self.low <= self.close <= self.high):
            raise ValueError(
                f"close ({self.close}) outside [low, high] = [{self.low}, {self.high}]"
            )
        if self.volume < 0:
            raise ValueError(f"volume must be >= 0, got {self.volume}")

    @property
    def close_time(self) -> datetime:
        """When this bar's window ends (open_time + timeframe duration)."""
        return self.open_time + self.timeframe.duration
