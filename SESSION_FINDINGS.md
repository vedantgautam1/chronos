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

---

## Phase 4b — signal-only null gate (4.1) and parameter plateau / N finalization (4.2), measured 2026-08-03

**Checkpoint 1 — stage 4.1 on the REAL milestone (trial #285, MA 20/50 BTC/USDT 1h,
H1 2026, gauntlet_seed 12345, `null_signal.B` = 2000):**
- θ̂ = mean(s_t·(fr_t − fr̄)) = **+4.52e-05** (small positive).
- **p-value = 0.1045** (one-sided, fraction of stationary-bootstrap θ ≥ θ̂) —
  **> α=0.05 → the entry rule does NOT beat noise before costs even enter (FAIL).**
  Unremarkable, exactly as the brief anticipated for a losing MA rule; not a
  "looks-wrong" result.
- D-R5-p block parameter **p_block = 1.0 (mean block 1.0, i.i.d.)** — VERIFIED
  genuine, not a mis-scaled selector: the window's log-return autocorrelations
  acf[1..10] are all inside the ±1.96/√T = ±0.0297 band (acf[1]=−0.008, acf[2]=−0.022,
  …), so the procedure settles at lag 1. Hourly BTC returns are near-white in linear
  autocorrelation, so i.i.d. resampling is the honest null here.
- Sensitivity bracket {p/2, 2p}: p(block 0.5) = **0.103**, p(block 1.0, 2p clamped to
  a valid probability) = **0.122**. All three ≥ α → the FAIL is stable;
  `fragile_to_block_length = false`.
- n_bars = 4344; n_long_bars = 2109 (≈48.5% long); `flat_portfolio_assumption: true`
  (exact for this state-independent MA entry).

**Checkpoint 2 — stage 4.2 → freeze → 4.3 on a SYNTHETIC candidate (temp store, grid
`fast in range(10,35,5)`, candidate fast=20/slow=50, 3 of 4 neighbors pre-seeded as
SEARCH):** the N-finalization machinery, end to end:
- pre-4.2 `compute_search_n` = **3** (neighbors fast=10/15/25 pre-seeded; fast=30 not
  yet run).
- 4.2 read the 3 present neighbors free and executed the one missing neighbor
  (fast=30) as `kind=SEARCH` → post-4.2 `compute_search_n` = **4** (incremented by
  **exactly 1**). `ctx.freeze_search()` fired; `search_frozen` False→True.
- 4.3 read the FROZEN N = **4** live (`search_n_raw = 4`, `n_used_for_deflation = 4`,
  `n_frozen: true`).
- **SR\* rose with the frozen N: SR\*(V, N=3) = 0.4573 → SR\*(V, N=4) = 0.5641** — a
  broken freeze→4.3 wiring that read the stale N=3 would set a strictly lower bar and
  fail the probe.
- `verdict.search_n = 4` == 4.3's N == post-freeze `compute_search_n` (the
  `VerdictNMismatch` divergence invariant held). 4.2 PASSed the plateau; the 4.3 DSR
  was 0 (V inflated to 0.287 by the FakeExchange monotonic-ramp neighbor's Sharpe
  ≈1.17 — a synthetic-data artifact, not a stage behaviour). This is probe G6c.

# Session finding: Phase 4c s1 — cost/capacity/shift on the milestone + first engine throughput

**Date:** 2026-08-03
**Status:** permanent record. Milestone MA(20/50) BTC/USDT 1h, H1 2026 dev window
(2026-01-01 → 2026-07-01), judged through stages 4.0–4.7 in full-evaluation mode under
v001 thresholds (uncalibrated → `NO_AUTHORITY`). Reproduce:
`uv run python scripts/moirai_phase4c_checkpoint.py` (temp store; records/ untouched).

## 4.5 cost stress — the losing rule loses harder, monotonically

Net return / per-bar Sharpe at each absolute slippage level (spread scaled in
proportion `half_spread = 1 × L/1`, taker held at 10 bps):

