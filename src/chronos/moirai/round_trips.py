"""round_trips.py — reconstruct closed round trips from a run's fills.

Both stage 4.0 (breadth: how many completed round trips) and stage 4.4 (path-risk:
the per-trade return factors) need the same reconstruction, so it lives here once.

The reconstruction is a FIFO match of SELL fills against open BUY lots (Stage 0 is
spot-only, long-only, so a round trip is buy-then-sell). Each closed portion yields
a multiplicative return FACTOR:

    net buy cost per unit  = buy_price  + buy_fee  / buy_qty     (fee adds to cost)
    net sell proceeds/unit = sell_price - sell_fee / sell_qty    (fee cuts proceeds)
    factor                 = net_sell_per_unit / net_buy_per_unit

`Fill.price` is already slippage/spread-adjusted (see hephaestus/types.py), so those
components are NOT re-applied here — only the separate absolute `fee` is. This is a
DIAGNOSTIC reconstruction under proportional sizing, exactly as spec §4.4 states:
it is not accounting-grade (the ledger, in the engine, is). Positions left open at
the end of the run are not completed round trips and are excluded.

Pure: imports only the standard library and the engine's frozen value types.
"""

from collections import deque
from dataclasses import dataclass

from chronos.hephaestus.types import Fill, Side


@dataclass(frozen=True)
class RoundTrip:
    """One closed buy→sell round trip, matched FIFO."""

    qty: float
    factor: float  # multiplicative return: net sell proceeds / net buy cost
    entry_time: object  # bar_time of the buy lot
    exit_time: object  # bar_time of the sell

    @property
    def fractional_return(self) -> float:
        return self.factor - 1.0


def reconstruct_round_trips(trades: tuple[Fill, ...]) -> list[RoundTrip]:
    """FIFO-match fills (in their given time order) into closed round trips.

    A BUY opens (or adds to) inventory; a SELL closes against the oldest open
    lots. Partial fills are handled by matching quantity fractions. Any inventory
    still open at the end is not a completed round trip and is dropped."""
    open_lots: deque[dict] = deque()
    round_trips: list[RoundTrip] = []

    for fill in trades:
        qty = float(fill.qty_filled)
        price = float(fill.price)
        fee_per_unit = float(fill.fee) / qty if qty > 0 else 0.0

        if fill.side is Side.BUY:
            open_lots.append({
                "qty": qty, "price": price, "fee_per_unit": fee_per_unit,
                "time": fill.bar_time,
            })
            continue

        # SELL: consume oldest open lots until this sell's quantity is exhausted.
        remaining = qty
        while remaining > 0 and open_lots:
            lot = open_lots[0]
            matched = min(remaining, lot["qty"])
            net_buy = lot["price"] + lot["fee_per_unit"]
            net_sell = price - fee_per_unit
            factor = net_sell / net_buy if net_buy > 0 else 0.0
            round_trips.append(RoundTrip(
                qty=matched, factor=factor,
                entry_time=lot["time"], exit_time=fill.bar_time,
            ))
            lot["qty"] -= matched
            remaining -= matched
            if lot["qty"] <= 0:
                open_lots.popleft()
        # A sell with no matching inventory (should not happen spot-only) is ignored.

    return round_trips
