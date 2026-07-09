"""The Phase 9 milestone strategy: a moving-average crossover.

Chosen because it is the "hello world" of systematic trading — simple,
well-understood, and almost certainly NOT profitable after honest costs
on hourly BTC. That is the point: the milestone proves the *instrument*
(data → engine → costs → record) end to end. An unremarkable or losing
result is success.

Logic (state-based, long-only, spot):
  - fast MA above slow MA and we hold nothing  -> buy with `fraction`
    of available cash (default 95%, leaving room for fees)
  - fast MA below slow MA and we hold a position -> sell all of it
  - anything else -> do nothing

All indicator math uses ONLY the bounded MarketView — the last
`slow` closed bars — exactly as every future strategy must.
Parameters come from ctx.params: fast (default 20), slow (50),
fraction (0.95).
"""

from decimal import Decimal

from chronos.hephaestus.types import Order, OrderType, Side, to_decimal
from chronos.hephaestus.view import Context, MarketView

QTY_GRID = Decimal("1E-8")  # order sizes on the exchange's satoshi grid


class MACrossover:
    def __init__(self, symbol: str = "BTC/USDT"):
        self.symbol = symbol

    def on_bar(self, view: MarketView, ctx: Context) -> list[Order]:
        fast = int(ctx.params.get("fast", 20))
        slow = int(ctx.params.get("slow", 50))
        fraction = to_decimal(ctx.params.get("fraction", "0.95"))
        if not (0 < fast < slow):
            raise ValueError(f"need 0 < fast < slow, got fast={fast} slow={slow}")

        bars = view.bars(self.symbol, lookback=slow)
        if len(bars) < slow:
            return []  # not enough closed history yet; wait

        closes = bars["close"].astype(float)
        fast_ma = closes.tail(fast).mean()
        slow_ma = closes.mean()

        held = ctx.portfolio["positions"].get(self.symbol, {}).get("qty", Decimal("0"))

        if fast_ma > slow_ma and held == 0:
            last_close = to_decimal(float(closes.iloc[-1]))
            qty = (ctx.portfolio["cash"] * fraction / last_close).quantize(QTY_GRID)
            if qty > 0:
                return [Order(id=0, symbol=self.symbol, side=Side.BUY,
                              type=OrderType.MARKET, qty=qty, created_at=view.now)]
        elif fast_ma < slow_ma and held > 0:
            return [Order(id=0, symbol=self.symbol, side=Side.SELL,
                          type=OrderType.MARKET, qty=held, created_at=view.now)]
        return []