| level | net return | per-bar Sharpe | |
|---|---|---|---|
| base (1 bps) | **−9.08%** | −0.00590 | reproduces trial #285's scar exactly |
| 5 bps | −14.72% | −0.01081 | |
| 10 bps | −21.29% | −0.01687 | **gate** — net<0 → FAIL |
| 25 bps | −38.18% | −0.03425 | reporting-only |

`cost_gate_fail` (not `non_monotone` — every level loses; net return is monotone
non-increasing as cost rises). Margin criterion active (`provisional_cost_constants`
present; floor 0.005/bar). The −8.6%-linear-vs-−9.08%-actual scar is why each level is
a full engine re-run and `cost_summary` is never scaled — a CI spy confirms three real
VERIFICATION `ctx.run` calls with distinct config hashes and one identical data hash.

## 4.6 capacity — the cap does not bind; capacity is not the milestone's problem

Base per-bar Sharpe −0.00590. **10×** cash: Sharpe −0.00590 (degradation ≈ 4.7e-08),
remainder-cancelled notional **0.0** → **PASS** (degradation ≤ 0.3, remainder ≤ 0.2).
**100×** (reporting-only): Sharpe −0.00507, remainder fraction **3.28%**. At BTC/USDT
hourly depth the 5% participation cap barely bites even at $1M; the milestone is
size-agnostic, so its unprofitability is a signal/cost problem (4.5/4.3), not capacity.

## 4.7 shifted window — the dev window sits at the cached-data edge

Base per-bar Sharpe −0.00590. Stored H1 coverage is **2026-01-01 → 2026-07-08 04:00**,
so of the four shifts only **+1w** is inside it:

| offset | outcome |
|---|---|
| −2w | REFUSED (past_available_data — starts before 2026-01-01) |
| −1w | REFUSED (past_available_data) |
| +1w | per-bar Sharpe −0.00347, deviation 0.412 < 0.50 → within band |
| +2w | REFUSED (past_available_data — ends after 2026-07-08) |

