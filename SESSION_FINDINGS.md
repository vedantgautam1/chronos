# Session finding: the DSR trial-count trap, demonstrated on real data

**Date:** 2026-07-16
**Status:** permanent record — not scratch work. Cross-references
`docs/SPEC_HEPHAESTUS.md` (Moirai boundary, §10) and `HANDOFF.md` (I6
trial-ontology open question).

## The trial-ontology distinction

`run_experiment()`'s trial counter (invariant I6) advances on every
execution, with no distinction between a pre-registered hypothesis run
once and one point sampled from a parameter search. DSR's `N` parameter,
however, means something narrower and specific: the number of trials in
the search that produced the candidate being judged.

Two runs in this record store illustrate both ends of that distinction
correctly:

- **Trial #4** (`H-003-ma-crossover-milestone`, fast=20/slow=50) was a
  single pre-registered hypothesis with no preceding parameter search.
  Its correct DSR search-breadth is **N ≈ 1**.
- **The 280-point sweep** (trial_index 5–284, every `fast` in
  `range(5,55,5)` × every `slow` in `range(60,200,5)`) is one search
  over one hypothesis family. Any single cell pulled out of it — in
  particular the best-performing one — carries **N = 280**, because it
  was selected as the max of 280 draws, not evaluated on its own.

The global execution counter (I6) does not currently distinguish these
cases; get the N right by reasoning about what search produced the
candidate, not by reading it off the trial counter. This is a known
open problem, not silently resolved here.

## The measured cross-trial variance

`V[{SR_n}]`, the cross-trial variance of per-bar Sharpes across the 280
sweep cells, computed empirically from the real runs (not simulated):

```
V = 8.659587301602424e-05
```

This is the quantity `chronos_math_probe.py`'s `sr_star(V, N)` consumes
to compute the DSR benchmark — measured directly from this project's own
backtests rather than the probe's simulated zero-edge path.

## The winning cell

Highest per-bar Sharpe among all 280 combinations:

| fast | slow | trial_index | Sharpe (per-bar) | T (bars) |
|---|---|---|---|---|
| 25 | 60 | 117 | 0.0024061391952578497 | 4344 |

The raw Sharpe is barely above zero — this is the *maximum* of 280
near-noise results, not a standout performer.

## DSR under both N assumptions

| | N = 1.0001, V = 1e-4 (as if single pre-registered) | N = 280, V = 8.6596e-05 (honest — this cell came from a 280-point search) |
|---|---|---|
| **DSR** | 0.563 | 0.054 |

**Why the gap matters:** the DSR swings roughly 10x — from "56% chance
of real skill" to "5% chance" — using the *identical* Sharpe, purely
because of which search-breadth N is charged against it; treating a
searched-and-cherry-picked winner as if it were a single pre-registered
hypothesis (N≈1) launders exactly the selection bias DSR exists to
detect, and the honest N=280 reading correctly shows this winning cell
as indistinguishable from noise.

---

# Session finding: R6 (slippage) measured, and trial #4's corrected framing

**Date:** 2026-07-17. Cross-references `HANDOFF.md` (2026-07-17 R6 entry,
full method/drift-confound/limitation detail) and `docs/SPEC_HEPHAESTUS.md`
§16 (Assumptions Register, R6).

Six months of real Binance BTC/USDT aggTrades (Jan–Jun 2026, 4,344
hourly bars) were used to measure market-buy slippage at 9,000 and
90,000 USDT order sizes (`measure_slippage.py`). Zero bars had
insufficient liquidity at either size. The raw distribution was
drift-dominated — BTC fell ~33% across the window, and a difference
estimator (90k slippage − 9k slippage, per bar) isolates the
size-dependent part: median 0.0019bps, confirming true impact at these
sizes is below this measurement's resolution. Full method and the
drift-confound explanation are in `HANDOFF.md`; the practical outcome
was changing `CostConfig.slippage_bps`'s default from 10 to 1.

