"""Phase 1 — Order, Fill, Position, BacktestResult (spec §2).

The engine's vocabulary. Two conventions run through everything here:

Numeric policy (founder decision, HANDOFF.md): money and quantities are
Decimal — the ledger reconciles to the cent, exactly. Price *series* and
returns stay float64 (they come from Oceanus and feed the Moirai's math).
`to_decimal()` is the one blessed crossing point between the two worlds.

Determinism (invariant I5): order ids come from a per-run counter
(`OrderIdSequence`) — never uuid4, never wall-clock. Same run, same ids.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

import pandas as pd


def to_decimal(value) -> Decimal:
    """The one boundary crossing from float-world to ledger-world.

    Decimal(str(x)) uses the float's shortest exact representation, so
    64123.45 becomes Decimal('64123.45'), not Decimal('64123.4499999...').
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderIdSequence:
    """Deterministic per-run order ids: 1, 2, 3, ... (invariant I5)."""

    def __init__(self) -> None:
        self._next = 1

    def next(self) -> int:
        issued = self._next
        self._next += 1
        return issued


def _require_utc(moment: datetime, name: str) -> None:
    if moment.tzinfo is None:
        raise ValueError(f"{name} is naive (no timezone): {moment}")
    if moment.utcoffset() != timedelta(0):
        raise ValueError(f"{name} is not UTC: {moment}")


@dataclass(frozen=True)
class Order:
    """A strategy's intention, stamped with the bar-time it was decided at."""

    id: int
    symbol: str
    side: Side
    type: OrderType
    qty: Decimal
    created_at: datetime  # bar time t at which the strategy emitted it
    limit_price: Decimal | None = None  # required iff type == LIMIT

    def __post_init__(self) -> None:
        _require_utc(self.created_at, "created_at")
        if self.qty <= 0:
            raise ValueError(f"order qty must be > 0, got {self.qty}")
        if self.type is OrderType.LIMIT:
            if self.limit_price is None or self.limit_price <= 0:
                raise ValueError("LIMIT order requires a positive limit_price")
        elif self.limit_price is not None:
            raise ValueError("MARKET order must not carry a limit_price")


@dataclass(frozen=True)
class Fill:
    """An execution. `price` already includes slippage/spread adjustment;
    the cost components are itemized so nothing hides inside the price."""

    order_id: int
    symbol: str
    side: Side
    qty_filled: Decimal  # may be < the order's qty (partial fills are normal)
    price: Decimal  # modeled execution price, cost-adjusted
    fee: Decimal  # absolute fee charged
    slippage_cost: Decimal  # absolute cost attributed to slippage
    spread_cost: Decimal  # absolute cost attributed to the modeled spread
    bar_time: datetime  # the bar in which the fill occurred (t+1 by default)

    def __post_init__(self) -> None:
        _require_utc(self.bar_time, "bar_time")
        if self.qty_filled <= 0:
            raise ValueError(f"qty_filled must be > 0, got {self.qty_filled}")
        if self.price <= 0:
            raise ValueError(f"fill price must be > 0, got {self.price}")
        for name in ("fee", "slippage_cost", "spread_cost"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")


class OrderEventKind(str, Enum):
    """Things that happen to orders besides filling — all recorded, never silent."""

    REJECTED = "REJECTED"  # insufficient cash / selling more than held / zero-volume bar
    EXPIRED = "EXPIRED"  # created on the final bar; there is no t+1 to fill in
    REMAINDER_CANCELLED = "REMAINDER_CANCELLED"  # unfilled part beyond the participation cap


@dataclass(frozen=True)
class OrderEvent:
    kind: OrderEventKind
    order_id: int
    bar_time: datetime
    reason: str  # plain English, e.g. "insufficient cash: need 500.00, have 120.00"
    qty: Decimal  # the quantity affected (rejected qty / expired qty / cancelled remainder)


@dataclass
class Position:
    """Holdings in one symbol. Spot-only: the engine never lets qty go negative."""

    symbol: str
    qty: Decimal = Decimal("0")
    avg_entry_price: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class CostSummary:
    """Itemized total costs for a whole run (spec §2 cost_summary)."""

    fees: Decimal
    slippage: Decimal
    spread: Decimal

    @property
    def total(self) -> Decimal:
        return self.fees + self.slippage + self.spread


@dataclass(frozen=True)
class BacktestResult:
    """What the engine hands the Moirai (spec §2, §10). Truthful and complete;
    it computes NO statistics — judging is the Moirai's job."""

    # Reproducibility coordinates (invariant I5): these four plus the code
    # fully determine every byte below.
    run_id: str
    core_version: str  # git SHA of the engine code
    config_hash: str
    data_snapshot_hash: str  # Oceanus snapshot hash
    seed: int

    # What was run
    bars_processed: int
    date_range: tuple[datetime, datetime]
    symbols: tuple[str, ...]
    timeframe: str

    # What happened
    trades: tuple[Fill, ...]  # every fill, itemized costs included
    order_events: tuple[OrderEvent, ...]  # rejections/expiries/cancellations
    equity_curve: pd.Series  # per-bar equity, float64, UTC datetime index
    returns: pd.Series  # per-bar simple returns, derived once (Phase 5)
    cost_summary: CostSummary

    # Honesty and bookkeeping (invariants I6, I8)
    warnings: tuple[str, ...]  # e.g. unsafe flags, provisional cost constants
    hypothesis_id: str
    trial_index: int