1 of 4 within band → 0.25 < 0.80 → **FAIL**. This is the forward guard working, not a
crash: shifts past the stored data are refused, never silently truncated or sent to a
live fetch. The honest reading — a stability gate a window cannot even demonstrate does
not pass. (Spec §4.7's sign-agreement sub-gate is dormant: no v001 key.)

## First real engine throughput — the number Phase 5/6's budget hangs on

Six re-runs through the shared `rerun_candidate` helper (3 cost + 2 capacity + 1 shift),
each a ~4344-bar H1 backtest:

- per-run seconds: **[1.413, 1.454, 1.414, 1.416, 1.426, 1.406]**
- **median 1.415 s/run** (min 1.406, max 1.454).

Until now the per-engine-run cost was only *inferred* from bar counts. Implications:
a single stage 4.9 (~200 cadence-matched nulls) ≈ **4.7 min — feasible on this
hardware, NOT a session-2 blocker.** The genuine wall is Phase 6 calibration's nested
loop: `calibration.R`=500 × 7 ladder points × ~200 nulls × 1.4 s ≈ **~11 days** run
naively — this is the calibration-budget decision (STATE.md "Blocking"), now sizable
against a measured 1.4 s rather than a guess.

# Session finding: Phase 4c s2 — sub-period, null benchmark, descriptive on the milestone + full-pipeline throughput

**Date:** 2026-08-04
**Status:** permanent record. Milestone MA(20/50) BTC/USDT 1h through ALL eleven stages
(4.0–4.10) in full-evaluation mode under v001 thresholds (uncalibrated → `NO_AUTHORITY`),
dev window 2026-01-01 → 2026-07-01. Reproduce:
`uv run python scripts/moirai_phase4c_checkpoint.py` (temp store; records/ untouched).

## Complete verdict

`status: FAIL`, `authority: NO_AUTHORITY`, cause_of_death (full-eval, ordered) =
`M4.1, M4.3, M4.5, M4.7, M4.8, M4.9`. Every stage's outcome is present in the record.

## 4.8 sub-period stability — unjudgeable on the dev window

The 6-month dev window yields **K=1** twelve-month sub-window → `insufficient_subperiods`
(the gate needs ≥ 2 windows for a sub-period comparison and its HAC t). Honest and
expected — the same data-edge limitation 4.7 hits. The HAC machinery itself is verified
by a unit test that matches the as-built per-window-means HAC t directly against
`statistics.newey_west` on K=6 windows. **Gate (ii) is an OPEN/UNRATIFIED methodology
decision** (per-window-means vs pooled-per-bar; the latter contaminated by warmup-reset
seams) — the quant ratifies at v002/Phase 6 (HANDOFF 2026-08-04).

## 4.9 full-engine null benchmark — the milestone beats most random trading, not enough

Candidate net −9.08% ranked against **200** cadence-matched nulls (42 entries over 4344
bars, holding durations resampled from the milestone's realized round trips):

| null net-return distribution | value |
|---|---|
| min | −45.43% |
| median | −24.79% |
| p95 (gate) | −2.93% |
| max | +4.92% |
| **candidate percentile** | **88.5** |

The milestone sits at the **88.5th percentile** — it loses LESS than ~88% of random
same-cadence long-only trading (random trading pays more cost / worse timing), but does
NOT clear the 95th-percentile bar → **FAIL** (`does_not_beat_null_benchmark`). The gate
reads v001's `null_bench.percentile_gate: 95` as a PERCENTILE (p95 = −2.93%), never as a
0.95 fraction. Null placement is price-blind by construction (no price parameter).

## 4.10 descriptive (no gates)

- Per-calendar-year 2026: net −9.08%, per-bar Sharpe −0.0059.
- Annualized Sharpe over [2026-01-01, 2026-07-01]: naive √k **−0.5518**, Lo (2002) Eq.22
  AR(1)-corrected **−0.5507** (ρ = +0.002 — near-white, so Lo ≈ naive, as expected).
- Metrics: CAGR **−17.5%**, maxDD **15.1%**, Sortino **−0.79**, profit factor **0.77**,
  turnover **78×** initial cash, 84 fills / 42 round trips.
- 200d-MA regime skipped (need 200 days of prior history; dev window is ~181 days).
- Cross-asset ETH/USDT skipped (no ETH data cached; milestone strategy is symbol-bound).

## Full-pipeline throughput — the Phase 6 budget number

**207 engine re-runs** through the shared `rerun_candidate` helper (4.5+4.6+4.7+4.8+4.9),
**median 0.566 s/run** (min 0.556, max 1.471); 4.9's 200 nulls alone median 0.566 s
(≈ 113 s), whole pipeline ≈ 2¼ min. Faster than session 1's 1.4 s (nulls trade at random
cadence and run warm in-process). Recomputes the naive Phase 6 calibration budget:
`calibration.R=500 × 7 ladder points × ~200 nulls × 0.566 s ≈ ~4.5 days` (down from the
~11-day figure at 1.4 s). This is the number the Phase 5/6 budget decision sizes against.

# Session finding: Phase 5 Step 1 — canonical-window throughput and the recomputed calibration wall

**Date:** 2026-08-04
**Status:** permanent record. The Phase 6 budget number, measured on real data — NOT
the 0.566 s/run milestone-window figure (that was ~4,344 bars; superseded here).

## Setup

Canonical full-history verdict window ingested this session: **BTC/USDT H1,
2017-08-17 → 2026-08-03, 78,444 bars** (nothing sealed yet → full history). 28
data-quality gap notices (historical exchange outages — soft notices, served; no hard
integrity failures). Milestone MA(20/50), warm (parquet already loaded). Wall-clock via
`time.perf_counter`.

## Data snapshot pinned (I5 — what these numbers were measured against)

The on-disk parquet was unchanged across every (a)/(b)/(c) run, so all measurements read
this exact snapshot. A future restatement changes the hash and visibly invalidates any
verdict/measurement pinned to it (I5, §5.3 `data_restated`).

- **Oceanus snapshot hash:** `7c0b19aa91b9b662d9c7a3623b6aae8947ea9d8a0b1f7e80bcfe814e52e551c2`
- **Coverage:** BTC/USDT H1, first bar `2017-08-17T04:00:00+00:00`, last bar
  `2026-08-03T23:00:00+00:00`, **78,444 bars** (half-open request `[2017-08-17T00:00,
  2026-08-04T00:00)`).
- **28 gapped windows** (128 bars missing in total; all pre-2023 exchange outages, served
  with notices — not corruption):

```
 6 bars  2017-09-06 16:00 → 23:00        1 bar   2020-03-04 09:00 → 11:00
 1 bar   2018-01-04 03:00 → 05:00        2 bars  2020-04-25 01:00 → 04:00
33 bars  2018-02-08 00:00 → 02-09 10:00  3 bars  2020-06-28 01:00 → 05:00
10 bars  2018-06-26 01:00 → 12:00        1 bar   2020-11-30 05:00 → 07:00
 1 bar   2018-06-27 12:00 → 14:00        4 bars  2020-12-21 13:00 → 18:00
 7 bars  2018-07-04 00:00 → 08:00        1 bar   2020-12-25 01:00 → 03:00
 3 bars  2018-10-19 05:00 → 09:00        1 bar   2021-02-11 03:00 → 05:00
 7 bars  2018-11-14 01:00 → 09:00        1 bar   2021-03-06 01:00 → 03:00
 6 bars  2019-03-12 01:00 → 08:00        2 bars  2021-04-20 01:00 → 04:00
10 bars  2019-05-15 02:00 → 13:00        3 bars  2021-04-25 04:00 → 08:00
 8 bars  2019-08-15 01:00 → 10:00        4 bars  2021-08-13 01:00 → 06:00
 2 bars  2019-11-13 01:00 → 04:00        2 bars  2021-09-29 06:00 → 09:00
 2 bars  2019-11-25 01:00 → 04:00        1 bar   2023-03-24 12:00 → 14:00
 1 bar   2020-02-09 01:00 → 03:00
 5 bars  2020-02-19 11:00 → 17:00
```

## The three numbers (brief Phase 5 Step 1)

| # | measurement | result |
|---|---|---|
| (a) | one full-window engine run | **median 28.20 s** (min 27.72, max 28.34, n=5) |
| (b) | full 11-stage pipeline, short-circuit | **median 48.09 s** (min 45.53, max 57.24, n=3) |
| (c) | full 11-stage pipeline, full-evaluation | **2385.85 s ≈ 39.76 min** (n=1) |

(b) is cheap because the milestone fails at 4.1, so 4.5–4.9 never run; the ~48 s is the
4.1 capture run (~28 s) plus its B=2000 stationary bootstrap over 78k bars. (c) pays the
full stack. (c) per-stage: **4.9 = 2141.9 s** (35.7 min), 4.5 = 83.3 s, 4.6 = 57.3 s,
4.1 = 45.4 s, 4.8 = 28.6 s, all others < 0.2 s.

## The engine is SUPER-LINEAR in the window (the headline)

0.566 s at 4,344 bars → 28.20 s at 78,444 bars: **18× the bars, ~50× the time.** Per-bar
cost grows with trade count (the milestone books 1,846 fills over 9 years; the Decimal
ledger and order processing dominate). Do NOT linearly extrapolate engine cost from short
windows — the 0.566 s figure understated the canonical cost ~50×.

## Per-engine-run depends on trade cadence (the refinement (c) gives)

The calibration wall's per-run is NOT the milestone's 28.2 s — it is the **null-run**
time, and nulls trade at a lighter, random cadence:

| 4.9 null-run wall-clock (n=200, canonical window) | value |
|---|---|
| median | **8.96 s** |
| min | 7.38 s |
| max | 23.77 s |
| mean (= 2141.9 s / 200) | 10.71 s |

## Recomputed calibration wall (Phase 6, Mode E) — beside the stale ~4.5-day figure

`calibration.R = 500 × 7 ladder points × 200 nulls = 700,000` null engine runs, plus the
per-candidate non-4.9 stages. Three honest estimates:

| basis | per-unit | full Mode-E calibration wall |
|---|---|---|
| **STALE (STATE, at 0.566 s/run)** | 0.566 s | **~4.5 days** |
| brief formula, per-run = milestone (a) 28.2 s | 28.2 s | ~228 days (overestimate — 4.9 runs at null cadence, not milestone cadence) |
| brief formula, per-run = measured null median 8.96 s | 8.96 s | **~72.6 days** |
| **measured full-eval (c) × R×ladder candidates** | 2385.85 s/candidate × 3500 | **~96.6 days** |

**Headline: the naive full Mode-E calibration is ~2–3 months, not ~4.5 days** — a ~15–20×
blowup over the stale figure (and the stale figure itself understated by ~50× per run).
This is the Phase 6 budget problem, now measured. It makes the founder's recommended
**A (split modes) + B (reduced n_nulls in calibration)** necessary, not optional; C
(shorter synthetic window) stays rejected (biases V, which shrinks with T). Final Phase 6
scoping is Step 5, with these numbers in hand.

# Session finding: Phase 5 Step 3.0 — provenance pin + ambient-coupling audit (with hash proof)

**Date:** 2026-08-04

**L1 — provenance.** `generator.provenance()` now returns `synthetic:v1@7c0b19aa`: the
generator version AND the Oceanus snapshot its volume constants (m=7.189, s=1.169) were
measured from, so every synthetic run traces to the data its realism borrows.

**L2 — ambient-coupling audit (canonical ingest put full BTC history on disk).** One test
was materially coupled — `test_descriptive` (200d-MA + cross-asset availability depend on
coverage EXTENT); fixed last session (hermetic `available_range` monkeypatch). Everything
else is hermetic (all `get_bars` sites in tests pass `root=tmp_path` + a fake exchange;
`test_shift` monkeypatches `available_range`) or value-stable.

**Value-stability VERIFIED BY HASH (not inferred from gap dates).** The tests that read the
real default store over the 2026 dev window (`test_milestone`, `run_experiment` sites) are
unaffected because that window's bars are byte-identical pre/post ingest:

| parquet version | role | 2026-01-01→2026-07-01 window hash | bars |
|---|---|---|---|
| v0004 | pre-full-ingest highest | `fe8be146d37544d7` | 4344 |
| v0005 | full-history write | `fe8be146d37544d7` | 4344 |
| v0006 | current served (highest) | `fe8be146d37544d7` | 4344 |

The ingest only APPENDED pre-2026 history and extended the tail to 2026-08-03; it restated
no 2026 bar. (v0006 is gitignored, like all of `data/`.)

# Session finding: Phase 5 Step 3 — the should-PASS touchstones surface a provisional-threshold impasse (T-a → T-a1/T-a2)

**Date:** 2026-08-06 · Front-loading T-a (the fork-4 unknown) before building the others paid
off: it surfaced, with nothing else built, that **under the provisional §14 thresholds no honest
strategy clears all eleven gates.** Both should-PASS canaries are therefore pinned
`BLOCKED-ON-PHASE-6-CALIBRATION` (verdicts DEFERRED — neither PASS nor FAIL). Runs use the
Step-2 isolated harness, reduced touchstone nulls (`null_bench.n_nulls`=40 via dev-config
override; v001 untouched), and the test-time `available_range` monkeypatch.

## The two a-priori rules discovered (both pinned, not tuned)

- **SNR rule (regime timeability):** a regime edge is timeable only if its cumulative drift
  exceeds within-regime noise, i.e. persistence `L_bars ≥ 8760 / S²`. A 21-day/S=3 regime is
  noise-dominated (regime move 10.3% < within-regime noise 14.4%; SNR 0.72 < 1) → no MA can time
  it. This produced the corrected fixtures.
- **MA timescale rule:** `slow = regime half-life in hours`, `fast = slow/4` (canonical 50/200-day
  1:4). The MA speed follows the fixture's timescale class, independent of the seed — the
  milestone's intraday MA(20/50h) was an arbitrary demo choice that whipsawed σ=0.60 noise (284
  round trips) and is not a regime-timescale trend-follower.

