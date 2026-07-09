"""Phase 3 — simulated broker: participation-capped fills, conservative
limit convention, recorded rejections (spec §5).

The broker's one job is HONEST fills. Its biases all point the same,
pessimistic way:

- A fill may consume at most participation_rate × bar volume (default 5%).
  Bigger orders PARTIALLY fill; the remainder is CANCELLED AND RECORDED
  (founder decision — no order state carried between bars).
- A buy limit fills only if the bar trades THROUGH the limit
  (low < limit, strictly). Touching the limit exactly does not fill —
  touch-fills flatter results. The optimistic variant exists behind
  `optimistic_touch_fills=True`, which stamps a warning into the run.
- The broker never fills outside the bar's price range, never fills
  against a zero-volume bar, and never lets spot accounts overspend cash
  or oversell holdings. Those become recorded REJECTED events, not
  exceptions and not silent drops.
- Every fill is priced THROUGH the cost model (invariant I2): base price
  ± (slippage + half-spread), always in the adverse direction, and the
  fee on the executed notional. Phase 3 wires a zero-parameter
  passthrough; Phase 4 makes the numbers real. The call path never
  changes.

Determinism: orders are processed in creation order; affordability is
tracked within the bar (an earlier buy consumes cash an equal later buy
may then lack). No randomness anywhere.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Protocol

import pandas as pd

from chronos.hephaestus.costs import CostModel
from chronos.hephaestus.types import (
    Fill,
    Order,
    OrderEvent,
    OrderEventKind,
    OrderType,
    Side,
    to_decimal,
)


@dataclass(frozen=True)
class BrokerConfig:
    participation_rate: Decimal = Decimal("0.05")  # ≤5% of the bar's volume
    optimistic_touch_fills: bool = False  # research-only; stamps a warning

    def __post_init__(self) -> None:
        if not (0 < self.participation_rate <= 1):
            raise ValueError("participation_rate must be in (0, 1]")


class PortfolioReader(Protocol):
    """The read-only slice of the portfolio the broker needs."""

    @property
    def cash(self) -> Decimal: ...
    def position_qty(self, symbol: str) -> Decimal: ...


class Broker:
    def __init__(self, cost_model: CostModel, portfolio: PortfolioReader,
                 config: BrokerConfig = BrokerConfig()):
        self._costs = cost_model
        self._portfolio = portfolio
        self._config = config
        # Honesty flags: the broker's own, plus whatever the cost model
        # declares (e.g. provisional constants). These reach the result.
        own = (
            ("optimistic_touch_fills enabled: limit orders fill on a touch — "
             "results are flattered and non-promotable",)
            if config.optimistic_touch_fills else ()
        )
        self.warnings: tuple[str, ...] = own + tuple(getattr(cost_model, "warnings", ()))

    def process(
        self, orders: list[Order], bars_at_t: Mapping[str, pd.Series]
    ) -> tuple[list[Fill], list[OrderEvent]]:
        """Attempt the t-1 orders against bar t. Returns (fills, events)."""
        fills: list[Fill] = []
        events: list[OrderEvent] = []
        # Intra-bar running availability: earlier orders consume cash/
        # holdings that later orders in the same bar can no longer use.
        cash_left = self._portfolio.cash
        qty_left: dict[str, Decimal] = {}

        for order in orders:  # creation order — deterministic
            bar = bars_at_t[order.symbol]
            bar_time = bar["open_time"].to_pydatetime()

            def reject(reason: str) -> None:
                events.append(OrderEvent(OrderEventKind.REJECTED, order.id,
                                         bar_time, reason, order.qty))

            volume = to_decimal(bar["volume"])
            if volume <= 0:
                reject("zero-volume bar: no liquidity to fill against")
                continue

            # Spot-only: an intent to sell more than held is rejected whole.
            if order.side is Side.SELL:
                held = qty_left.setdefault(
                    order.symbol, self._portfolio.position_qty(order.symbol))
                if order.qty > held:
                    reject(f"insufficient position: order qty {order.qty}, held {held} (no shorting)")
                    continue

            # Participation cap -> possibly partial fill.
            cap = volume * self._config.participation_rate
            fillable = min(order.qty, cap)

            # Base price by order type.
            if order.type is OrderType.MARKET:
                base_price = to_decimal(bar["open"])
            else:
                base_price = self._limit_base_price(order, bar)
                if base_price is None:
                    # Not traded through: dies at end of bar per the
                    # cancel-and-record (no carry) policy.
                    events.append(OrderEvent(
                        OrderEventKind.REMAINDER_CANCELLED, order.id, bar_time,
                        "limit not traded through this bar; cancelled per no-carry policy",
                        order.qty))
                    continue

            # THE cost path (I2): every fill goes through all three calls.
            participation = fillable / volume
            slip = self._costs.slippage(order, bar, participation)
            half_spread = self._costs.spread(bar)
            adverse = slip + half_spread  # price moves against you, always
            exec_price = base_price + adverse if order.side is Side.BUY else base_price - adverse
            notional = fillable * exec_price
            fee = self._costs.fee(order.side, notional)

            # Affordability (buys): notional + fee within remaining cash.
            if order.side is Side.BUY and notional + fee > cash_left:
                reject(f"insufficient cash: need {notional + fee}, have {cash_left}")
                continue

            fills.append(Fill(
                order_id=order.id, symbol=order.symbol, side=order.side,
                qty_filled=fillable, price=exec_price, fee=fee,
                slippage_cost=slip * fillable, spread_cost=half_spread * fillable,
                bar_time=bar_time,
            ))
            if order.side is Side.BUY:
                cash_left -= notional + fee
            else:
                qty_left[order.symbol] -= fillable

            # Cancel-and-record the capped remainder (founder decision).
            remainder = order.qty - fillable
            if remainder > 0:
                events.append(OrderEvent(
                    OrderEventKind.REMAINDER_CANCELLED, order.id, bar_time,
                    f"participation cap ({self._config.participation_rate:%} of "
                    f"volume {volume}) allowed {fillable}; remainder cancelled, not carried",
                    remainder))

        return fills, events

    def _limit_base_price(self, order: Order, bar: pd.Series) -> Decimal | None:
        """Conservative trade-through convention. None = did not fill.

        BUY  fills iff low(t)  < limit (strictly) — the market traded
             through the price; a bare touch is not evidence you'd have
             been filled. Fill AT the limit price.
        SELL fills iff high(t) > limit (strictly), symmetric.
        The optimistic (touch = fill) variant is flagged and warned.
        """
        limit = order.limit_price
        low, high = to_decimal(bar["low"]), to_decimal(bar["high"])
        if order.side is Side.BUY:
            traded_through = low < limit or (self._config.optimistic_touch_fills and low <= limit)
        else:
            traded_through = high > limit or (self._config.optimistic_touch_fills and high >= limit)
        return limit if traded_through else None
