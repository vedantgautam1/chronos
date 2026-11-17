```yaml
id: B17
title: Slippage and spread measurement method
size: S
model: opus
who: loop
needs: [B16]
ticks: 2
touches:
  - v2/src/chronos2/costs/**
  - v2/tests/costs/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B17 — Slippage and spread measurement method

## Why
B16 takes spread and slippage as inputs. Something has to produce them from real trading records, with a method we trust. v1 measured slippage from a tape of trades by "walking" the trades a market order would have hit. That method carries over; v1's numbers (Binance spot) don't. This build ports the method and tests it on tapes where the right answer is known by construction. Real numbers come later, from Kraken trades (phase 3) and from the futures we actually trade (the spike).

## Read first
- v1 `measure_slippage.py` (200 lines): the walk, and the two traps in its comments (timestamp units; which side of the tape a market buy hits).
- `BUILD_NOTES.md` §4 (never deduplicate on timestamp; store sizes at their own precision), §5 (no maker savings without measured markout).

## Deliver
1. `costs/measure.py`:
   - `Tape`: a validated frame of trades: `at` (tz-aware UTC), `price`, `size`, `aggressor` (`buy` or `sell`), in arrival order.
   - `walk_cost(tape, side, notional, window_start, window_end) -> WalkResult`: consume the trades a market order of `notional` on `side` would have matched inside the window (a buy matches trades whose aggressor is `buy`), in order; return the volume-weighted price paid, the reference price (**the first print on the same side** in the window, so the result is the cost of walking the book and holds no spread; B16 charges the spread separately), the slippage in price units and in basis points, and `filled: bool` (false when the window didn't hold enough volume; never a silently partial answer).
   - `effective_half_spread(tape, window) -> Decimal`: half the volume-weighted distance between consecutive opposite-aggressor trades in the window (a tape-only estimate, labelled as such).
   - `impact_curve(tape, sides, notionals, windows)`: a table of median and 90th-percentile slippage by notional.
2. Tests on synthetic tapes.

## Steps
1. Tests (red). 2. `Tape`. 3. `walk_cost`. 4. Spread estimate and curve. 5. Docs, report.

## Known answers and checks
**Tape A** (one window):

| # | price | size (BTC) | aggressor |
|---|---|---|---|
| 1 | 100,000 | 0.010 | buy |
| 2 | 100,010 | 0.020 | buy |
| 3 | 99,995 | 0.050 | sell |
| 4 | 100,020 | 0.030 | buy |
| 5 | 99,990 | 0.050 | sell |

All values below [Certain — computed with exact decimals, 16 Nov]:
- Market **buy** of 3,000.50 USD: takes all of #1 (1,000.00), all of #2 (2,000.20) and 0.30 USD of #4. Size `0.030002999400119976…` BTC; VWAP `100,006.667999600120`; reference 100,000 (first buy print); slippage `6.667999600` in price units = `0.666799960` bps. Each asserted to 1e-6.
- Market **sell** of 1,000 USD: matches only #3 at 99,995; reference 99,995 (first sell print); slippage **0** (one level, no walk; asserted as `abs(slippage) < 1e-12`, since an exact-decimal division can leave a remainder around 1e-45). The 5.00 between #1 and #3 is spread, and must not appear here.
- Market **sell** of 6,000 USD: all of #3 (4,999.75) and 1,000.25 USD of #5. Size `0.060003500350035…` BTC; VWAP `99,994.166423601`; reference 99,995; slippage `0.833576399` in price units = `0.083361808` bps against the seller. Each asserted to 1e-6.
- Market buy of 100,000 USD: `filled == False`.
- Same-timestamp prints: giving #1 and #2 the same timestamp changes nothing (order is arrival order; nothing is merged or dropped).

**Tape B** (alternating buy at 100,002, sell at 99,998, equal sizes, 100 trades): `effective_half_spread == 2.00`.

**Unit safety:** a tape whose timestamps are naive, or whose sizes were rounded to the price tick (a 0.004 size stored as 0), is rejected by `Tape` validation.

**Scale:** `impact_curve` on a 1,000,000-trade synthetic tape finishes in under 20 seconds on the CI runner.

## Not in this build
Any real data · any number that goes into a venue file · maker fills and markout.

## Halt if
- The meaning of `aggressor` in Kraken's files turns out not to be the taker side (it is stated as [Likely] in BUILD_NOTES §4). This build doesn't depend on it, but if evidence appears while reading, record it.

## For the gate
`COMPONENTS.md` §2 "Cost and slippage measurement" (this build edits it): method ported in B17; slippage is measured net of the spread; numbers pending real tapes.
