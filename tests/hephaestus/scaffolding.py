"""TEST SCAFFOLDING — minimal stand-ins for the engine's collaborators.

These exist only so Phase 2's loop can be exercised before the real
broker (Phase 3) and portfolio (Phase 5) are built. They are deliberately
naive: full fills at the bar's open, zero costs, cash-and-qty bookkeeping
only. Nothing here is engine code and nothing here survives into results
the Moirai will ever see.
"""

from datetime import datetime
from decimal import Decimal
from typing import Mapping

import pandas as pd

from chronos.hephaestus.types import Fill, Order, OrderEvent, Side, to_decimal
from chronos.hephaestus.view import Context, MarketView


class StubBroker:
    """Fills every market order fully at the processing bar's open. No
    costs, no caps, no limits — Phase 3 replaces this with honesty."""

    warnings: tuple[str, ...] = ()

    def process(
        self, orders: list[Order], bars_at_t: Mapping[str, pd.Series]
    ) -> tuple[list[Fill], list[OrderEvent]]:
        fills = []
        for order in orders:
            bar = bars_at_t[order.symbol]
            fills.append(
                Fill(
                    order_id=order.id,
                    symbol=order.symbol,
                    side=order.side,
                    qty_filled=order.qty,
                    price=to_decimal(bar["open"]),
                    fee=Decimal("0"),
                    slippage_cost=Decimal("0"),
                    spread_cost=Decimal("0"),
                    bar_time=bar["open_time"].to_pydatetime(),
                )
            )
        return fills, []


class StubPortfolio:
    """Cash + quantities, no cost tracking. Phase 5 replaces this with
    the real Decimal ledger and the reconciliation identity."""

    def __init__(self, initial_cash: Decimal):
        self.cash = initial_cash
        self.qty: dict[str, Decimal] = {}

    def apply_fill(self, fill: Fill) -> None:
        notional = fill.qty_filled * fill.price
        if fill.side is Side.BUY:
            self.cash -= notional
            self.qty[fill.symbol] = self.qty.get(fill.symbol, Decimal("0")) + fill.qty_filled
        else:
            self.cash += notional
            self.qty[fill.symbol] = self.qty.get(fill.symbol, Decimal("0")) - fill.qty_filled

    def mark_to_market(self, closes: Mapping[str, float], at: datetime) -> Decimal:
        holdings = sum(
            (qty * to_decimal(closes[sym]) for sym, qty in self.qty.items()),
            Decimal("0"),
        )
        return self.cash + holdings

    def position_qty(self, symbol: str) -> Decimal:
        return self.qty.get(symbol, Decimal("0"))

    def snapshot(self) -> Mapping:
        return {"cash": self.cash, "positions": dict(self.qty)}


class DoNothingStrategy:
    """Emits no orders, ever. The flat-equity baseline."""

    def on_bar(self, view: MarketView, ctx: Context) -> list[Order]:
        return []


class BuyOnceStrategy:
    """Buys a fixed qty the first time it sees `trigger_bars` bars of
    history, then goes quiet. Loop-exercising fixture, not a strategy."""

    def __init__(self, qty: Decimal = Decimal("0.1"), trigger_bars: int = 3):
        self.qty = qty
        self.trigger_bars = trigger_bars
        self._done = False

    def on_bar(self, view: MarketView, ctx: Context) -> list[Order]:
        from chronos.hephaestus.types import OrderType

        if self._done or len(view.bars("BTC/USDT", self.trigger_bars)) < self.trigger_bars:
            return []
        self._done = True
        return [
            Order(id=0, symbol="BTC/USDT", side=Side.BUY, type=OrderType.MARKET,
                  qty=self.qty, created_at=view.now)  # id/created_at get re-stamped
        ]