## T-a1 — faint edge (S=3, 45-day regimes, σ=0.60, MA 270/1080h), full-eval, 40 nulls

`status: INSUFFICIENT_BREADTH` · cause 4.0. Eleven-stage table:

| stage | passed | score | note |
|---|---|---|---|
| 4.0 eligibility | ❌ | 10 | INSUFFICIENT_BREADTH (10 round trips < 30) |
| 4.1 signal-null | ✅ | 0.0025 | edge detected |
| 4.2 plateau | ✅ | — | no_neighborhood |
| 4.3 DSR | ✅ | 0.9951 | ≥ 0.95 |
| 4.4 shuffle | ✅ | 0.347 | p95 maxDD < ruin_dd 0.40 |
| 4.5 cost-stress | ✅ | 0.0156 | ≥ margin |
| 4.6 capacity | ✅ | 0.016 | |
| 4.7 shift | ✅ | 1.000 | |
| 4.8 subperiod | ❌ | 1.915 | subperiod_instability |
| 4.9 null-bench | ✅ | 97.5th | beats nulls |
| 4.10 descriptive | ✅ | — | no gate |

Edge-clarity gates all pass; the slow, faint edge legitimately under-trades → 4.0 breadth + 4.8
stability fail. **Not scoped to a PASS** (that would rig the canary); **not a FAIL** (the edge is
real). DEFERRED.

