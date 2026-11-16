```yaml
id: B18
title: Costs vs typical price moves by holding time (proposal P-12)
size: S
model: opus
who: loop
needs: [B12, B13]
ticks: 2
touches:
  - v2/src/chronos2/research/**
  - v2/tests/research/**
  - docs/v2/research/cost-feasibility/**
may_modify_tests: []
```

# B18 — Costs vs typical price moves

## Why
Before anyone designs a strategy that holds for 20 minutes, we should know whether a 20-minute move is even bigger than the cost of trading it. The pre-build audit's rough numbers said: at these fees, holds under about 15 minutes barely cover costs, and hours look workable. This build does that calculation properly, on our own data door and cost model, and writes down a **minimum holding time** to design against. It describes the market; it tests no strategy, so it isn't a counted trial.

*Built only if the founder accepted P-12 (16 Nov: "take the call"; placed here, last in step 2).*

## Data
One of, in this order:
1. A Kraken BTC/USD 1-minute OHLCVT file supplied by the founder (loaded with B12's loader; this is also the real-file check that lets `VERIFIED_AGAINST_REAL_FILE` become true).
2. If none has been supplied when this build is reached: the public Bitstamp minute set the audit used (`ff137/bitstamp-btcusd-minute-data`, MIT), every output labelled "Bitstamp, not Kraken".

Either way the data goes through the door, so nothing from 1 Apr 2026 onward can be read, and the report prints the footprint.

## Read first
- `docs/v2/research/pre-build-audit.md` §2. Master doc §12 P-12 (including the founder's note: no holds under 15 minutes; 3:1 reward-to-risk stops planned). `BUILD_NOTES.md` §5 (nano fees in bps move with price).

## Deliver
1. `research/cost_feasibility.py`: for each calendar year from 2020 to the last full pre-seal year, and each horizon in {5 min, 15 min, 30 min, 1 h, 2 h, 4 h, 8 h, 24 h}: the median and mean absolute log move over non-overlapping windows; the round-trip cost in bps at that year's median price for nano BTC and for MBT at 1× and at 2× frictions (fees only, then fees plus a stated spread-and-slippage placeholder shown as a separate column and labelled "assumed, not measured"); and the break-even hit rate under two payoff shapes: symmetric (win = loss = the mean absolute move) and 3:1 (`25% + cost ÷ (4 × stop distance)`, stop = the mean absolute move).
2. `docs/v2/research/cost-feasibility/RESULTS.md`: the tables, the footprint, and one paragraph: "the shortest horizon at which the break-even hit rate at 2× fees is at or below 55% (symmetric) in every year from 2022 on is H". The **55%** and **2022** are fixed here, now.
3. `docs/v2/research/cost-feasibility/PREREGISTERED.md`: this spec's method section copied verbatim, committed in step 1 before any number is computed.
4. Tests on synthetic data.

## Steps
1. `PREREGISTERED.md` + tests (red). 2. The calculation. 3. Run on real data through the door. 4. `RESULTS.md`. 5. Report.

## Known answers and checks
- **Synthetic check:** on a generated random walk with hourly sd 0.5% and no drift (seed 5), the mean absolute 1-hour log move is `0.5% × sqrt(2/π) = 0.3989%` (± 0.01%), and the 4-hour figure is twice that (± 0.02%).
- **Cost columns** equal B13's `fees_in_bps` at the same price (cross-check, exact).
- **Break-even formulas, by hand:** mean move 37.0 bps, cost 9.7 bps → symmetric `p = 0.5 + 9.7 / (2 × 37.0) = 63.1%`; 3:1 with the stop at 37.0 bps → `25% + 9.7 / (4 × 37.0) = 31.6%`.
- **Seal:** asking the script for a year that reaches past 31 Mar 2026 fails at the door, not in the script.
- **Reproduces the audit:** if run on the Bitstamp set for 2024, the 1-hour median absolute move is 24.4 bps and the mean 37.0 bps (± 0.5 bps) [Certain — pre-build audit run]. If run on Kraken data the numbers will differ somewhat; the report shows both sets side by side when both are available.
- `RESULTS.md` states the horizon H, or states plainly that no horizon up to 24 h meets the rule.

## Not in this build
Any strategy, signal or filter · measured spreads (the placeholder column says so) · a decision about S-TREND as its own sleeve (that question is the founder's, with these tables in hand).

## Halt if
- Neither data source is reachable from the session.
- The result contradicts the audit's direction (short holds looking cheap): re-check the units before believing it, then report it either way.

## Doc rows to update
Master doc §12 P-12: "computed in B18; minimum horizon H = …; awaiting the founder". `docs/v2/research/README.md`: one row.