**Trial #4's registered result must be read against this change.** Trial
#4 (`H-003-ma-crossover-milestone`) ran under the OLD 10bps provisional
slippage and reported **-15.40% net**. Rescaling its itemized slippage
cost line item (756.45 USDT at 10bps) linearly to the new 1bps default
(75.65 USDT; fees and spread unchanged) gives a recomputed net of
approximately **-8.6% ("~-9%")**. This is a linear rescaling of the cost
breakdown, not a fresh engine run — trial #4 was never re-executed under
the new default, and an exact re-run could differ slightly (cost changes
can interact with cash-sufficiency checks in ways linear rescaling
doesn't capture).

**The milestone's registered prediction still holds either way:** trial
#4's pre-registered prediction was a losing result — the milestone
exists to prove the instrument works, not to claim an edge. At both
-15.40% (old cost basis) and ~-9% (measured cost basis), the strategy
loses. The correction changes the size of the loss, not its sign, and
therefore does not overturn the milestone's own stated purpose.

**Cross-comparability boundary:** every record with `trial_index <= 284`
(trial #4 through the full 280-point sweep) was produced under the OLD
10bps slippage value. None of those records are cost-comparable with
any run made after the 2026-07-17 default change without re-running —
do not compare a pre-284 Sharpe/return against a post-284 one and
attribute the difference to strategy or parameter changes alone.

---

## Moirai Phase 4a — the milestone judged through the three free stages (2026-07-30)

First real gauntlet numbers. The milestone MA-crossover (trial #285,
`H-003-ma-crossover-milestone`, canonical dev window 2026-01-01→2026-07-01,
4344 H1 bars, 42 completed round trips) run through stages 4.0/4.3/4.4 under
v001's provisional thresholds. **Verdict: FAIL, cause M4.3-dsr, authority
NO_AUTHORITY** (uncalibrated — a smoke test, not a judgment).

**4.3 Deflated Sharpe (the number this project exists to compute honestly):**
- per-bar Sharpe (non-annualized, ddof=1): **−0.005895** — a losing strategy.
- T = 4344; sample skew 0.287; raw kurtosis 15.21.
- honest search N: **compute_search_n = 0** — the 280-sweep that selected the
  milestone is legacy (`kind=None`, ≤#284), excluded by construction; there are
  zero SEARCH records in the store. Deflation N floored to 1 (a candidate is ≥1
  trial); at N=1 SR*→0 so DSR degenerates to PSR (no deflation to apply).
- **DSR @ raw N = 0.349** (< the 0.95 confidence gate → FAIL). Well-defined and
  small, not nan — the N=1/V=0 `0*-inf` trap is guarded.
- V, N̂ (JPM App. C): both **not_estimable** (D-08 guard: M=0). Phase 7 re-runs
  the sweep live under `kind=SEARCH` to re-establish N=280, at which point the
  0.563-vs-0.054 laundering counterfactual (T-e) becomes measurable end to end.

**4.4 Trade-shuffle Monte Carlo (1000 shuffles, ctx.rng seeded):**
- realized max-drawdown: **0.1365**.
- p95 shuffled max-drawdown (THE drawdown expectation): **0.2212** (≤ 0.40
  provisional ruin gate → PASS; the gate is a Themis placeholder, weakest-derived
  threshold, little information until Phase 6).
- no sequence-luck warning (realized DD not below the 5th percentile).
- terminal equity under proportional reinvestment: **0.9044** (−9.6%), order-
  invariant across all shuffles — close to the record's −9.08% ledger return, the
  gap being exactly the documented proportional-sizing approximation.

**4.0 Eligibility:** PASS — 42 round trips ≥ 30 min; `provisional_cost_constants:
true` recorded for stage 4.5 (a later phase); no unsafe flag; fragmentation screen
skipped (the milestone carries no `param_grid_description`).