## T-a2 — higher-frequency edge (S=6, 12-day regimes, σ=0.60, MA 72/288h), full-eval, 40 nulls

`status: FAIL` · cause 4.4, 4.8. 47 round trips (breadth clears). Table:

| stage | passed | score | note |
|---|---|---|---|
| 4.0 eligibility | ✅ | 47 | breadth clears (≥30) |
| 4.1 signal-null | ✅ | 0.0065 | |
| 4.3 DSR | ✅ | 0.9783 | |
| 4.4 shuffle | ❌ | 0.535 | p95 maxDD 0.535 > ruin_dd 0.40 |
| 4.5 cost-stress | ✅ | 0.0110 | |
| 4.6 / 4.7 / 4.9 | ✅ | — / 1.0 / 97.5th | |
| 4.8 subperiod | ❌ | 4.391 | subperiod_instability |
| 4.10 descriptive | ✅ | — | |

Higher frequency clears breadth but trips 4.4 (higher exposure → maxDD 0.535) and 4.8. Still no
clean all-eleven PASS. DEFERRED.

## The meta-finding (Phase-6 PRECONDITION for pinning the should-PASS canaries)

The gauntlet's provisional §14 gates are **mutually tensioned** — each trips a different honest
should-PASS:

| | 4.0 breadth (≥30) | 4.4 ruin_dd (0.40) | 4.8 subperiod |
|---|---|---|---|
| T-a1 (slow, faint, 10 trips) | ❌ under-trades | ✅ 0.347 | ❌ |
| T-a2 (fast, strong, 47 trips) | ✅ | ❌ 0.535 | ❌ |

