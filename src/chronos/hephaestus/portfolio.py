"""Phase 5 — accounting: Decimal ledger, equity marks, reconciliation
identity (spec §7).

THE LEDGER (all Decimal, all exact):
  cash, per-symbol holdings (quantity + COST BASIS), realized PnL,
  and itemized cumulative costs (fees / slippage / spread).

Why cost basis instead of average entry price: the reconciliation
identity below holds EXACTLY under basis tracking, regardless of how a
partial sale's basis is apportioned — the apportionment cancels between
realized and unrealized. Average entry price is derived from basis only
for display. (The quant should verify this cancellation; it is the
load-bearing trick of the whole ledger.)

THE RECONCILIATION IDENTITY (checked at every single mark):

    equity[t] == initial_cash + realized_pnl + unrealized_pnl − fees_paid

where equity = cash + Σ qty×close and unrealized = Σ (qty×close − basis).
Note the cost term is FEES ONLY: slippage and spread are embedded in the
execution price (buys enter at a worse price, sells exit at a worse
price), so they already live inside realized/unrealized PnL — counting
them again would double-charge. They are still tracked and itemized for
the cost summary; they are attribution, not separate cash flows. This is
a deliberate accounting convention, recorded in HANDOFF.md.

A violation raises AccountingDriftError immediately — a drift here is a
build-breaking bug, never something to log and continue past.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Mapping

import pandas as pd

from chronos.hephaestus.types import Fill, Side, to_decimal


class AccountingError(Exception):
    """An operation the ledger must never perform (e.g. overselling)."""


class AccountingDriftError(Exception):
    """The reconciliation identity failed. Build-breaking; never ignore."""


@dataclass
class _Holding:
    qty: Decimal = Decimal("0")
    basis: Decimal = Decimal("0")  # total cost (at execution prices) of current qty
    realized_pnl: Decimal = Decimal("0")

    @property
    def avg_entry_price(self) -> Decimal:
        """Display-only derivation; the ledger never computes from this."""
        return self.basis / self.qty if self.qty else Decimal("0")


class Portfolio:
    """The engine's books. Implements both PortfolioLike (engine) and
    PortfolioReader (broker)."""

    def __init__(self, initial_cash: Decimal, check_identity: bool = True):
        if initial_cash <= 0:
            raise ValueError("initial_cash must be > 0")
        self.initial_cash = initial_cash
        self._cash = initial_cash
        self._holdings: dict[str, _Holding] = {}
        self.fees_paid = Decimal("0")
        self.slippage_paid = Decimal("0")
        self.spread_paid = Decimal("0")
        self._check_identity = check_identity

    # ---- read interface (PortfolioReader, used by the broker) ----

    @property
    def cash(self) -> Decimal:
        return self._cash

    def position_qty(self, symbol: str) -> Decimal:
        holding = self._holdings.get(symbol)
        return holding.qty if holding else Decimal("0")

    @property
    def realized_pnl(self) -> Decimal:
        return sum((h.realized_pnl for h in self._holdings.values()), Decimal("0"))

    # ---- write interface (PortfolioLike, used by the engine) ----

    def apply_fill(self, fill: Fill) -> None:
        self.fees_paid += fill.fee
        self.slippage_paid += fill.slippage_cost
        self.spread_paid += fill.spread_cost

        holding = self._holdings.setdefault(fill.symbol, _Holding())
        notional = fill.qty_filled * fill.price

        if fill.side is Side.BUY:
            self._cash -= notional + fill.fee
            holding.qty += fill.qty_filled
            holding.basis += notional
        else:
            if fill.qty_filled > holding.qty:
                raise AccountingError(
                    f"oversell reached the ledger: selling {fill.qty_filled} "
                    f"of {holding.qty} held {fill.symbol} — the broker must prevent this"
                )
            # Apportion basis to the sold quantity. Selling everything takes
            # the whole basis exactly (no division residue); a partial sale
            # takes the pro-rata share. ANY rounding in this apportionment
            # cancels in the reconciliation identity (see module docstring).
            if fill.qty_filled == holding.qty:
                sold_basis = holding.basis
            else:
                sold_basis = holding.basis * fill.qty_filled / holding.qty
            self._cash += notional - fill.fee
            holding.realized_pnl += notional - sold_basis
            holding.qty -= fill.qty_filled
            holding.basis -= sold_basis

    def unrealized_pnl(self, closes: Mapping[str, object]) -> Decimal:
        total = Decimal("0")
        for symbol, holding in self._holdings.items():
            if holding.qty:
                total += holding.qty * to_decimal(closes[symbol]) - holding.basis
        return total

    def mark_to_market(self, closes: Mapping[str, object], at: datetime) -> Decimal:
        """Equity at this bar's close — and the identity check, every time."""
        equity = self._cash
        for symbol, holding in self._holdings.items():
            if holding.qty:
                equity += holding.qty * to_decimal(closes[symbol])

        if self._check_identity:
            expected = (self.initial_cash + self.realized_pnl
                        + self.unrealized_pnl(closes) - self.fees_paid)
            if equity != expected:
                raise AccountingDriftError(
                    f"reconciliation failed at {at}: equity={equity} but "
                    f"initial+realized+unrealized-fees={expected} "
                    f"(drift={equity - expected}). This is a bug in the ledger."
                )
        return equity

    def snapshot(self) -> Mapping:
        """Read-only view for the strategy's Context."""
        return {
            "cash": self._cash,
            "positions": {
                s: {"qty": h.qty, "avg_entry_price": h.avg_entry_price,
                    "realized_pnl": h.realized_pnl}
                for s, h in self._holdings.items() if h.qty
            },
            "fees_paid": self.fees_paid,
        }


def returns_from_equity(equity: pd.Series) -> pd.Series:
    """Per-bar simple returns, derived ONCE here (spec §7) — the Moirai
    consume these; nothing downstream recomputes them differently.

    Convention: returns[t] = equity[t]/equity[t-1] − 1; the first bar's
    return is 0.0 (no prior bar), keeping the series aligned with equity.
    """
    returns = equity.pct_change()
    if len(returns):
        returns.iloc[0] = 0.0
    return returns.rename("returns")
