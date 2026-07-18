"""Phase 4 — CostModel: fee/spread/slippage on every fill, no bypass path
(spec §6, invariant I2).

There is exactly ONE cost model class. A "frictionless" run is achieved
only by configuring the parameters to zero — never by skipping the code
path. The broker cannot construct a Fill without this model's outputs.

FEES — verified at build time (working rule 6):
    Binance spot, regular/VIP-0 tier: maker 0.100%, taker 0.100% (10 bps).
    Source: https://www.binance.com/en/fee/trading, retrieved 2026-07-08.
    The BNB-payment discount (0.075%) is deliberately NOT assumed.
    We charge TAKER on every fill, including resting limit fills that
    would plausibly be maker — conservative simplification, recorded.

SPREAD — an admitted approximation. Bar data has no order book, so the
    bid/ask spread is modeled as a configured half-spread charged per
    side, referenced to the fill's base price. Default 1 bp.

SLIPPAGE — fixed-bps placeholder, default 1 bp, MEASURED 2026-07-17 from
    6 months of real Binance BTC/USDT aggTrades (see costs below and
    HANDOFF.md 2026-07-17). Was 10 bps (founder guess) before this
    measurement; structured so a size-aware (participation/√-impact)
    model can replace it behind the same interface. R6 discipline still
    applies: the measured value is drift-confounded, not a clean impact
    estimate (see HANDOFF.md), so every result still carries the
    provisional_cost_constants warning, and the Moirai's 2×/5×
    cost-sensitivity test still exists precisely because of this
    uncertainty. Records with trial_index <= 284 used the old 10 bps
    value and are not cost-comparable with later runs.

FUNDING — spot-only Stage 0 (founder decision): raises NotImplementedError.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import pandas as pd

from chronos.hephaestus.types import Order, OrderType, Side, to_decimal

_BPS = Decimal("10000")  # 1 basis point = 1/10000 of price/notional


class CostModel(Protocol):
    """The interface every fill must pass through (invariant I2).

    All returns are ledger-Decimals:
      fee(...)      -> absolute fee on the fill's notional
      slippage(...) -> absolute PRICE adjustment per unit (adverse direction)
      spread(...)   -> absolute half-spread PRICE per unit (adverse direction)
    """

    warnings: tuple[str, ...]

    def fee(self, side: Side, notional: Decimal) -> Decimal: ...
    def slippage(self, order: Order, bar: pd.Series, participation: Decimal) -> Decimal: ...
    def spread(self, bar: pd.Series) -> Decimal: ...


@dataclass(frozen=True)
class CostConfig:
    # Binance spot VIP-0, verified 2026-07-08 (see module docstring).
    taker_fee_bps: Decimal = Decimal("10")  # 0.100%
    maker_fee_bps: Decimal = Decimal("10")  # 0.100% (recorded; taker charged everywhere)
    half_spread_bps: Decimal = Decimal("1")  # modeled spread approximation
    # R6 MEASURED 2026-07-17: BTC/USDT spot, 4,344 hourly bars Jan–Jun
    # 2026, zero liquidity failures at 9k or 90k USDT. Raw distribution is
    # drift-dominated (median 0.00bps, std 1.53bps) — true impact at 9k is
    # below measurement resolution, plausibly ~0.1bps. Default 1bps ≈ 10x
    # margin on plausible impact without manufacturing false negatives.
    # Cross-comparability warning: records trial_index <= 284 used the
    # 10bps provisional value.
    slippage_bps: Decimal = Decimal("1")  # measured (R6); was 10 (provisional)
    # True while the spread/slippage numbers are configured guesses rather
    # than estimates from our own real fills. Stamps a warning on results.
    provisional_constants: bool = True

    def __post_init__(self) -> None:
        for name in ("taker_fee_bps", "maker_fee_bps", "half_spread_bps", "slippage_bps"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")


#: For probe/comparison runs ONLY: the same code path with zero parameters.
ZERO_COSTS = CostConfig(
    taker_fee_bps=Decimal("0"), maker_fee_bps=Decimal("0"),
    half_spread_bps=Decimal("0"), slippage_bps=Decimal("0"),
    provisional_constants=True,  # zeros are still not measured truth
)

PROVISIONAL_WARNING = (
    "provisional_cost_constants: spread/slippage values are configured "
    "guesses, not estimates from real fills (R6). Results require the "
    "Moirai cost-sensitivity test (2x/5x) to pass with margin."
)


class FixedBpsCostModel:
    """Fixed-basis-points costs. Simple, exact, and honest about being
    provisional. The interface is what matters: a size-aware model
    replaces this class without the broker changing a line."""

    def __init__(self, config: CostConfig = CostConfig()):
        self._config = config
        self.warnings: tuple[str, ...] = (
            (PROVISIONAL_WARNING,) if config.provisional_constants else ()
        )

    def fee(self, side: Side, notional: Decimal) -> Decimal:
        """Taker bps on the executed notional — taker charged on ALL fills
        (conservative: maker <= taker on every published tier)."""
        return notional * self._config.taker_fee_bps / _BPS

    def slippage(self, order: Order, bar: pd.Series, participation: Decimal) -> Decimal:
        """Adverse price movement per unit, as bps of the base price.

        `participation` (fill qty / bar volume) is accepted but unused by
        this fixed model — it is the hook the future size-aware model
        needs, kept in the signature so swapping models never touches the
        broker."""
        return self._base_price(order, bar) * self._config.slippage_bps / _BPS

    def spread(self, bar: pd.Series) -> Decimal:
        """Half the modeled bid/ask spread per unit, charged per side,
        referenced to the bar's open (the market-order base price)."""
        return to_decimal(bar["open"]) * self._config.half_spread_bps / _BPS

    def funding(self, position, interval):
        raise NotImplementedError(
            "funding() is perpetuals-only. Stage 0 is spot-only by founder "
            "decision (HANDOFF.md); extending to perps requires extending "
            "HEPHAESTUS_SPEC.md first."
        )

    @staticmethod
    def _base_price(order: Order, bar: pd.Series) -> Decimal:
        if order.type is OrderType.LIMIT and order.limit_price is not None:
            return order.limit_price
        return to_decimal(bar["open"])