- **`min_round_trips`=30 (4.0)** and the **subperiod gate (4.8)** encode a hidden HIGH-FREQUENCY
  assumption: a genuine low-frequency real edge cannot clear them in a bounded window.
- **`ruin_dd`=0.40 vs σ=0.60 (4.4)** is exposure-dependent: a mostly-flat strategy clears it, a
  more-invested one does not — same class as the ruin_dd-vs-σ finding already logged.
- **4.8 fails for BOTH** — at K=3 windows a regime-timer's per-window outcome is inherently uneven.

Consequence: **the gauntlet as currently thresholded would reject a genuine slow edge in live
use.** Phase-6 calibration MUST reconcile `min_round_trips` / `subperiod` / `ruin_dd` before the
should-PASS canaries (T-a1, T-a2) can be pinned as PASS. This is their explicit pinning precondition.

---

# Session finding: Phase 5 Step 3 — the four DIE/reject touchstones built and PINNED (T-b…T-e) — 2026-08-07

**Model:** Opus. Suite **315 green** (+4 CI assertions in `tests/moirai/test_touchstones.py`).
Authority NO_AUTHORITY throughout (uncalibrated — these measure the INSTRUMENT). These four have
threshold-robust verdicts and are pinned now; the should-PASS canaries stay DEFERRED (above).

