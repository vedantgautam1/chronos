"""nulls.py — cadence-matched random null strategies for stage 4.9 (spec §4.9).

The full-engine null benchmark ranks the candidate against `n_nulls` random strategies
that trade at the SAME cadence (same entry count, same holding-duration distribution)
but decide WHEN to trade from nothing but chance. Two pieces live here:

`place_null_entries(n_bars, durations, n_entries, rng)` — the placement function. It
receives ONLY the bar COUNT, the candidate's realized holding durations, and the RNG.
**It cannot see prices — look-ahead is impossible by construction, not by discipline.**
There is no price parameter to pass, so no future (or present) price can influence
which bars are chosen. This is the gate's whole validity; the property test asserts the
signature carries no price data and that identical seeds give identical placements
(I10). Entries are placed uniformly at random without overlap; durations are resampled
with replacement from the candidate's own realized durations.

`NullStrategy` — a strategy that BUYS at its scheduled entry bars and SELLS at its
scheduled exit bars, keyed off an internal bar COUNTER (the bar index), never off
prices. The one price it consults is the CURRENT bar's close, solely to convert cash to
an order quantity (present-price sizing, exactly as the milestone does) — that is not
look-ahead: the entry/exit DECISION is fixed before any price is seen. Long-only (spot),
one position at a time.
"""

from decimal import Decimal

from chronos.hephaestus.types import Order, OrderType, Side, to_decimal

QTY_GRID = Decimal("1E-8")  # satoshi grid, matching the milestone strategy


def _random_composition(total: int, parts: int, rng) -> list[int]:
    """`parts` non-negative integers summing to `total`, drawn from `rng` (sorted
    uniform dividers). Deterministic under a fixed rng — the sole randomness source."""
    if parts <= 1:
        return [max(0, total)]
    if total <= 0:
        return [0] * parts
    dividers = sorted(int(x) for x in rng.integers(0, total + 1, parts - 1))
    out, prev = [], 0
    for d in dividers:
        out.append(d - prev)
        prev = d
    out.append(total - prev)
    return out


def place_null_entries(n_bars: int, durations, n_entries: int, rng) -> list[tuple[int, int]]:
    """`n_entries` non-overlapping (entry_bar, exit_bar) index pairs within [0, n_bars).

    Durations are resampled WITH REPLACEMENT from `durations` (the candidate's realized
    holding lengths, in bars); entries are placed uniformly at random without overlap,
    with at least a one-bar gap after each exit so an exit and the next entry never
    collide. **Receives no price series — zero look-ahead by construction (spec §4.9).**
    If the resampled durations cannot fit in `n_bars`, they are scaled down to fit and
    the caller can see the effect in the returned interval lengths.
    """
    durs = [int(d) for d in durations if int(d) >= 1]
    if n_entries <= 0 or not durs or n_bars <= 0:
        return []
    drawn = [durs[int(i)] for i in rng.integers(0, len(durs), n_entries)]
    # Reserve one bar of gap after each interval so exits never coincide with entries.
    max_total = max(0, n_bars - n_entries)
    total = sum(drawn)
    if total > max_total and total > 0:
        scale = max_total / total
        drawn = [max(1, int(d * scale)) for d in drawn]
        total = sum(drawn)
    slack = max(0, n_bars - total - n_entries)
    gaps = _random_composition(slack, n_entries + 1, rng)

    intervals: list[tuple[int, int]] = []
    cursor = 0
    for i in range(n_entries):
        cursor += gaps[i]
        entry = cursor
        exit_bar = entry + drawn[i]
        if exit_bar >= n_bars:
            break  # ran out of room (only under extreme scaling) — stop cleanly
        intervals.append((entry, exit_bar))
        cursor = exit_bar + 1  # the reserved one-bar gap
    return intervals


class NullStrategy:
    """Trades at the scheduled bars and nowhere else. Decisions are keyed to the bar
    index (an internal counter incremented once per bar), NOT to any price. Long-only,
    one position at a time. The current bar's close is read only to size the order
    (present-price sizing; the decision was fixed before any price was seen)."""

    def __init__(self, symbol: str, intervals, fraction: str = "0.95"):
        self.symbol = symbol
        self.entries = {int(e) for e, _ in intervals}
        self.exits = {int(x) for _, x in intervals}
        self.fraction = to_decimal(fraction)
        self._bar_index = -1

    def on_bar(self, view, ctx):
        self._bar_index += 1
        i = self._bar_index
        held = ctx.portfolio["positions"].get(self.symbol, {}).get("qty", Decimal("0"))
        orders = []
        if i in self.exits and held > 0:
            orders.append(Order(id=0, symbol=self.symbol, side=Side.SELL,
                                type=OrderType.MARKET, qty=held, created_at=view.now))
            held = Decimal("0")
        if i in self.entries and held == 0:
            bars = view.bars(self.symbol, 1)
            if len(bars) > 0:
                last_close = to_decimal(float(bars["close"].iloc[-1]))
                qty = (ctx.portfolio["cash"] * self.fraction / last_close).quantize(QTY_GRID)
                if qty > 0:
                    orders.append(Order(id=0, symbol=self.symbol, side=Side.BUY,
                                        type=OrderType.MARKET, qty=qty, created_at=view.now))
        return orders
