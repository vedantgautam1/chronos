"""Phase 4 — CostModel: fee/spread/slippage on every fill, no bypass path
(spec §6, invariant I2).

Phase 3 status: only the PROTOCOL and a temporary passthrough live here,
so the broker's call path through the cost model exists from the very
first fill. Phase 4 replaces the passthrough with the real model (fees
verified against Binance's published schedule, configurable spread and
provisional slippage). The passthrough is not a bypass — it IS the cost
path, with all parameters at zero. There is no code path around it.
"""

from decimal import Decimal
from typing import Protocol

import pandas as pd

from chronos.hephaestus.types import Order, Side


class CostModel(Protocol):
    """The interface every fill must pass through (invariant I2).

    All return values are ledger-Decimals:
      fee(...)      -> absolute fee charged on the fill's notional
      slippage(...) -> absolute PRICE adjustment per unit (adverse direction)
      spread(...)   -> absolute half-spread PRICE per unit (adverse direction)
    """

    def fee(self, side: Side, notional: Decimal) -> Decimal: ...
    def slippage(self, order: Order, bar: pd.Series, participation: Decimal) -> Decimal: ...
    def spread(self, bar: pd.Series) -> Decimal: ...


class PassthroughCostModel:
    """TEMPORARY (Phase 3 scaffolding, replaced in Phase 4).

    Zero fee, zero slippage, zero spread — but the broker still routes
    every fill through these calls, so the I2 path is real from day one.
    """

    def fee(self, side: Side, notional: Decimal) -> Decimal:
        return Decimal("0")

    def slippage(self, order: Order, bar: pd.Series, participation: Decimal) -> Decimal:
        return Decimal("0")

    def spread(self, bar: pd.Series) -> Decimal:
        return Decimal("0")
