```yaml
id: B14
title: Slippage and spread measurement method
size: S
model: opus
who: loop
needs: [B13]
ticks: 2
touches:
  - v2/src/chronos2/costs/**
  - v2/tests/costs/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B14 — Slippage and spread measurement method

## Why
B13 takes spread and slippage as inputs. Something has to produce them from real trading records, with a method we trust. v1 measured slippage from a tape of trades by "walking" the trades a market order would have hit. That method carries over; v1's numbers (Binance spot) don't. This build ports the method and tests it on tapes where the right answer is known by construction. Real numbers come later, from Kraken trades (phase 3) and from the futures we actually trade (the spike).

## Read first
- v1 `measure_slippage.py` (200 lines): the walk, and the two traps in its comments (timestamp units; which side of the tape a market buy hits).
- `BUILD_NOTES.md` §4 (never deduplicate on timestamp; store sizes at their own precision), §5 (no maker savings without measured markout).

## Deliver
1. `costs/measure.py`:
   - `Tape`: a validated frame of trades: `at` (tz-aware UTC), `price`, `size`, `aggressor` (`buy` or `sell`), in arrival order.
   - `walk_cost(tape, side, notional, window_start, window_end) -> WalkResult`: consume the trades a market order of `notional` on `side` would have matched inside the window (a buy matches trades whose aggressor is `buy`), in order; return the volume-weighted price paid, the reference price (the first trade price in the window), the slippage in price units and in basis points, and `filled: bool` (false when the window didn't hold enough volume; never a silently partial answer).
   - `effective_half_spread(tape, window) -> Decimal`: half the volume-weighted distance between consecutive opposite-aggressor trades in the window (a tape-only estimate, labelled as such).
   - `impact_curve(tape, sides, notionals, windows)`: a table of median and 90th-percentile slippage by notional.
2. Tests on synthetic tapes.

## Steps
1. Tests (red). 2. `Tape`. 3. `walk_cost`. 4. Spread estimate and curve. 5. Docs, report.

## Known answers and checks
**Tape A** (one window; aggressor `buy` unless marked):

| # | price | size (BTC) | aggressor |
|---|---|---|---|
| 1 | 100,000 | 0.010 | buy |
| 2 | 100,010 | 0.020 | buy |
| 3 | 99,995 | 0.050 | sell |
| 4 | 100,020 | 0.030 | buy |

- Market **buy** of 3,000.50 USD notional: takes all of #1 (1,000.00), all of #2 (2,000.20), and 0.30 USD of #4. Size bought = `0.010 + 0.020 + 0.30/100,020`; VWAP = `3,000.50 / size`; reference = 100,000; the test asserts VWAP to 1e-6 and slippage in bps to 1e-6 (the builder writes the exact decimals in the test from this arithmetic before coding).
- Market **sell** of 1,000 USD: matches only #3; price 99,995; reference 100,000 (first trade in the window); slippage `+5.00` in price units against the seller.
- Market buy of 100,000 USD: `filled == False`.
- Same-timestamp prints: duplicating #2's timestamp onto #1 changes nothing (order is arrival order; nothing is merged or dropped).

**Tape B** (alternating buy at 100,002, sell at 99,998, equal sizes, 100 trades): `effective_half_spread == 2.00`.

**Unit safety:** a tape whose timestamps are naive, or whose sizes were rounded to the price tick (a 0.004 size stored as 0), is rejected by `Tape` validation.

**Scale:** `impact_curve` on a 1,000,000-trade synthetic tape finishes in under 20 seconds on the CI runner.

## Not in this build
Any real data · any number that goes into a venue file · maker fills and markout.

## Halt if
- The meaning of `aggressor` in Kraken's files turns out not to be the taker side (it is stated as [Likely] in BUILD_NOTES §4). This build doesn't depend on it, but if evidence appears while reading, record it.

## Doc rows to update
`COMPONENTS.md` §2 "Cost and slippage measurement": method ported in B14; numbers pending real tapes.
