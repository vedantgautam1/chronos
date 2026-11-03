# CHRONOS × JESSE — Deep Comparison and Integration Master Plan

**Date:** 2026-07-28
**Sources:** full clone of `jesse-ai/jesse` @ master (v2.4.1, MIT) and
`vedantgautam1/chronos` @ main (152 tests, Stage 0). Every claim below was
verified against actual source code, not READMEs. Confidence tags per
project convention.

> **FOUNDER DECISIONS ADOPTED 2026-07-28 (supersede any conflicting
> phrasing below; full record in HANDOFF.md same date):**
> 1. **Scope clarified:** Chronos's end state is the full pipeline —
>    research → backtest → journal (Mnemosyne) → live simulation → live
>    trading (Stage 2 rail) → risk monitoring (Themis/Nemesis/Argus).
>    "Research instrument" describes Stage 0's rigor, not the product.
> 2. **Architecture: Chronos core + rail TBD.** Hephaestus/Moirai/
>    Mnemosyne remain the truth layer. The Stage-2 execution rail
>    (build Hermes vs adopt Jesse's licensed closed-source live plugin)
>    is DEFERRED until a strategy passes validation. Jesse is never the
>    backtester (no slippage/spread/liquidity model exists in its engine).
> 3. **Full Moirai, built as one deliverable.** *(This 2026-07-28 line
>    originally scoped a reduced "v1-first" gauntlet with the
>    touchstone/power-curve machinery deferred; that split was REVERTED by
>    D-06 — founder decision 2026-07-28, reaffirmed 2026-07-29. Superseded
>    text retained per the append-only/no-silent-rewrite discipline; the
>    live decision follows.)* The v1 gauntlet is the complete validation
>    set — DSR at honest N, walk-forward, cost stress, the signal-only null
>    gate, the touchstone ladder, the calibration harness, and the
>    published power curve — with nothing deferred to a later gauntlet
>    version. The Gate 0→1 acceptance list lives in `docs/SPEC_MOIRAI.md`
>    §15. See HANDOFF.md (2026-07-29) and STATE.md.
> 4. **Mnemosyne hardening path:** SQLite store (ACID; autoincrement =
>    trial index) when parallelism is needed (Phase E3); `flock` file
>    locking is the acceptable quick fallback.

---

## 0. Weakest part of the request (read this first)

The framing "make Chronos everything Jesse is and much more, since it's
built on whatever Jesse has" contains two errors that, uncorrected, would
damage the project:

1. **Chronos is not built on Jesse and should not become Jesse.** Jesse is
   a retail *product*: a FastAPI web dashboard, a strategy IDE, a GPT
   assistant, 300+ indicators, live-trading for hobbyists. Chronos is a
   *research instrument* whose entire thesis is rejecting almost every
   strategy. Roughly 60% of Jesse's codebase (controllers, websockets,
   auth, tabs, notification keys, LSP server, static frontend — 85% of the
   repo by line count is JavaScript) is product surface Chronos must NOT
   absorb. Copying it would burn months and add zero research honesty.
   [Certain — verified against the repo's language split and module list]

2. **"Everything Jesse has" is not a superset worth having.** In the two
   dimensions Chronos actually competes on — execution realism and
   statistical honesty — Jesse is *behind* Chronos today, not ahead
   (see §2). The correct goal: absorb Jesse's genuine engineering
   advantages (intrabar simulation, 1m-ground-truth data architecture,
   parallel compute, robustness testing machinery) while keeping Chronos's
   validation discipline, which Jesse has no equivalent of.

One more correction: **Jesse's live-trading engine is not in the open
repo.** The OSS code gates it behind `jh.has_live_trade_plugin()` — the
live drivers are a closed-source plugin distributed through jesse.trade.
"Lifting everything Jesse is" is not even mechanically possible for the
part that trades real money. Hermes must be built, not copied.
[Certain — verified: `jesse/__init__.py` imports live_controller only if
the plugin exists; no live execution drivers exist in the repo]

---

## 1. Barriers assessment (the direct answer to your question)

### 1.1 Legal / licensing — NO material barrier

- Jesse core is **MIT licensed** (Copyright 2020 Jesse.Trade). You may
  use, copy, modify, merge, and sell derived work. The only obligation:
  if you copy substantial verbatim code, preserve their copyright notice
  in those files. Ideas, patterns, and algorithms carry no obligation at
  all. [Certain — read LICENSE in the repo]
- `jesse-rust` (their Rust kernel) is a separate published crate/wheel by
  the same team; verify its license before importing it as a dependency
  (safer: write our own Rust/numba kernels — they are small).
  [Likely MIT, unverified]
- The closed live-trade plugin cannot be copied — patterns only, from the
  OSS driver interfaces. [Certain]

### 1.2 Computational power — NO barrier at Stage 0–1; cheap at any stage

Measured/derived workload sizes:

| Workload | Size | Feasibility on your Mac |
|---|---|---|
| Current hourly milestone (6 mo, 4,344 bars) | trivial | seconds [Certain — it already runs] |
| 280-cell sweep, hourly engine runs | 280 × 4,344 bars | minutes [Certain — already done] |
| Moirai calibration ladder (5 effect sizes × ~300 seeded realizations × 6.2 yr hourly ≈ 54k bars each) | ~1,500 engine runs | hours single-core, **minutes-to-~1hr parallelized** [Likely] |
| 1m-resolution simulation, 6.2 yr, single symbol | ~3.26M bars/run | one run: seconds-to-minutes; 1,500-run calibration at 1m: overnight on 8 cores, or ~1–2 hr on a rented 32-core box [Guessing on exact throughput; the order of magnitude is safe] |
| 1m history storage, BTC/USDT since 2017 | ~4.6M rows ≈ 150–300 MB Parquet | trivial [Certain] |
| Monte Carlo (1,000 trade-shuffle scenarios) | reconstruction only, no re-simulation | minutes [Certain — Jesse's version doesn't re-run the engine] |

**The honest bottom line:** you will not run out of computational power
for anything on the current roadmap. The heaviest planned workload
(power-curve calibration at 1m resolution) is an overnight laptop job or
a ~$1–3 cloud burst. Compute becomes a real constraint only in futures
you have already rejected (dozens of symbols × 1m × millions of MC paths
× ML feature search), and even then it's rental, not infrastructure.

### 1.3 Running costs

| Item | Cost | Notes |
|---|---|---|
| Data (Binance public klines + aggTrades) | **$0** | already proven in R6 work |
| Local compute (Stage 0–1) | **$0** | Mac is sufficient |
| Cloud burst for big calibration campaigns | ~$0.5–1.5/hr spot for 16–32 cores; **tens of dollars per campaign, occasional** | optional, not required |
| Stage 2 live ops (Hermes) | VPS $5–40/mo | hourly-frequency strategies need no colocation |
| PostgreSQL / Redis (if ever adopted) | $0 self-hosted | Chronos's Parquet+JSONL is fine for years |
| Jesse ecosystem costs | $0 — we take nothing that costs money | their paid plugin is not usable anyway |

### 1.4 The REAL barriers (ranked — none of them are money or compute)

1. **Team bandwidth.** Jesse's engine encodes years of accumulated
   edge-case handling (order lifecycle, partial fills, forming-candle
   generation, exchange quirks). Reimplementing the useful subset with
   Chronos-grade tests is person-weeks per item. The plan in §4 sequences
   this so nothing blocks Gate 0→1. [Certain]
2. **Mnemosyne is single-process.** Every parallel-compute win (Ray,
   multiprocessing sweeps, parallel calibration) is **blocked** on the
   record store: the current stub has no file locking; two workers would
   corrupt the trial counter and violate I6. Parallelism requires
   Mnemosyne hardening first. This is the one hard technical dependency
   in the whole plan. [Certain — stated in HANDOFF.md limitations]
3. **Scope-creep risk.** The single most likely failure mode of this
   integration is starting engine upgrades before the Moirai exists,
   leaving Chronos permanently "almost validated." §4 makes the Moirai
   the immovable first phase. [Likely, but it is the standard way such
   projects die]
4. **Invariant erosion.** Every Jesse pattern imported must be re-derived
   under I1–I9. Jesse's own code violates several of them by design
   (global mutable store, no run logging, no hypothesis discipline).
   Import behavior, never architecture. [Certain]

---

## 2. The verified head-to-head (what the code actually says)

### 2.1 Where Chronos is ahead — protect these, never trade them away

| Dimension | Chronos | Jesse | Verdict |
|---|---|---|---|
| **Cost model** | Fees + slippage + half-spread, itemized per fill, measured R6, provisional-flag discipline, no cost-free path (I2, AST-enforced) | **No slippage model exists anywhere in the codebase. No spread. Market orders fill at `current_price` exactly; flat fee only. No participation cap, no liquidity check against volume.** | Chronos categorically ahead. Jesse's "accuracy" claim is about look-ahead avoidance, not cost realism. [Certain — grep for "slippage" returns zero engine hits; `Sandbox.market_order` fills at current price] |
| **Fill realism vs liquidity** | 5% participation cap, partial fills, cancel-and-record remainders, no fills on zero-volume bars, no prices outside bar range | Orders always fill fully at their price when touched | Chronos ahead [Certain] |
| **Statistical honesty** | DSR with honest N from `compute_search_n()`, SR* floored, non-annualized Sharpe, register-sourced methods with known-answer tests, sealed holdout, pre-registered hypotheses, I9 judge-hashing | Naive `mean/std·√365` Sharpe; "smart sharpe" autocorr penalty is unsourced; optimizer selects max fitness across hundreds of Optuna trials with **zero selection-bias accounting**; no experiment log; no hypothesis concept; no holdout sealing | Chronos categorically ahead. Jesse's optimize mode is, by Chronos's standards, a selection-bias machine: it manufactures exactly the N-laundering your SESSION_FINDINGS demo quantified (DSR 0.563 → 0.054). [Certain] |
| **Determinism & provenance** | 5-coordinate reproducibility, byte-compare probe, append-only records, `-dirty` SHA honesty | Seeds exist for MC scenarios; backtests have no run records, no config hashing, no provenance at all | Chronos ahead [Certain] |
| **Accounting exactness** | Decimal ledger, LEDGER_QUANTUM, reconciliation identity tested every bar | float throughout, no reconciliation identity | Chronos ahead [Certain] |
| **Look-ahead enforcement** | Structural: bounded MarketView, poisoned-future probe that catches planted leaks | Convention + architecture: forming candles generated from 1m stream (good), but nothing equivalent to the poisoned-future probe; a strategy CAN reach `store.candles` internals | Chronos ahead on enforcement; Jesse ahead on multi-timeframe mechanics (below) [Certain] |

### 2.2 Where Jesse is ahead — the genuine steal list

| # | Capability | What it actually is (verified) | Value to Chronos |
|---|---|---|---|
| J1 | **1m ground truth, all timeframes derived** | Jesse stores/imports 1m candles and generates every higher timeframe in-sim (`generate_candle_from_one_minutes`); trading any timeframe still steps through 1m internally | Eliminates cross-timeframe inconsistency; prerequisite for J2. Oceanus currently fetches/stores each timeframe independently — two fetches of "the same market" can disagree. **Highest-value data-layer upgrade available.** [Certain] |
| J2 | **Intrabar order triggering at 1m resolution** | Limit/stop/liquidation triggers checked per 1m candle via `candle_includes_price()`; `split_candle()` splits the bar at the trigger price so entry and post-entry exits sequence correctly within one trading-timeframe bar | Chronos's next-bar-open on 1h bars cannot see a stop hit mid-bar, cannot express protective stops honestly, and marks equity only at closes (intra-bar drawdown invisible — already listed as a known limitation in your HANDOFF). This is **the single most valuable engine idea in Jesse.** [Certain] |
| J3 | **Two-speed simulation (step vs skip)** | `_step_simulator` walks every 1m candle; `_skip_simulator` (fast_mode) jumps in larger strides when no orders are pending | Pattern for keeping 1m fidelity affordable in sweeps/calibration. [Certain mechanism; port is design work] |
| J4 | **Trade-order-shuffle Monte Carlo** | Shuffle closed trades, reconstruct equity curves, build percentile bands + p-values against the original (1,000 scenarios, seeded, Ray-parallel) | Direct Moira candidate: "was the equity path shape luck?" Cheap (no re-simulation). Methodology needs a register entry before it can influence verdicts. [Certain] |
| J5 | **Candle-pipeline synthetic-data harness** | `BaseCandlesPipeline` abstraction feeding modified 1m candles into an unmodified backtest: Gaussian-noise pipeline, moving-block bootstrap pipeline (block size derived, deltas of close/high/low resampled, OHLC bounds re-enforced) | The *harness* is exactly what Moirai robustness tests and the touchstone calibration ladder need (inject known effect sizes / perturbed paths through the REAL engine). Their MBB is heuristic; replace internals with R5's Politis-Romano stationary bootstrap, keep the plumbing idea. [Certain] |
| J6 | **Signal-only null test** | `rule_significance_test()`: run the strategy with orders suppressed, record +1/−1/0 signals per bar, detrend log returns, bootstrap the signal-weighted mean, p-value vs null | Cheap early Moira ("does the entry rule beat noise before costs even enter?"). Kill ideas for cents before spending on full runs. Bootstrap scheme must be re-derived under R5 (theirs is i.i.d. resampling — wrong for autocorrelated returns; your register already knows better). [Certain about their implementation] |
| J7 | **Parallel execution fabric (Ray + Optuna infra)** | Ray remote functions for MC scenarios and Optuna trials, progress streaming, seed-per-scenario | Adopt the *infrastructure* for sweeps and calibration. Reject the fitness methodology entirely. **Blocked on Mnemosyne hardening (§1.4.2).** [Certain] |
| J8 | **Rust/compiled hot loops** | `candle_from_one_minutes`, `fix_jumped_candles`, ~15 indicators in Rust; bit-exactness documented against numpy | Pattern (not dependency): if 1m simulation makes Python the bottleneck, move candle aggregation + the event loop's hot path to Rust/numba with byte-identical tests. Determinism probe already exists to verify. [Certain] |
| J9 | **Exchange driver abstraction** | `CandleExchange` ABC: `fetch()`, `get_starting_time()`, `get_available_symbols()`, rate limiting, backup-exchange failover, 10+ implementations | The right shape for Oceanus multi-venue later; also the template for Hermes's execution drivers at Stage 2. [Certain] |
| J10 | **Descriptive metrics battery** | Sortino, Calmar, Omega, Serenity, Ulcer, CVaR, streaks, expectancy, holding periods, long/short win rates | Cheap to port as *descriptive* reporting on BacktestResult. Must never enter verdicts without register sourcing — several (serenity, "smart" variants) have no primary source and would go to §16 Assumptions at best. [Certain] |
| J11 | **Indicator library** | 300+ indicators, consistent array-in/float-or-array-out API | Optional convenience: vendor a vetted subset as pure functions strategies may call **on bounded-view data only**. The engine must never precompute them (your spec §3 explicitly forbids the warm-up-leak facility — that rule stands). [Certain] |
| J12 | **Forming-candle semantics** | Partial candle of the trading timeframe continuously updated from 1m stream; indicators see the forming bar consistently between backtest and live | Matters at Stage 2 (live parity: backtest logic == live logic). Record as a Hermes design input. [Certain] |
| J13 | **ML pipeline shape** | gather features/labels during backtest → CSV → sklearn train → deploy `ml_predict()` in-strategy | Relevant only when R2 (purged/embargoed CV) activates. Their pipeline has NO leakage protection between train/test at the label level — adopt shape, add purging. [Certain] |

### 2.3 What to explicitly REJECT (with the concrete failure mode)

| Jesse pattern | Failure mode it would import |
|---|---|
| Global mutable `store` singleton | Cross-run state bleed; parallel corruption; the exact class of silent bug I3/I5 exist to prevent. Chronos's injected-collaborator design is strictly better. |
| Optimizer fitness methodology (normalized ratio × trade-count, pick the max) | Industrial-scale N-laundering: hundreds of looks, zero charge to DSR. If a Chronos optimizer ever exists, every Optuna trial is a `SEARCH`-kind record under ONE hypothesis, and the winner is judged at the honest N. |
| Web dashboard / controllers / auth / websocket layer | Months of product work, zero research value, permanent maintenance tax. Your results-viewer deferral stands. |
| "Smart sharpe"/serenity-style unsourced stats in decisions | Violates the register rule — no primary source, no known-answer test. |
| Filling at touched price with no liquidity model | Re-introduces the fantasy-fill bias Hephaestus §5 was built to kill. |
| No-record backtesting (`research.backtest()` free function) | Unlogged runs — direct I3/I6 violation. Every execution goes through `run_experiment()`, forever. |
| Their MBB block-size heuristic ("max(10, batch/10)") | Un-derived tuning constant; R5's primary source (Politis-Romano §5) prescribes the procedure. Use it. |

---

## 3. What "better than Jesse in every way that matters" concretely means

Chronos should NOT try to beat Jesse at being a product. Define superiority
on the axes that decide whether money survives:

1. **Execution realism:** Jesse detects triggers at 1m but fills at
   fantasy prices with no costs. Chronos already has honest costs; add
   J1+J2 and Chronos has honest costs *at 1m trigger resolution* —
   strictly better than both current systems. That is the crown jewel of
   this whole integration.
2. **Statistical honesty:** already ahead; the Moirai widens the gap to
   something Jesse simply does not have (deflated selection-aware
   verdicts, sealed holdout, power curves, judge-hashing).
3. **Robustness machinery:** Jesse's MC/bootstrap machinery re-founded on
   R4/R5 sources = Jesse's breadth with Chronos's rigor.
4. **Provenance:** no comparison — Jesse has none.
5. **Deliberately conceded to Jesse, forever:** GUI, indicator count as a
   marketing number, beginner ergonomics, community plugins, GPT
   assistant. These are product axes; conceding them is a strategy, not a
   loss.

---

## 4. THE INTEGRATION PLAN — phased, gated, invariant-safe

Ordering rule: **nothing may delay Gate 0→1.** Phase M is unchanged
Chronos roadmap; Jesse's influence enters M as *design inputs only*
(zero new code dependencies). Engine/data upgrades follow the gate.

### Phase M — the Moirai, enriched by Jesse's ideas (NOW; owns the next session)

Deliverables unchanged: `SPEC_MOIRAI.md` → approval → build. Jesse-derived
additions to fold INTO the spec (each as a candidate Moira with its own
threshold entry under I9):

- **M-a. Signal-only null gate (from J6).** Cheapest gate in the DAG,
  runs before any full engine spend. Re-derive the bootstrap under R5
  (stationary bootstrap, p chosen per Politis-Romano §5 autocovariance
  procedure — an open decision your handoff §8 already lists). Detrending
  step: adopt (it is correct and cheap). `kind=VERIFICATION`.
- **M-b. Trade-shuffle Monte Carlo (from J4).** Percentile bands on
  max-drawdown and terminal equity from shuffled trade order. Cheap (no
  re-simulation). Threshold = named, hashed config entry. Needs a
  register decision: the method itself is folklore-standard; source it
  or place it in §16 Assumptions with a sensitivity range.
- **M-c. Candle-pipeline harness (from J5) as the CALIBRATION mechanism.**
  The touchstone ladder ("inject known effect S ∈ {0.25…2.0}, measure
  detection rate") needs synthetic paths through the REAL engine — that
  is exactly the pipeline pattern. Implement as an Oceanus-adjacent
  test-data generator feeding `get_bars()`-shaped frames into
  `run_experiment()`; NEVER as a bypass of the one-door rule (I7):
  synthetic data enters through a clearly-marked test fixture door, not
  through a second data path.
- **M-d. Cost-stress form decision** (already open): Jesse offers no
  guidance here (it has no cost model). Recommend absolute levels
  (5/10/25 bps) over multipliers-of-1bps for exactly the reason your
  handoff flags — 2× of a tiny base is a weak stress. Provisional,
  founder approves.

**Explicitly NOT in Phase M:** any engine or data-layer change. The
gauntlet judges the engine as it exists.

### Phase E1 — data layer: 1m ground truth (post-Gate 0→1) [from J1]

1. Oceanus ingests and stores **1m** as the canonical series per symbol
   (Parquet, versioned snapshots exactly as today). ~4.6M rows for
   BTC/USDT full history — trivial.
2. `get_bars(timeframe=X)` derives X-bars from stored 1m by aggregation
   (one tested aggregation function, hash-covered). Higher-timeframe
   fetching remains only as a cross-check tool (restatement probe gains a
   second use: compare derived vs exchange-served 1h bars).
3. Snapshot hash now covers the 1m ground truth → every derived
   timeframe inherits provenance for free.
4. Invariant impact: none violated; I7 strengthened (one door, one
   ground truth). Tests: aggregation known-answer fixtures (hand-computed,
   like everything else), derived-vs-fetched consistency check on a real
   week.
5. Effort: days, not weeks. Prerequisite for E2.

### Phase E2 — engine: intrabar fill resolution (after E1) [from J2, J3]

The big one. Hephaestus keeps its decision cadence (strategy decides at
trading-timeframe closes; next-open fill convention for entries stands),
but the broker gains a **1m fill path** between decisions:

1. Between decision bar t and t+1, the broker walks the 1m candles,
   checking pending limit/stop orders per 1m bar with the SAME
   conservative conventions (strict trade-through at 1m; touch ≠ fill;
   participation cap now against 1m volume — a *stricter* and more
   honest cap).
2. Protective stop orders become expressible for the first time
   (currently impossible to model honestly at 1h resolution). This
   unlocks realistic risk-managed strategies for Stage 1.
3. Equity marking gains optional 1m resolution → intra-bar drawdown
   becomes visible (removes a known limitation; Monte-Carlo drawdown
   Moira gets honest inputs).
4. Same-bar entry/exit sequencing: adopt the `split_candle` idea with
   the conservative rule — if entry and exit could both trigger in one
   1m bar, assume the ADVERSE ordering. (Jesse splits at the price and
   sequences optimistically-neutral; Chronos should pick the pessimistic
   branch, consistent with the trade-through convention.)
5. Invariant impact: I1 (view stays bounded at decision times — 1m data
   used by the broker only, never shown to the strategy), I2 (cost model
   routes every 1m fill), I5 (deterministic — no RNG involved). All seven
   probes must pass unchanged; poisoned-future probe extended to poison
   1m tails too.
6. Protected path: this is cost-model/fill-logic territory → diff-first,
   founder approval, hand-computed fixtures for multi-1m-bar fill
   scenarios. Effort: 1–2 weeks equivalent. The most test-intensive item
   in the plan, and worth it.

### Phase E3 — throughput: Mnemosyne hardening, then parallelism [from J7, J8]

1. **Mnemosyne first** (this is on the roadmap anyway): single-writer
   lock or writer-process for the JSONL store + trial counter; parallel
   workers submit results through it. Without this, no parallel sweeps —
   period.
2. Then: multiprocessing (or Ray, if deps are acceptable) pool where each
   worker calls `run_experiment()` with `kind=SEARCH` under ONE
   registered hypothesis; records serialize through the single writer.
   Target: the 1,500-run calibration campaign in ~an hour on the Mac.
3. Optional, only if profiling says so: numba/Rust kernel for 1m→X
   aggregation and the broker's 1m walk, with byte-identical output
   asserted by the existing determinism probe. Do not import `jesse-rust`
   the dependency; import the *pattern*. [J8]
4. Effort: Mnemosyne days; pool days; kernels only-if-needed.

### Phase E4 — reporting & library conveniences [from J10, J11, J9]

1. Port the descriptive metrics battery as pure functions over
   `BacktestResult.returns` (`reporting/` module, clearly non-verdict).
   Anything that wants verdict power goes through the register first.
2. Vendor a vetted indicator subset (EMA/SMA/ATR/RSI + what strategies
   actually request) as pure functions over view-provided arrays, with
   known-answer tests against hand-computed values. Warm-up handling is
   the strategy's job from bounded data, exactly as spec §3 demands.
3. Refactor Oceanus's exchange touchpoint behind a small
   `CandleSource` protocol (fetch/get_starting_time/available_symbols)
   — a two-hour change now that pays off at multi-venue time. [J9]

### Phase L — Stage 2 execution (Hermes), Jesse as reference only [J12, J9]

When Stage 2 opens: Jesse's OSS driver interfaces and forming-candle
semantics are the reference for backtest/live parity design. Their live
plugin is closed; nothing liftable. Paper-trading mode = Hephaestus
broker pointed at live 1m feed — the E2 work makes this nearly free.
Everything under Themis/Nemesis (risk vetoes, kill switch) has no Jesse
counterpart at all; that remains original Chronos design.

---

## 5. Concrete changes to what is currently built

Small, additive, non-blocking amendments to existing components (all
post-Gate 0→1 except where noted):

1. **Oceanus:** add 1m as canonical timeframe + aggregation door (E1).
   Extend restatement probe to compare derived vs fetched bars. The
   coverage-metadata quirk (edge re-fetching) becomes more important at
   1m volume — fix it during E1.
2. **Hephaestus types:** `BacktestResult` gains nothing for E2 —
   fills already carry bar_time; 1m-resolution fills just populate finer
   timestamps. Equity curve optionally gains 1m marks behind a config
   flag (default off until Moirai thresholds are recalibrated for it).
3. **Broker:** 1m walk + stop orders + adverse same-bar sequencing (E2).
   Protected path.
4. **Mnemosyne:** locking/single-writer (E3) — already planned; now it
   has a concrete forcing function.
5. **Screener:** unchanged. It already does the vectorized-reject job
   Jesse's benchmark mode approximates, with better quarantine.
6. **CLAUDE.md additions when E-phases start:** (a) 1m is ground truth;
   derived bars never fetched for trusted runs; (b) parallel workers
   never write records directly — single writer only; (c) vendored
   indicator/metric code enters only with known-answer tests; no Jesse
   import ships in `src/chronos/`.
7. **Nothing in the Moirai plan changes structurally** — Phase M items
   M-a…M-d are additions inside the spec work you were already about to
   do.

---

## 6. Sequencing summary (one glance)

```
NOW ──────────► Gate 0→1 ─────────► post-gate ────────► Stage 2
Phase M                    E1 → E2 → E3 → E4              L
Moirai spec+build          1m     intrabar  parallel      Hermes
 + M-a null gate           truth  fills     (Mnemosyne    (Jesse as
 + M-b trade-shuffle MC                      first!)       reference)
 + M-c pipeline harness
 + M-d cost-stress form
```

Dependencies: E2 needs E1. E3 parallelism needs Mnemosyne hardening.
E4 anytime post-gate. Phase M needs nothing from Jesse's code — only the
four ideas, re-derived under the register.

---

## 7. What this plan deliberately does not do

- No Jesse code dependency ever enters `src/chronos/` (patterns yes,
  imports no). Keeps license surface zero and the register rule intact.
- No GUI, no web server, no live-plugin chase, no 300-indicator port.
- No change to the Stage 0 sequence: the Moirai remains next, exactly as
  `docs/handoffs/2026-07-18-moirai.md` defines it.
- No re-litigation of settled forks (spot-only, Decimal ledger,
  cancel-and-record, screens-as-non-trials). Nothing found in Jesse
  provides a new failure mode against any of them. One partial
  exception worth recording: Jesse's stop-order support is evidence that
  the "no order state between bars" simplification will eventually chafe
  — E2 addresses it without reopening the carry-vs-cancel decision
  (stops live within the decision interval, remainder policy unchanged).

---

*End of plan. Recommended immediate action: proceed with the Moirai
session as already scheduled, with M-a…M-d added to the spec's §6/§7
candidate list. The E-phases become a dated HANDOFF.md entry so the
decision is committed, not chat-resident.*
