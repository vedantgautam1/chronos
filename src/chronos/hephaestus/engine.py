"""Phase 2 — the event loop (spec §4). The execute function is
module-PRIVATE; run_experiment() (Phase 6) is the only public door.

Per bar t, in strict order:

    1. clock advances to bar t
    2. broker processes orders created at t-1 against bar t  -> Fills
    3. portfolio applies fills (cash, positions, realized PnL)
    4. feed builds the MarketView bounded at t's CLOSE
    5. strategy.on_bar(view, ctx) -> new orders, stamped with bar t
    6. portfolio marks to market at close(t) -> equity[t]
    7. next bar

Timing convention (the most important line in the engine): a signal
computed on the close of bar t executes at the OPEN of bar t+1. Orders
therefore sit in `pending` for exactly one iteration — created in step 5
of bar t, processed in step 2 of bar t+1. There is no path from decision
to same-bar execution. Orders created on the final bar have no t+1: they
EXPIRE and are recorded, never silently dropped.

The engine stamps every order itself: the id (from the deterministic
per-run counter) and created_at (the bar's open_time). A strategy cannot
forge either — whatever it writes in those fields is overwritten.

The broker and portfolio are injected collaborators (real ones arrive in
Phases 3 and 5; tests use minimal scaffolding). Their required shapes are
the BrokerLike / PortfolioLike protocols below.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from typing import Mapping, Protocol

import numpy as np
import pandas as pd

from chronos.oceanus.model import Timeframe
from chronos.hephaestus.types import (
    Fill,
    Order,
    OrderEvent,
    OrderEventKind,
    OrderIdSequence,
)
from chronos.hephaestus.view import Context, Feed, Strategy


@dataclass(frozen=True)
class EngineConfig:
    initial_cash: Decimal = Decimal("10000")  # founder decision: 10,000 USDT
    seed: int = 0
    strategy_params: Mapping = field(default_factory=dict)
    # Same-bar fills are a research-only mode, NOT implemented yet; the
    # field exists so the config hash covers it from day one. Enabling it
    # before the broker phases raises (see _execute).
    unsafe_same_bar_fill: bool = False


class BrokerLike(Protocol):
    """What the engine needs from a broker (real one lands in Phase 3)."""

    def process(
        self, orders: list[Order], bars_at_t: Mapping[str, pd.Series]
    ) -> tuple[list[Fill], list[OrderEvent]]: ...


class PortfolioLike(Protocol):
    """What the engine needs from a portfolio (real one lands in Phase 5)."""

    def apply_fill(self, fill: Fill) -> None: ...
    def mark_to_market(self, closes: Mapping[str, Decimal], at: datetime) -> Decimal: ...
    def snapshot(self) -> Mapping: ...


@dataclass(frozen=True)
class _EngineOutput:
    """What one loop execution produces. run_experiment() (Phase 6) wraps
    this with coordinates/hypothesis/trial into a full BacktestResult."""

    fills: tuple[Fill, ...]
    order_events: tuple[OrderEvent, ...]
    equity_curve: pd.Series  # float64, indexed by bar open_time (UTC)
    bars_processed: int
    warnings: tuple[str, ...]


def _execute(
    bars_by_symbol: Mapping[str, pd.DataFrame],
    timeframe: Timeframe,
    strategy: Strategy,
    broker: BrokerLike,
    portfolio: PortfolioLike,
    config: EngineConfig,
) -> _EngineOutput:
    """The event loop. MODULE-PRIVATE: nothing outside this package may
    call it — every run must enter through run_experiment() (I3)."""
    if config.unsafe_same_bar_fill:
        raise NotImplementedError(
            "unsafe_same_bar_fill is not implemented yet (arrives with the "
            "broker phases); it will never be the default."
        )

    feed = Feed(bars_by_symbol, timeframe)  # validates sorted/unique input

    # Stage 0 simplification (recorded in HANDOFF): all symbols must share
    # the same bar timestamps. True trivially for one symbol; multi-symbol
    # alignment is future work, refused rather than guessed at.
    all_times = [tuple(f["open_time"]) for f in bars_by_symbol.values()]
    if len(set(all_times)) != 1:
        raise ValueError("all symbols must share identical bar timestamps (Stage 0)")
    open_times = list(all_times[0])

    rng = np.random.default_rng(config.seed)  # THE run's only RNG (I5)
    order_ids = OrderIdSequence()

    pending: list[Order] = []  # orders created at t-1, awaiting bar t
    fills: list[Fill] = []
    order_events: list[OrderEvent] = []
    equity_times: list[datetime] = []
    equity_values: list[float] = []

    for i, bar_open in enumerate(open_times):  # step 1: clock -> bar t
        bars_at_t = {sym: frame.iloc[i] for sym, frame in bars_by_symbol.items()}

        # step 2: broker tries the t-1 orders against bar t
        new_fills, new_events = broker.process(pending, bars_at_t)
        pending = []
        fills.extend(new_fills)
        order_events.extend(new_events)

        # step 3: portfolio absorbs the fills
        for fill in new_fills:
            portfolio.apply_fill(fill)

        # step 4: the bounded view — the strategy decides on bar t's CLOSE,
        # so the view is cut at close time (bar t itself is visible; t+1 is not)
        decision_time = bar_open + timeframe.duration
        view = feed.view_at(decision_time)

        # step 5: the strategy speaks; the engine stamps what it says
        ctx = Context(rng=rng, portfolio=portfolio.snapshot(), params=config.strategy_params)
        for order in strategy.on_bar(view, ctx):
            if not isinstance(order, Order):
                raise TypeError(f"strategy returned {type(order).__name__}, expected Order")
            if order.symbol not in bars_by_symbol:
                raise ValueError(f"order for {order.symbol!r}: not in this run's universe")
            # id and created_at are engine-owned: overwrite unconditionally.
            pending.append(replace(order, id=order_ids.next(), created_at=bar_open))

        # step 6: mark to market at close(t)
        closes = {sym: row["close"] for sym, row in bars_at_t.items()}
        equity_times.append(bar_open)
        equity_values.append(float(portfolio.mark_to_market(closes, at=decision_time)))

    # End of data: orders created on the final bar have no t+1. Expire them
    # on the record (never silently dropped).
    last_close = open_times[-1] + timeframe.duration
    for order in pending:
        order_events.append(
            OrderEvent(
                kind=OrderEventKind.EXPIRED,
                order_id=order.id,
                bar_time=last_close,
                reason="created on the final bar; no next bar exists to fill in",
                qty=order.qty,
            )
        )

    equity_curve = pd.Series(
        equity_values, index=pd.DatetimeIndex(equity_times, name="open_time"), name="equity"
    )
    return _EngineOutput(
        fills=tuple(fills),
        order_events=tuple(order_events),
        equity_curve=equity_curve,
        bars_processed=len(open_times),
        warnings=(),
    )
