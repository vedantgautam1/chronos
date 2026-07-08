"""Phase 1 — MarketView + Feed: the time-bounded view that makes
look-ahead impossible (spec §3, invariant I1).

HOW THE BOUND WORKS (the quant should audit this first):

1. The Feed holds the full bar series (from Oceanus get_bars()).
2. At each decision time t, the Feed constructs a MarketView containing
   ONLY the rows whose bar has fully CLOSED by t — i.e. rows where
   open_time + timeframe <= t. The cut is made by position (searchsorted
   on the precomputed close-time column), before the view ever exists.
3. The MarketView therefore never *contains* future data. This is the
   structural guarantee: even a strategy that reaches into the view's
   private attributes finds nothing beyond t, because nothing beyond t
   was ever put in. Look-ahead isn't forbidden — it's impossible.
4. bars() hands out a deep COPY of the requested slice, so a strategy
   that mutates what it received cannot corrupt the engine's data or
   leak state into later bars (or other strategies).

The strategy contract (Strategy protocol) and Context live here too:
a strategy is a pure function  on_bar(view, ctx) -> [orders]  and the
Context carries exactly three things — the seeded RNG (invariant I5),
a read-only portfolio snapshot, and the strategy's own parameters.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from chronos.oceanus.model import Timeframe
from chronos.hephaestus.types import Order, _require_utc


class MarketView:
    """Read-only market data bounded at decision time `now`.

    Constructed only by the Feed. Contains no bar that closes after `now`.
    """

    __slots__ = ("_now", "_frames")

    def __init__(self, now: datetime, frames: dict[str, pd.DataFrame]):
        self._now = now
        self._frames = frames  # already bounded by the Feed — see module docstring

    @property
    def now(self) -> datetime:
        """The decision time t. Everything visible has closed by this moment."""
        return self._now

    def bars(self, symbol: str, lookback: int) -> pd.DataFrame:
        """The last `lookback` bars of `symbol` that have closed by `now`.

        Returns a copy: mutate it freely, the engine's data is untouched.
        Returns fewer rows (possibly zero) if history is shorter than asked.
        """
        if lookback <= 0:
            raise ValueError(f"lookback must be > 0, got {lookback}")
        if symbol not in self._frames:
            raise KeyError(f"symbol {symbol!r} is not in this run's universe")
        return self._frames[symbol].tail(lookback).copy(deep=True).reset_index(drop=True)


class Feed:
    """Owns the full series; manufactures time-bounded MarketViews."""

    def __init__(self, bars_by_symbol: Mapping[str, pd.DataFrame], timeframe: Timeframe):
        self._timeframe = timeframe
        self._frames: dict[str, pd.DataFrame] = {}
        self._close_times: dict[str, pd.Series] = {}
        for symbol, frame in bars_by_symbol.items():
            if frame.empty:
                raise ValueError(f"empty bar series for {symbol!r}")
            opens = frame["open_time"]
            if not opens.is_monotonic_increasing or opens.duplicated().any():
                # get_bars() guarantees this; a violation here means someone
                # fed the engine data around the one door. Refuse.
                raise ValueError(f"bars for {symbol!r} are not sorted/unique — engine input must come from get_bars()")
            self._frames[symbol] = frame.copy(deep=True).reset_index(drop=True)
            # Precomputed close time of each bar: open_time + duration.
            self._close_times[symbol] = self._frames[symbol]["open_time"] + timeframe.duration

    def view_at(self, now: datetime) -> MarketView:
        """A MarketView containing exactly the bars closed by `now`."""
        _require_utc(now, "now")
        bounded: dict[str, pd.DataFrame] = {}
        for symbol, frame in self._frames.items():
            # Number of bars with close_time <= now, found by binary search.
            n_closed = int(self._close_times[symbol].searchsorted(now, side="right"))
            bounded[symbol] = frame.iloc[:n_closed]
        return MarketView(now, bounded)


@dataclass(frozen=True)
class Context:
    """What a strategy gets besides market data — and ALL it gets (spec §3).

    rng:       the run's single seeded random generator (invariant I5).
    portfolio: read-only snapshot of current holdings/cash.
    params:    the strategy's own configuration.
    """

    rng: np.random.Generator
    portfolio: Mapping[str, Any]
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        # Wrap in read-only proxies so a strategy cannot mutate shared state.
        object.__setattr__(self, "portfolio", MappingProxyType(dict(self.portfolio)))
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))


@runtime_checkable
class Strategy(Protocol):
    """A strategy is a pure decision function over a bounded view."""

    def on_bar(self, view: MarketView, ctx: Context) -> list[Order]: ...