**T-b — should-DIE (GATE A), MA grid curve-fit to NOISE. Verdict FAIL, cause ∈ {4.2, 4.3}.**
Construction (founder 2026-08-07, Option 1): an 8-cell fast×slow grid (`fast∈{10,20,30,40} ×
slow∈{80,120}`) searched over a ZERO-EDGE frame (`target_sharpe=0.0`, seed 20260202, 2-yr base
window). Whole grid registered `kind=SEARCH` under one hypothesis → **honest N=8, not 1** (verified:
verdict `search_n==8`, and 4.3's `search_n_raw==8`). Honest argmax = **fast=40/slow=120**, per-bar
Sharpe 0.00625 (a barely-positive noise-max; 7 of 8 cells negative — pinned a priori, drift-guarded).
Full-eval per-stage table (the founder-checkpoint table):

| 4.0 | 4.1 | **4.2** | **4.3** | 4.4 | 4.5 | 4.6 | 4.7 | 4.8 | 4.9 | 4.10 |
|---|---|---|---|---|---|---|---|---|---|---|
| PASS | PASS | **FAIL** (spike, not plateau; median & cliff both fail) | **FAIL** (DSR 0.483 @ N=8 < 0.95) | FAIL | FAIL | FAIL | PASS | FAIL* | FAIL (self-pct 92.5) | PASS |

Dies at BOTH overfit gates {4.2, 4.3} — GATE A holds; 4.8 (`*` not asserted, form unratified until
v002) is NOT relied on. Note 4.1 PASSED on the cherry-picked cell — a single gate slips; the OVERFIT
gates are what catch it (exactly why GATE A runs full-eval, not short-circuit). Runtime 199 s.

**T-c — should-DIE via safety. Verdict NON_PROMOTABLE, terminal at 4.0.** `unsafe_same_bar_fill=True`
(flag-gated future leak, I1 untouched) → engine stamps the unsafe warning → 4.0 returns
NON_PROMOTABLE and short-circuits. Cause `M4.0-eligibility`. Runtime 0.5 s.

**T-d — null baseline. Verdict FAIL, 4.9 self-percentile 27.5% ∈ [0.2, 0.8].** Seeded price-blind
`NullStrategy` (45 random entries, strategy seed 4040) over a zero-edge 2-yr frame. FAILs (4.1/4.3/
4.4/4.5/4.7/4.8/4.9). Its **4.9 self-percentile = 27.5%** — mid-distribution, as a null must be (an
extreme percentile would mean the 4.9 benchmark is mis-calibrated). Honest draw, NOT reseeded; the
CI asserts the BAND [0.2,0.8], not the point 0.275. Runtime 108 s.

**T-e — the laundering demo as regression. Verdict: DSR@N=1 > DSR@N=280, and DSR@N=280 < 0.95.**
Reproduced on the SHIPPED `statistics.dsr` from a COMMITTED provenance-stamped fixture
(`fixtures/te_laundering_winner.json` — the 280-sweep winner's per-bar returns, cell fast=25/slow=60
= trial 117, snapshot 7c0b19aa, V=8.6596e-05, extracted ONCE from the 119 MB gitignored records):

| | N = 1 (as if pre-registered) | N = 280 (honest search) |
|---|---|---|
| **DSR** | **0.56300** | **0.05438** |

`0.56300 > 0.05438` AND `0.05438 < 0.95` — the honest-N form (NOT the §6 chained form, a confirmed
v002 defect: 0.5630 ≯ 0.95). Runtime <1 s. Legacy fixture; Phase 7 re-pins against live SEARCH records.

**CI budget:** the pinned set runs ~5.1 min (T-b 199 s + T-d 108 s dominate; 4.9's 40 nulls ≈ 80 s
each). Within the §6 ≤10-min budget. Heavier than the old budget-note guess (which assumed T-b
short-circuit — impossible under GATE A, since short-circuit never exercises 4.3). Trimming T-b's
window (it does not assert 4.8) is available as a Step-5 budget lever if wanted.
