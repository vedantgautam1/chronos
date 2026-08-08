# CHRONOS — Moirai Specification (`docs/SPEC_MOIRAI.md`)

**Audience:** the implementing developer, the reviewing quant, and every Claude Code
session that builds against this document.
**Scope:** the full validation gauntlet — pipeline, every test, threshold governance
(I9), Touchstones, calibration and the published power curve, and the Atropos
holdout protocol.
**Companion:** `MOIRAI_BUILD_BRIEF.md` (written after founder approval of this spec;
the phased Claude Code build sequence). This document is the contract; the brief is
the sequence. Where they disagree, this spec wins.
**Boundary contract:** `docs/SPEC_HEPHAESTUS.md` §10. The engine is a witness, not a
judge. It hands over a complete, truthful `BacktestResult`; the Moirai judge it.

> **STATUS NOTE (2026-07-28, supersedes the same-day "Moirai-lite" entry):** founder
> decision — the lite/v2 split is REVERTED. The full Moirai is specified and built as
> one deliverable. Rationale recorded in HANDOFF.md: a gauntlet with unmeasured
> thresholds is a plausible gate, not an honest one, and "honest" in Chronos means
> measured. The only element deliberately deferred to an explicit founder checkpoint
> is the irreversible act of sealing Atropos (§8). The Jesse-derived design inputs
> M-a…M-d (`docs/JESSE_INTEGRATION_MASTER_PLAN.md` §4) are folded in as ideas only —
> zero Jesse code, all statistics re-derived under the register.

---

## 0. What this component is, and where the rigor lives

The Moirai are the intellectual core of Chronos: an ordered, short-circuiting
pipeline of tests that a pre-registered strategy must survive before it can be
called anything other than noise. The design target is a high rejection rate — **if
most candidates pass, the gauntlet is broken.**

The engine's hard problem was correctness under self-deception; the gauntlet's hard
problem is **honesty about its own accuracy**. Its rigor is therefore concentrated
in three places:

1. **The honest N** — every statistic that depends on search breadth reads
   `compute_search_n()`, never the audit counter, and the pipeline is designed so
   that no path exists to launder search into pre-registration (§4.0, §4.2, §4.8,
   §11).
2. **The fixed judge (I9)** — every threshold is a named entry in a versioned,
   hashed, protected-path artifact. Changing the judge visibly invalidates every
   verdict the old judge issued (§5).
3. **The measured instrument** — the gauntlet's false-positive rate and detection
   power are *measured* by calibration against known injected effects, published as
   a power curve, and pinned by regression touchstones. A threshold that has not
   been calibrated has no authority (§6, §7).

Everything else in this spec serves those three.

**Fixed context for Stage 0 (settled decisions, do not re-open):** single symbol
BTC/USDT, timeframe H1, spot-only, no shorting, Decimal ledger, cancel-and-record,
next-bar-open fills, cost defaults taker 10 bps / slippage 1 bps (R6-measured) /
half-spread 1 bps. Multi-symbol breadth is a settled dead end for Stage 0 (20
correlated majors ≈ 1.23 independent bets).

---

## 1. Invariants

Inherited invariants this component touches (wording per CLAUDE.md; do not restate
differently in code comments — link here):

- **I3 / I6** — every gauntlet-triggered execution goes through `run_experiment()`
  with an explicit `kind=`; verification re-runs (walk-forward windows, cost stress,
  capacity, shifted-window, null strategies) are `VERIFICATION` and never count
  toward N; plateau neighbor runs are `SEARCH` and always do (§4.2).
- **I4** — the Moirai never read sealed ranges except through the Atropos protocol
  (§8) with a `FinalEvaluationToken`. The gauntlet surfaces `SealedDataError`; it
  never catches and continues past it.
- **I7** — one data door. `moirai/` imports market data exclusively via
  `chronos.oceanus.access.get_bars()` (directly only for signal extraction, §4.1;
  otherwise indirectly via `run_experiment()`). It never imports `ccxt`, never reads
  `data/`, never fetches from the network. Synthetic calibration data enters through
  the marked fixture door (§7.2), never a second data path.
- **I8** — hypothesis precedes results, including the final exam: the Atropos
  expectation is written and committed *before* the seal is opened (§8.4).
- **I9** — the judge is fixed before the trial. Enforcement (previously deferred) is
  defined in §5 and is a build-breaking requirement of this component.

New invariants introduced by this component:

- **I10 — Verdict determinism.** Identical (judged result's five coordinates,
  `gauntlet_config_hash`, `moirai_code_version`, gauntlet seed) → byte-identical
  serialized verdict. Every stochastic element in the gauntlet (stationary
  bootstrap, trade shuffles, null-strategy generation, synthetic paths) draws from
  one injected, seeded RNG. No global `random`/`np.random` calls anywhere in
  `moirai/`. Probe G1 (§9).
- **I11 — Every judgment recorded.** Gauntlet evaluation writes, via the append-only
  store, one outcome record per *executed* stage plus one verdict record, on every
  exit path including crashes (try/finally, exactly as `run_experiment()` does).
  There is no unlogged judgment and no verdict-record mutation. Probe G4 (§9).

Hard rules (register-level, not numbered invariants):

- **Calibration precedes authority.** No `GauntletConfig` version may become the
  active judge without an attached calibration report (§7.5) produced under that
  exact config hash. A threshold that has not been measured cannot reject or promote
  anything. (This is CLAUDE.md rule 6 — "statistical methods enter the core only
  from primary sources with passing known-answer tests" — extended from methods to
  thresholds.)
- **Synthetic never touches production.** The calibration harness structurally
  refuses the production records directory; touchstone/calibration runs can never
  advance the production trial counter or appear in any production
  `compute_search_n()`. Probe G5 (§9).
- **DSR/PSR consume the non-annualized Sharpe** at native bar frequency; `SR*` is
  floored at 0; N comes from `compute_search_n()` (CLAUDE.md rule 7, restated
  because every prior model instance has tripped on it at least once).

---

## 2. Core data types

Final field names are the implementer's call; the *contracts* are not. All types
frozen dataclasses; all serialization via the same canonical mechanism as
`serialize_result()` (sorted keys, no whitespace, Decimals as strings, datetimes as
ISO) so byte-comparison probes work.

```
TestOutcome:                       # per spec §7.1 of the Stage 0 spec, extended
  moira_id       : str             # e.g. "M4.3-dsr" — stable, versioned with the config
  passed         : bool
  score          : float           # the test's headline number (p-value, DSR, percentile…)
  evidence       : dict            # everything needed to audit the score offline:
                                   #   inputs used, intermediate stats, sensitivity brackets
                                   #   (e.g. DSR at raw N and at N-hat; p-value at p/2 and 2p),
                                   #   config keys + values consumed, and any warnings
  executed       : bool            # False iff short-circuited before reaching this stage
  runtime_s      : float

GauntletVerdict:
  verdict_id            : str      # monotonic, derived from store
  judged_run_id         : str      # the candidate's verdict-grade BacktestResult (§3.1)
  hypothesis_id         : str
  status                : PASS | FAIL | NON_PROMOTABLE | INSUFFICIENT_BREADTH | ERRORED
  cause_of_death        : str | None      # first failing moira_id under short-circuit;
                                          # ordered list of all failures under full-eval mode
  outcomes              : tuple[TestOutcome, ...]   # every executed stage, in DAG order
  # Reproducibility coordinates (I10):
  gauntlet_config_hash  : str      # sha256 of the active GauntletConfig (§5)
  moirai_code_version   : str      # git SHA of moirai/ at judgment time (+ -dirty)
  engine_core_version   : str      # copied from the judged result
  data_snapshot_hash    : str      # copied from the judged result
  gauntlet_seed         : int
  search_n              : int      # compute_search_n(hypothesis_id) at final judgment (§4.2)
  effective_n           : float | None    # JPM App. C N-hat, when estimable (§10, R7)
  evaluation_window     : (start, end)    # the window V and every statistic were measured on
  judged_at             : datetime

GauntletConfig:                    # THE judge. One frozen artifact; §5 governs it.
  version               : int      # monotonic; activation protocol in §5.2
  thresholds            : Mapping[str, value]   # every named key in §4's tables
  pipeline_order        : tuple[str, ...]       # moira_ids in execution order
  full_evaluation_mode  : bool = False          # §3.2
  cost_defaults_version : str      # pins the engine CostConfig defaults this judge
                                   # was calibrated against (§5.3 staleness)
  calibration_report    : str      # relative path to the report produced under THIS hash

Moira(Protocol):
  def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome: ...

GauntletContext:                   # injected, never global
  rng          : np.random.Generator     # seeded from gauntlet_seed (I10)
  store        : RecordStore             # production store (reads N, writes outcomes)
  config       : GauntletConfig
  run          : callable                # thin wrapper over run_experiment() that
                                         # forces explicit kind= and stamps
                                         # gauntlet_config_hash into RunConfig (I9 anchor)
```

The verdict and outcome records are appended to the same Mnemosyne stub
(`records/runs.jsonl`) with `type: "gauntlet_outcome"` / `type: "gauntlet_verdict"`.
The store's append-only property is inherited; no new storage machinery is built
here (Mnemosyne hardening is E3, post-gate).

---

## 3. The pipeline DAG

### 3.1 What enters the gauntlet

The gauntlet judges one **verdict-grade run**: a `kind=VERIFICATION` execution of
the already-selected candidate (fixed parameters) over the **canonical research
window** — all available history from 2017-08-17 (BTC/USDT listing) up to the
Atropos seal boundary (§8), under current engine code and measured cost defaults.
The 6-month development window remains available for iteration but is **never
verdict-grade** (D-03). Selection happened before this run, in the search whose
SEARCH-kind records determine N; running the selected cell once more on the full
window is evaluation, not search, hence VERIFICATION.

Window-mismatch note (honest and deliberate): V[{SR_n}] is measured from the search
as it was actually run. If the search window was shorter than the verdict window,
the measured V is *larger* than the verdict window's V (V shrinks with T), which
makes SR* — and therefore the DSR bar — *stricter*. The mismatch is conservative in
the only direction that matters. The evidence dict records both windows.

### 3.2 Order, short-circuiting, cause of death

Execution order (cheapest first, and ordered so that N is final before DSR reads
it):

```
 4.0 Eligibility & breadth            (free — record inspection only)
 4.1 Signal-only null gate            (1 capture pass + bootstrap; seconds)
 4.2 Parameter plateau                (0–K SEARCH runs; FINALIZES N)
 4.3 Deflated Sharpe at honest N      (free math)                 ── the selection-bias gate
 4.4 Trade-shuffle Monte Carlo        (free math; 1,000 shuffles)
 4.5 Cost stress                      (3 VERIFICATION runs)
 4.6 Capacity                         (2 VERIFICATION runs)
 4.7 Shifted-window stability         (4 VERIFICATION runs)
 4.8 Sub-period stability             (6–8 VERIFICATION runs + HAC aggregate)
 4.9 Full-engine null benchmark       (≈200 VERIFICATION runs; the expensive last wall)
 4.10 Descriptive reporting           (no gates — regime, cross-asset, annualization)
 ────────────────────────────────────────────────────────────────
 §8  ATROPOS                          (separate protocol; survivor only; once)
```

**Short-circuit semantics (default):** first failure stops execution of later
stages. `cause_of_death` = that moira_id. **Ordering-artifact resolution** (the
known limitation flagged in the 2026-07-18 handoff §7.1): every *executed* stage's
outcome is recorded regardless, and un-executed stages are recorded with
`executed: false` — so the record states plainly that downstream verdicts are
unknown, not passed. A verdict's cause_of_death is therefore explicitly "the first
failure *in this pipeline order*," and the order itself is part of the hashed
config, so it cannot drift silently.

**Full-evaluation mode** (`full_evaluation_mode: true`): all stages run regardless
of failures; `cause_of_death` becomes the ordered list of all failing stages. Used
for post-mortem analysis and for calibration (per-stage power attribution, §7.4).
Costs more; changes no verdict semantics (a single failure still means FAIL).

**Verdict statuses:** `PASS` (all gates green), `FAIL` (≥1 gate failed),
`NON_PROMOTABLE` (unsafe-flagged input — terminal at stage 4.0, no amount of score
rescues it), `INSUFFICIENT_BREADTH` (stage 4.0 breadth gate — distinct from FAIL
because the candidate wasn't wrong, it was unjudgeable), `ERRORED` (crash; record
persists per I11, then re-raise).

### 3.3 What the gauntlet never does

It never invokes itself (no recursion — `run_experiment()` does not call the
gauntlet; verified in code and preserved). It never modifies engine code, cost
models, or data. It never writes anything except outcome/verdict records. It never
reads sealed data outside §8. Its verdict is **binding**: nothing reaches Atropos,
and nothing is called promotable, without `status: PASS` under the currently active
config hash. There is no founder override of a FAIL — the only lever is changing
the judge, which is a protected-path commit that visibly invalidates every old
verdict (§5). (D-01; this bindingness is itself a founder decision — see §14.)

---

## 4. The Moirai — test roster

Format per test: **Contract · Defends against · Data needs · Kind accounting ·
Threshold keys (all live in `GauntletConfig.thresholds`; every default here is
PROVISIONAL until calibrated per §7 and approved per §14) · Verification · Known
failure modes.**

The Stage 0 spec §7.2 roster maps as follows: vectorized screen and event-driven
baseline are already built (screener/Hephaestus) and sit *before* the gauntlet;
"train/test + walk-forward" → 4.8 (renamed honestly, see there); "cost-sensitivity
2×/5×" → 4.5 (form re-decided per M-d); "parameter robustness/plateau" → 4.2;
"random/null benchmark" → 4.9 (plus the cheap pre-cost variant 4.1, from M-a);
"Monte Carlo resampling" → 4.4 (trade order) and §7 (synthetic paths, promoted to
the calibration machinery); "regime decomposition" → 4.10 (descriptive, deferral
argued there); "Deflated Sharpe" → 4.3; "Atropos" → §8. Nothing from the Stage 0
list is dropped; two things are added (4.6 capacity, 4.7 shifted-window, both from
the 2026-07-18 handoff §7.6, adopted with reasons; cross-asset trace adopted as
descriptive-only in 4.10; breadth gate adopted into 4.0).

---

### 4.0 Eligibility & breadth gate

**Contract.** Pure inspection of the `BacktestResult` and the store. No execution.
Checks, in order: (a) result completeness — five coordinates present, returns
length == bars_processed, hypothesis link present; (b) **unsafe flags** — any
`unsafe_same_bar_fill` warning → verdict `NON_PROMOTABLE` immediately, terminal;
(c) `provisional_cost_constants` warning → sets a context flag requiring 4.5 to
pass *with margin* (its stricter criterion, see 4.5); (d) data-quality warnings
copied into evidence; (e) **breadth** — count of completed round trips over the
research window ≥ `eligibility.min_round_trips`, else `INSUFFICIENT_BREADTH`;
(f) **search-fragmentation screen** — scan the store for sibling hypotheses (same
strategy class, overlapping `param_grid_description` neighborhoods, registered
within `eligibility.fragmentation_window_days`); if found, stamp
`possible_search_fragmentation` into evidence with the sibling ids and the **union
N**, and report DSR additionally at union N in 4.3's evidence. This is a visibility
mechanism, not a hard gate — intent can't be inferred mechanically, but the pattern
that would launder N across families is now on the record where a reviewer sees it.

**Defends against.** Judging garbage; the unsafe research path reaching promotion;
few-trade equity curves whose bar-level Sharpe hides that the whole result is two
lucky trades; the cross-family N-laundering hole identified in this project's own
challenge log.

**Data needs.** `warnings`, `trades`, `hypothesis_id`, store read.

**Kind accounting.** None (no execution).

**Thresholds.** `eligibility.min_round_trips: 30` (derivation: below ~30 completed
trades no per-trade statistic distinguishes skill from a coin at conventional
power; the bar-level statistics downstream don't depend on this — the gate exists
to refuse degenerate curves, not to measure anything. Weakly derived, honestly
flagged as such). `eligibility.fragmentation_window_days: 90`.

**Verification.** Property tests: unsafe-flagged fixture → NON_PROMOTABLE with zero
downstream stages executed (probe G8); constructed fragmentation scenario (two
hypotheses, adjacent grids, same class) → warning present with correct union N
(probe G6); 29-trade fixture → INSUFFICIENT_BREADTH.

**Failure modes.** A fragmentation screen that's too aggressive nags legitimate
re-tests of old ideas — mitigated by the time window and by it being warn-only.

---

### 4.1 Signal-only null gate (M-a; R5)

**Contract.** Does the entry rule beat noise *before costs even enter*? Extract the
candidate's per-bar signal series s_t ∈ {+1, 0} (long/flat — Stage 0 is spot-only;
−1 reserved for later stages) by running a `SignalCapture` wrapper strategy through
`run_experiment()`: the wrapper calls `inner.on_bar(view, ctx)`, records intended
direction, emits **no orders**. The engine's own bounded views, seed, and logging
apply unchanged (this is the `_DecisionRecorder` pattern the invariant probes
already use; **no engine change**). Because no orders are emitted, the portfolio
stays at initial state throughout, so the views the inner strategy sees assume a
flat portfolio — exact for portfolio-state-independent strategies (the MA
milestone is one), an approximation otherwise; evidence stamps
`flat_portfolio_assumption: true` and the limitation is stated, not hidden.

Statistic: with log returns x_t detrended (x_t − x̄), the signal-weighted mean
θ̂ = mean(s_t · (x_{t+1} − x̄)) — signal decided at close(t) is exposed to bar
t+1, matching next-bar-open timing to first order (approximation documented in
evidence). Null distribution: B draws of θ under the **stationary bootstrap**
(Politis–Romano 1994, R5 — *not* i.i.d. resampling; crypto hourly returns are
autocorrelated and the register already knows better), resampling the detrended
returns with block parameter p per D-R5-p, signals held fixed. One-sided p-value =
fraction of bootstrap θ ≥ θ̂.

**Defends against.** Paying for full-pipeline compute on entry rules that are noise
before costs; adopting Jesse's idea while rejecting Jesse's broken i.i.d. null.

**Data needs.** The candidate strategy object + the research window via
`get_bars()` (through the wrapper run); nothing beyond `BacktestResult` fields plus
the capture.

**Kind accounting.** The capture run is `VERIFICATION` (one logged, counted
execution; never toward N).

**Thresholds.** `null_signal.alpha: 0.05` · `null_signal.bootstrap_B: 2000` ·
`null_signal.p_block: per D-R5-p` (§10). Evidence must include the sensitivity
bracket: p-value recomputed at p/2 and 2p; a pass that flips within the bracket is
recorded as `fragile_to_block_length` (warn, not fail — the bracket exists to make
fragility visible).

**Verification.** Known-answer: the resampler is already pinned to Lemma 1's closed
form (probe module, 28/28); add: injected-drift synthetic series with known θ →
p-value below α at calibrated power; pure-noise series → empirical rejection rate ≈
α over 200 seeded repetitions (a mini-calibration inside CI, tolerance ±2σ).
Property: p-value invariant to detrending constant; deterministic under fixed seed
(I10).

**Failure modes.** Timing approximation (close-to-close vs next-open) mis-scores
strategies that live inside the open-close gap — accepted at H1 granularity,
recorded; revisit at E2 (intrabar). State-dependent strategies get an approximate
signal series — flagged, and 4.9 (full-engine null) provides the state-aware
backstop.

---

### 4.2 Parameter plateau — and the finalization of N

**Contract.** The selected parameter point must sit on a broad performance plateau,
not a lonely spike. Take the candidate's immediate neighborhood in parameter space
(axis-aligned ±1 and ±2 grid steps per tunable parameter, per the grid geometry in
`param_grid_description`). For every neighbor **already present in the store as a
SEARCH record of this hypothesis** (the normal case when the candidate came from a
sweep), read its per-bar Sharpe from disk — free. For any neighbor *not* yet run:
running it now is **new search**, executed as `kind=SEARCH` under the same
hypothesis — **N increases, and that is the point.** A "pre-registered single
point" that needs neighbors evaluated to prove its plateau pays for them in N,
exactly as honesty requires; the spec makes this explicit so no future session
"optimizes" it away.

Pass criterion: median neighbor Sharpe ≥ `plateau.median_frac` × candidate Sharpe,
AND no more than `plateau.max_cliff_frac` of neighbors have Sharpe < 0 while the
candidate's is > 0. ("Broad," quantified: the plateau holds if the point is not
better than most of its neighborhood by more than the allowed decay, and the
neighborhood doesn't fall off a cliff.)

**After this stage completes, `search_n = compute_search_n(hypothesis_id)` is
frozen for the verdict.** No stage after 4.2 may execute SEARCH-kind runs; probe
G6b asserts this ordering structurally (the context's `run` wrapper refuses
`kind=SEARCH` once the pipeline has passed 4.2).

**Defends against.** Curve-fitting to a lucky grid point; the subtle inverse
laundering where a plateau check is done "informally" (unlogged neighbor evals that
never enter N).

**Data needs.** `hypothesis.param_grid_description`, store SEARCH records; possibly
new SEARCH runs via ctx.run.

**Kind accounting.** Neighbor evaluations: `SEARCH` (count toward N). This is the
only stage permitted to add SEARCH runs.

**Thresholds.** `plateau.median_frac: 0.5` · `plateau.max_cliff_frac: 0.25` ·
`plateau.neighborhood_steps: 2` (all provisional; calibrated in §7 — the ladder's
injected-edge strategies must pass this stage at target power, the overfit
touchstone must fail it).

**Verification.** Property: adding a neighbor run changes `search_n` by exactly 1
and changes 4.3's SR* monotonically upward; touchstone (b) (overfit spike) fails
here with the expected cause; a synthetic flat-plateau fixture passes.

**Failure modes.** Grid-geometry parsing of `param_grid_description` is stringly —
mitigation: `register_search()` already persists the description verbatim; the
build adds a structured `param_grid` sidecar for new searches while accepting
legacy strings with a documented parser; ambiguous geometry → stage returns
`executed: true, passed: false` with reason `grid_unparseable` rather than
guessing (stop-and-flag, CLAUDE.md rule 8).

---

### 4.3 Deflated Sharpe Ratio at honest N (R1 — primary source now in hand)

**Contract.** The selection-bias gate. Inputs, all non-annualized at native H1
frequency (Appendix A of the engine spec): candidate per-bar Sharpe SR̂ from the
verdict-grade run's returns (ddof=1); T = number of return observations; skewness
γ̂₃ and raw kurtosis γ̂₄ of those returns (normal ⇒ 3), computed here — the engine
computes no statistics; V[{SR_n}] = variance across the selecting search's per-bar
trial Sharpes read from SEARCH records; N = `search_n` frozen by 4.2.

SR* = √V · ((1−γ)Z⁻¹[1−1/N] + γZ⁻¹[1−1/(Ne)]), **floored at 0** (SR* is negative
at small N; an unfloored DSR passes zero-edge strategies ~99.9% at N=1 — the trap
is real and already demonstrated on this project's data). DSR = PSR(SR*) =
Z[ (SR̂ − SR*)·√(T−1) / √(1 − γ̂₃·SR̂ + ((γ̂₄−1)/4)·SR̂²) ].

Gate: DSR ≥ `dsr.confidence`. Evidence must additionally report: DSR at effective
N̂ (§10/R7) when estimable — the bracket [DSR@N, DSR@N̂], gated on the stricter
raw-N value; DSR at union-N if 4.0 flagged fragmentation; V's measurement window
alongside the verdict window (§3.1); and the annualized-for-humans translation via
R3 (reporting only, after the verdict).

**Defends against.** Selection bias — the test most systems omit, and the entire
reason Mnemosyne counts what it counts. The measured stakes on this repo: the best
cell of the 280-point sweep scores DSR 0.563 treated as pre-registered and 0.054
at its honest N. Ten-x swings on identical returns are what this gate exists to
prevent.

**Data needs.** `returns`, store SEARCH records for V and N.

**Kind accounting.** None (no execution).

**Thresholds.** `dsr.confidence: 0.95` (the paper's own worked convention; the
*meaning* of 0.95 for this pipeline — its realized FPR — is what §7 measures).

**Verification — the JPM known-answer tests (build-phase gate; these numbers were
re-derived independently for this spec and match the published values exactly):**
with the paper's example — N=100, V annual = 0.5 with 250 obs/yr (so per-bar
V = 0.5/250 = 0.002), T=1250, γ̂₃=−3, γ̂₄=10, SR̂ = 2.5/√250 ≈ 0.158114:

- SR* (non-annualized) = **0.1132** (tolerance ±0.0002)
- DSR = **0.9004** (±0.0005) — the paper's rejection at 95%
- counterfactual N=46, same moments → DSR = **0.9505** (±0.0005)
- counterfactual N=88 with normal returns (γ̂₃=0, γ̂₄=3) → DSR = **0.9505** (±0.0005)

Three published values, one source, four assertions (SR* + three DSRs). On green,
R1's register status upgrades FORMULA-SOURCED → **SOURCED** (§10). Property tests
retained from the probe: DSR monotone decreasing in N; SR* ∝ √V; floor behavior at
small N.

**Failure modes.** Feeding annualized Sharpe (trap #4 — Appendix A settles it, the
known-answer test catches it: an annualized feed misses 0.9004 by construction);
reading N from `trial_counter.txt` (trap #1 — structurally impossible here: the
code path takes N from the frozen 4.2 value only); legacy records (≤ #284)
polluting V or N (already excluded by construction in `compute_search_n`; V reader
applies the same kind/hypothesis filter — property-tested).

---

### 4.4 Trade-shuffle Monte Carlo (M-b; Assumptions register)

**Contract.** Was the *path shape* luck? Take the candidate's closed round trips as
per-trade fractional returns; generate `mc_shuffle.n_shuffles` reshufflings of
their order; reconstruct equity paths under proportional reinvestment; extract the
max-drawdown distribution. Two outputs: (i) **risk band** — the 95th-percentile
shuffled maxDD is *the* drawdown expectation stamped into evidence (the realized
single path's maxDD is one draw, not a property); gate: p95 maxDD ≤
`mc_shuffle.ruin_dd`; (ii) **sequence-luck flag** — realized maxDD below the 5th
percentile of the shuffled distribution ⇒ `sequence_luck_warning` (the lived path
was unusually gentle; expect worse), warn-only.

Two honest limitations, stated in the record: terminal equity is order-invariant
under proportional reinvestment (the product of per-trade factors commutes), so
this test contains **zero information about returns** — it is purely a path-risk
diagnostic; and the reconstruction assumes proportional sizing, whereas the actual
ledger sizes orders by strategy logic — the shuffle is a diagnostic approximation,
not accounting-grade simulation (accounting-grade lives in the engine only).

**Defends against.** Under-estimating drawdown risk from one lucky ordering;
promoting a strategy whose realized path happened to dodge its own risk.

**Data needs.** `trades` (round trips reconstructed from fills), initial cash.

**Kind accounting.** None (no execution; pure resampling).

**Thresholds.** `mc_shuffle.n_shuffles: 1000` · `mc_shuffle.ruin_dd: 0.40`
(provisional; a placeholder for Themis's future risk limits — flagged as the
weakest-derived threshold in this spec, see §14) · `mc_shuffle.luck_pct: 0.05`.

**Register status.** No primary academic source in the register for
trade-order-shuffle bands; entered as **A-MC-1 in §16 Assumptions** (engine spec's
register extension): folklore-standard method, verdict participation limited to the
drawdown gate, evidence must carry the full percentile table so any future sourced
method can be back-checked against these records.

**Verification.** Property: terminal equity identical across all shuffles (the
order-invariance assertion doubles as an implementation check); deterministic under
seed; known-answer on a hand-built 4-trade fixture whose shuffle distribution is
enumerable exactly (4! = 24 paths, computed by hand — the fixtures tradition
continues).

---

### 4.5 Cost stress (M-d resolved: absolute levels)

**Contract.** Re-run the candidate (same params, same window) at absolute slippage
levels `cost_stress.levels_bps: [5, 10, 25]` with spread scaled in proportion, fees
held at the published schedule (fees are known; slippage/spread are the R6-space
uncertainty). Three `VERIFICATION` re-runs through `run_experiment()` — **never a
rescale of line items; costs are path-dependent** (the −8.6% linear prediction vs
−9.08% actual re-run is this project's own scar tissue; trap #6).

Gate: at 10 bps — net return > 0 AND per-bar Sharpe > 0. The 5 bps run must also
pass (it is dominated; a violation indicates non-monotone cost response, which is
itself a red flag → fail with reason `non_monotone_cost_response`). The 25 bps run
is reporting-only. **Margin criterion** (active when 4.0 saw
`provisional_cost_constants`, which at Stage 0 is always): the 10 bps gate must
pass with per-bar Sharpe ≥ `cost_stress.margin_sharpe` rather than merely > 0 —
this is the engine spec §10's "provisional-cost results require the
cost-sensitivity test to pass with margin," made concrete.

Form rationale (the genuinely open question the previous session refused to
answer, now decided and argued): multipliers of the measured 1 bps base (2×/5× = 2
and 5 bps) stress almost nothing — the measured impact is ~0.1 bps with 10×
default margin already. Absolute levels anchor to *scenario space*: 10 bps ≈ the
old conservative placeholder ≈ what a thinner venue or stressed book plausibly
costs; 25 bps ≈ regime-break territory. An edge that needs sub-10 bps slippage to
exist is an edge that dies the week liquidity does. R6 stays an assumption (§16);
this gate is how a verdict "reports a range, not a point."

**Data needs.** RunConfig re-derivation; ctx.run.

**Kind accounting.** 3 × `VERIFICATION`.

**Thresholds.** `cost_stress.levels_bps: [5,10,25]` · `cost_stress.gate_level: 10`
· `cost_stress.margin_sharpe: 0.005/bar` (≈ 0.47 annualized; provisional,
calibrated).

**Verification.** Property: monotone non-increasing net return across levels for
the touchstone strategies (violations flagged); the three runs' records carry
distinct config hashes and identical data hashes; determinism per run (engine I5).

---

### 4.6 Capacity

**Contract.** Re-run at 10× and 100× `initial_cash`. The participation cap (5% of
bar volume) either binds or it doesn't: gate — at 10×, per-bar Sharpe degrades by
≤ `capacity.max_degradation_frac` of the base Sharpe and no more than
`capacity.max_remainder_frac` of intended notional is cancelled as remainders; at
100×, reporting-only (the honest expectation is visible degradation — a 100× run
that *doesn't* degrade suggests the cap isn't binding anywhere, which is
informative, not suspicious, at BTC/USDT depth; R6 measured zero liquidity
failures at $90k).

**Defends against.** Fantasy size — an edge that exists only below the
participation cap's radar is real but unfundable; promotion math should know its
capacity ceiling before capital does.

**Kind accounting.** 2 × `VERIFICATION`.

**Thresholds.** `capacity.factors: [10, 100]` · `capacity.max_degradation_frac:
0.3` · `capacity.max_remainder_frac: 0.2` (provisional).

**Verification.** Property: order-event records show REMAINDER_CANCELLED events
appearing as size grows on a constructed thin-volume fixture; evidence carries the
remainder fraction per run.

---

### 4.7 Shifted-window stability

**Contract.** Re-run the identical candidate with the window start shifted by
{−2w, −1w, +1w, +2w} (window length preserved; end shifts accordingly, never
crossing the seal boundary). Gate: the sign of net return agrees with the base run
in ≥ 4 of the 5 runs (base + 4 shifts), and per-bar Sharpe stays within
`shift.sharpe_band` of the base. A result that flips sign because the window moved
a week was an artifact of window edges (one entry/exit landing in or out), not an
edge.

**Kind accounting.** 4 × `VERIFICATION`.

**Thresholds.** `shift.offsets_weeks: [-2,-1,1,2]` · `shift.min_sign_agree: 4/5` ·
`shift.sharpe_band: ±50%` (provisional).

**Verification.** Property: shifted configs hash differently, data hashes differ
(different bar sets), seed constant; a constructed edge-artifact fixture (single
giant trade at the window edge) fails as expected.

---

### 4.8 Sub-period stability ("walk-forward," named honestly)

**Contract.** The Stage 0 spec calls this train/test + walk-forward. For a Stage 0
candidate the parameters are already fixed, so there is nothing to re-fit per
window — true walk-forward (re-optimize each train window, test on the next)
multiplies search and belongs to Stage 1's Prometheus loop. What this stage
honestly is: **out-of-sample-style sub-period stability of a fixed rule.** Split
the research window into K contiguous, non-overlapping year-long sub-windows;
re-run the candidate on each (`VERIFICATION`); aggregate.

Gates: (i) per-bar Sharpe > 0 in ≥ `wf.min_positive_frac` of windows; (ii) the
pooled mean of per-window mean returns is > 0 with one-sided HAC t >
`wf.hac_t_min` at lag m per D-R4-m (R4 — this is where Newey–West is consumed
pre-Atropos), sensitivity bracket at {m/2, 2m} in evidence; (iii) no single window
contributes more than `wf.max_window_pnl_frac` of total net PnL (an edge that is
one window is a regime artifact wearing a full-period costume — this quantifies
4.10's regime concern at the resolution the data actually supports).

**N-laundering warning (binding on all future sessions):** if any future variant
of this stage introduces per-window parameter selection, every inner evaluation is
`SEARCH` under its own registered hypothesis and DSR charges the inner N. Window
boundaries do not reset trial accounting. This sentence exists because the path
from "walk-forward" to hidden search is exactly one lazy implementation away.

**Kind accounting.** K × `VERIFICATION` (K ≈ 6–7 given ~7.4 research years at the
proposed seal).

**Thresholds.** `wf.window_months: 12` · `wf.min_positive_frac: 0.6` ·
`wf.hac_t_min: 1.645` · `wf.max_window_pnl_frac: 0.6` (provisional).

**Verification.** Known-answer: HAC implementation already pinned (NW weights
exact, m=0 reduction, PSD, AR(1) ratio — 28/28 probe suite, promoted to
`tests/statistics/` as an early build task); property: windows partition the
research window exactly (half-open, no overlap, no gap); a constructed
one-regime-wonder fixture fails gate (iii).

---

### 4.9 Full-engine null benchmark (R5-adjacent; touchstone (d) calibrates it)

**Contract.** The expensive last wall: rank the candidate against
`null_bench.n_nulls` cadence-matched random strategies pushed through the *real
engine with real costs*. Null construction: same number of entries as the
candidate, same holding-duration distribution (resampled from the candidate's
realized durations), entry bars placed uniformly at random without overlap, long
side only (spot). Each null runs as `VERIFICATION` under hypothesis id
`<candidate>:null:<i>`. Gate: candidate net return >
`null_bench.percentile`-percentile of the null distribution.

This is the state-aware, cost-aware backstop to 4.1: the signal gate asks "is the
rule noise pre-cost"; this asks "does the rule beat luck *after* the cost
structure, fills, caps, and its own cadence are priced in." A rule whose entire
edge is "trades rarely, so pays little" scores well here only if random
same-cadence trading doesn't.

**Kind accounting.** ≈200 × `VERIFICATION` (the audit counter advances by 200 per
candidate judged; that is honest and intended — the store is append-only JSONL and
lightweight; the runs live in the production store because they are legitimate
verification of a real candidate, tagged by the `:null:` id convention for
filtering).

**Thresholds.** `null_bench.n_nulls: 200` · `null_bench.percentile: 0.95`
(provisional; §7 measures the realized joint FPR of this-plus-4.3, which
overlapping gates make non-obvious — exactly why calibration exists).

**Verification.** Touchstone (d) — the pre-registered random baseline — must land
mid-distribution here (its own percentile ∈ [0.2, 0.8] band across CI runs);
determinism: fixed seed → identical null placements; property: null strategies
carry zero look-ahead by construction (they consult only the bar index, not
prices).

**Failure modes.** Duration-resampling can't match path-dependent exits
(stop-based strategies, post-E2) — noted for the E2 revisit; runtime (~10 min per
candidate) makes this stage the strongest argument for its last-place DAG slot.

---

### 4.10 Descriptive reporting (no gates)

Computed and stamped into evidence; influences no verdict:

- **Regime decomposition — deferred as a gate, with the math (handoff §7.6 item
  answered):** ~8.9 years of BTC/USDT contains on the order of 3–5 regime
  transitions by any defensible labeling. Per-regime Sharpe SE at 1–2 years of
  hourly bars is ~0.7–1.0 annualized (Lo Eq. 9) — wide enough that "the edge is
  regime-dependent" and "the edge is uniform" are statistically indistinguishable
  at these sample sizes for any true edge below ~2. A regime *gate* would be
  theater. What ships instead: per-calendar-year and above/below-200d-MA
  performance tables in evidence, human-read. Revisit as a gate when either the
  window doubles or Stage 1 brings cross-sectional breadth.
- **Cross-asset trace (adopted descriptive-only):** the identical rule run once on
  ETH/USDT H1 (`VERIFICATION`), reported, not gated — correlation among majors
  makes a pass weak evidence and a fail weak counter-evidence (the settled
  multi-symbol analysis), but a *sign flip* is worth a human look.
- **Annualized translations (R3):** Lo Eq. 22 AR(1)-corrected annualized Sharpe
  alongside the naive √k version, both labeled reporting-only, computed after the
  verdict. Every annualized figure in any report must name its window (V and the
  bar both depend on it).
- Turnover, profit factor, CAGR, Sortino, maxDD per the Stage 0 Appendix A
  definitions — computed here, since the engine computes nothing.

---

## 5. I9 enforcement — the judge as artifact

### 5.1 The config artifact

`configs/gauntlet/v<NNN>.json` — git-tracked, protected path (CLAUDE.md rule 1
extends to it on creation). Canonical serialization → sha256 =
`gauntlet_config_hash`. The active version is named by
`configs/gauntlet/ACTIVE` (a one-line pointer file, also tracked). Every threshold
key in §4 lives here; nothing threshold-like may be hardcoded in `moirai/` (probe
G2 greps for numeric literals adjacent to comparisons in gate code — crude,
honest, effective).

### 5.2 Activation protocol

A new version activates only by a commit that (a) adds the new artifact, (b)
updates ACTIVE, (c) **attaches the calibration report produced under the new
hash** (§7.5 — "calibration precedes authority"), and (d) passes full CI including
the Touchstone regression set re-pinned to the new config. Absent (c), CI fails by
construction: the touchstone harness reads the report path from the config and
refuses a dangling reference. Threshold changes are therefore expensive on
purpose — the judge cannot be quietly nudged after seeing a result it disliked.

### 5.3 Invalidation and staleness

"Visibly invalidated" (the phrase I9 left undefined) means: verdict records are
never edited or deleted (append-only), but every read path — the report script,
`scripts/moirai_verify.py`, and any future viewer — computes validity at read time
and renders stale verdicts as `INVALIDATED(<reason>)`. A verdict is **valid** iff
all rows below hold:

| Changed since judgment | Verdict status | Reason code |
|---|---|---|
| `gauntlet_config_hash` ≠ ACTIVE's hash | INVALIDATED | judge_changed |
| `moirai_code_version` not current moirai/ SHA | INVALIDATED | judge_code_changed |
| Engine `core_version` newer than judged result's | INVALIDATED | engine_changed |
| Data snapshot for (symbol, timeframe, window) superseded (restatement) | INVALIDATED | data_restated |
| New bars appended beyond the evaluation window | **valid** | — (window is pinned `[start,end)`) |
| Engine CostConfig defaults changed | INVALIDATED | via `cost_defaults_version` in the config → hash change |

`scripts/moirai_verify.py` lists every verdict with validity, reason, and the
diff-of-coordinates — the one-command answer to "which of our conclusions still
stand." Re-judging a strategy after invalidation is a fresh verdict under the new
coordinates; the old record remains as history.

### 5.4 The anchor closes

`ctx.run` stamps `gauntlet_config_hash` into every `RunConfig` it derives, so
every gauntlet-triggered engine record carries the judge that commissioned it —
the I9 anchor field, populated at last. Runs executed outside any gauntlet keep
`None`, which now *means* something: "not commissioned by a judge."

---

## 6. Touchstones — the regression set (Stage 0 spec §6, implemented)

Pinned cases, each `build() -> (data, Strategy)` deterministic from a seed, each
with an immutable pre-registered verdict + rationale committed beside the code.
Required CI on every trusted-core change; **any flipped verdict fails CI.**

| ID | Case (per Stage 0 §6) | Pre-registered verdict | What a flip means |
|---|---|---|---|
| T-a1 / T-a2 (T-a split; see §6 amendment below) | Should-pass canaries: honestly-constructed faint regime edges a correct gauntlet must not reject — **T-a1** (slow, S=3, above the measured ~2.3 floor) and **T-a2** (faster, S=6) | **DEFERRED — `BLOCKED-ON-PHASE-6-CALIBRATION`** (neither PASS nor FAIL; not CI-asserted until Phase-6 calibration pins them) | gauntlet too harsh or broken |
| T-b | Should-die: 8-parameter rule curve-fit to noise in-sample (beautiful IS, garbage OOS) | FAIL, cause ∈ {4.2, 4.3, 4.8} | overfitting gate broken |
| T-c | Should-die: deliberate future leak (unsafe_same_bar_fill fixture — the flag-gated path is the sanctioned way to construct one without touching I1) | NON_PROMOTABLE at 4.0 | the judge stopped reading warnings |
| T-d | Null baseline: seeded random strategy | FAIL; and its 4.9 self-percentile ∈ [0.2, 0.8] | null machinery mis-calibrated |
| T-e | **The laundering demo as regression:** the 280-sweep winner's returns judged at N=1 vs honest N — assert DSR@N=1 (0.563) > DSR@N=280 (0.054) AND DSR@N=280 (0.054) < `dsr.confidence` (0.95) | both inequalities hold | the flagship failure mode has re-entered |

**§6 AMENDMENT (founder decision, 2026-08-06 — recorded, not silent).** T-a is split into
**T-a1 and T-a2**, so the regression set is now **six touchstones (T-a1, T-a2, T-b, T-c, T-d,
T-e)**. Both should-PASS canaries' verdicts are **DEFERRED — `BLOCKED-ON-PHASE-6-CALIBRATION`,
not asserted in CI** — until Phase-6 calibration reconciles the provisional §14 thresholds.

- **T-a1** — a faint, honestly-constructed regime edge (within-regime annualized Sharpe ±3,
  45-day persistence, σ=0.60, MA 270/1080h). Measured: edge-clarity gates 4.1/4.3/4.4/4.5/4.9
  PASS; 4.0 (breadth) and 4.8 (subperiod) FAIL. Certifies detectability at that SPECIFIC point,
  not "the ~2.3 floor."
- **T-a2** — a higher-frequency regime edge (±6, 12-day persistence, MA 72/288h) that clears
  breadth (47 round trips) but trips 4.4 (ruin_dd-vs-σ) and 4.8.

Their verdicts are **neither PASS nor FAIL**: scoping a PASS to the passing gates would rig a
canary that can never fail; calling it FAIL would slander a genuine edge. The construction is
NOT tuned (a-priori SNR rule `L_bars ≥ 8760/S²` for regime timeability; MA timescale rule
slow=half-life, fast=slow/4). See SESSION_FINDINGS 2026-08-06.

**Why deferred — the meta-finding (Phase-6 precondition), as amended by the 2026-08-07
subperiod diagnostic.** Under provisional §14, each constructed should-PASS canary trips one
*real* gate plus a K=3 subperiod (4.8) co-trip. **T-a1** (slow, S=3) trips **4.0** —
`min_round_trips`=30, a deliberate frequency floor (~25 round trips over the 7.4-yr seal
window, still < 30). **T-a2** (faster, S=6) trips **4.4** — `ruin_dd`=0.40 vs σ=0.60,
exposure-dependent, the §14 placeholder.

**Subperiod (4.8) is NOT a reconcile target.** The diagnostic established that both canaries'
4.8 failures at the CI window are a **K=3 low-resolution artifact in gate (iii)**, not a
frequency assumption — 4.8 fails T-a2 at 47 round trips, so it is not a frequency gate. At the
real operating point K≈7: **T-a2 clears 5/5** — fix the *touchstone* (4.8 is not evaluable at
K=3), NOT the gate; loosening the threshold to pass a K=3 artifact would break 4.8 at K≈7
where it correctly discriminates. **T-a1 stays 2/5, unresolved** — an explicit
reclassify-vs-recalibrate call that folds into the open 4.8 gate-(ii) methodology decision,
not a threshold-loosen.

**Not yet proven:** 4.0 and 4.4 at K≈7 are UNTESTED, so the stronger claim — no honest
strategy clears all eleven gates / the gauntlet would reject a genuine slow edge live — rests
only on 4.0 and 4.4 and is not established until the all-eleven-at-K≈7 test runs. Phase-6
**calibrates** `ruin_dd` (4.4), **decides** `min_round_trips` (4.0, a Themis/founder policy
call, not a tuning target), and **runs the all-eleven-K≈7 test** before T-a1/T-a2 can pin.
(The §6 chained-form assertion for T-e — `DSR@N=1 > dsr.confidence > DSR@N=280` — is a
confirmed v002 defect: it requires 0.563 > 0.95, impossible; T-e uses the two-part honest
form, and the T-e table row below is corrected inline.)

T-e deserves the emphasis: it pins *the* project-defining counterfactual (0.563 vs
0.054 on real data) into CI forever. If any change makes the cherry-picked winner
pass at honest N, or fail at N=1, the trial-ontology machinery has been damaged
and the build stops.

Touchstone runs execute against an **isolated store** (see §7.2's same rule); CI
runtime budget for the set: ≤ 10 minutes (T-a/T-b/T-d use short synthetic windows;
the full-window machinery is exercised by the calibration job, not CI).

---

## 7. Calibration — measuring the instrument, publishing the power curve

### 7.1 Two modes, both required

- **Mode S (statistics-level):** inject known effects directly into synthetic
  *returns series* and drive the statistical stages (4.3, 4.1, 4.8's aggregate)
  alone. Validates the wiring against `chronos_math_probe.py` Part 2's existing
  Monte Carlo (whose machinery this is — pointed at the shipped code instead of
  scratch reimplementations). Fast (no engine); its numbers must reproduce the
  probe's: detection ≈ 0.3% at true S=1.0 after a 280-wide search, ~40–50%
  pre-registered, floor ≈ 2.3 — tolerances ±0.5 pp, ±10 pp, ±0.2 respectively.
  Divergence means the shipped statistics differ from the verified probe.
- **Mode E (end-to-end):** synthetic *candles* through the real engine — real
  costs, fills, caps — judged by the real full pipeline. This is the true
  detection floor of the instrument as built, and the published curve.

### 7.2 The synthetic-candle generator (M-c, the fixture door)

An `moirai/calibration/` module generating Oceanus-*valid* H1 OHLCV frames
(positive prices, low ≤ open/close ≤ high, tz-aware UTC, volume from the empirical
BTC/USDT volume distribution): geometric path with per-bar drift μ set so the
annualized Sharpe of log returns equals the target S at volatility σ =
`calib.ann_vol` (default 0.60, the measured project figure), OHLC synthesized by a
seeded intra-bar bridge. Generator is versioned; its version string enters every
calibration report and every synthetic run's warnings as
`data_provenance: synthetic:<version>`.

**Structural quarantine (I7 + "synthetic never touches production"):** synthetic
frames enter `run_experiment()` only through the existing test-override parameters
(`data_root=`/`exchange=`), pointed at a **calibration store**
(`records/calibration/`, gitignored like all records). The harness constructor
takes the store path and **raises if it resolves inside the production records
directory** — probe G5 asserts both the refusal and that a full calibration ladder
leaves the production `trial_counter.txt` and `compute_search_n()` outputs
byte-identical. Generator self-test (known-answer): over 1,000 seeded draws at
each ladder rung, the realized-Sharpe distribution centers on target S within
±0.05 annualized.

### 7.3 The ladder

`calib.effect_ladder: S ∈ {0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0}` annualized ·
`calib.realizations: 500` seeded paths per rung · two search postures per rung:
**pre-registered** (the capturing strategy's params fixed a priori; N=1) and
**searched** (the standard 280-point grid run per path, best cell judged; honest
N=280) — because the floor is a function of search count, not estimator quality,
and the published curve must show both lines or it lies by omission.

### 7.4 What gets measured

Per rung × posture: full-pipeline pass rate (the power curve; at S=0 it *is* the
FPR), and — under full-evaluation mode — per-stage marginal rejection rates (which
gate kills what, at which effect size: the attribution table that tells the
founder which thresholds bind and which are decorative). Thresholds are then tuned
(one round, documented) to hit `calib.target_fpr: ≤ 0.05` full-pipeline at S=0,
searched posture; resulting power at each rung is *accepted and published*, not
tuned toward — Stage 0 proves the instrument; it does not promise the instrument
is sensitive.

### 7.5 The report — a versioned artifact

`docs/calibration/CAL-<config_version>.md`: config hash, generator version, both
curves (table + rendered PNG regenerable from committed arrays' script), FPR,
per-stage attribution, runtimes, and the machine-readable sidecar JSON the
activation protocol (§5.2) checks. Headline numbers additionally appended to
`SESSION_FINDINGS.md` (its one job: measured numbers). Compute budget: Mode S
minutes; Mode E ≈ 500 × 7 × 2 postures — the searched posture dominates (280
engine runs per realization is ~2.3M runs, which is **not** feasible overnight;
resolution: searched-posture Mode E runs the search on the *screener* (untrusted,
but calibration measures the pipeline's response to a selection process, and the
selection process in production also begins at the screener) with only the
selected cell promoted to a real engine run — documented as the one place
untrusted code participates in calibration, with Mode S covering the pure-engine
counterfactual. Pre-registered posture: 500 × 7 = 3,500 engine runs ≈ 3–5 laptop
hours. Overnight job: `scripts/calibrate_gauntlet.py`).

### 7.6 Recalibration rule

Any config version bump, engine `core_version` change touching costs/fills, or
generator version bump ⇒ the attached report is stale ⇒ §5.2 blocks activation
until re-run. CI runs Mode S only (fast); Mode E is the manual overnight gate.

---

## 8. Atropos — the sealed holdout protocol

### 8.1 What it is, and is not

The one-shot final exam on data nothing has seen — not the Touchstones (which
measure the *instrument* on synthetic data, repeatably), not the gauntlet (which
judges on research data, repeatably). Atropos answers exactly one question, once
per candidate: does the passed strategy's edge exist on truly unseen history? The
seal mechanism exists (`oceanus/seal.py`, additive-only, token-gated, tested);
**nothing is sealed yet, and this spec does not seal anything** — it defines the
protocol and the proposal; the founder executes the seal by explicit recorded
decision (D-02).

### 8.2 Sizing (proposal, from the verified power math)

Sealed years for 80% power, one-sided 5% (Lo Eq. 9; frequency cancels;
re-verified for this spec):

| Detectable true annual Sharpe | Sealed years needed | Research years remaining (of ~8.9) |
|---|---|---|
| 1.0 | 6.18 | ~2.7 — starves research |
| 1.5 | 2.75 | ~6.2 |
| **2.0 (proposed)** | **1.55** | **~7.4** |
| 3.0 | 0.69 | ~8.2 |

**Proposed: seal ≈ 1.6 years, powered for S = 2.0.** Honest reading of the
tradeoff: the gauntlet's own measured floor is ≈ 2.3 after a realistic search —
a holdout powered for S = 1.0 would be sized to confirm strategies the gauntlet
cannot deliver in the first place. Sizing the exam to the instrument's actual
sensitivity is coherence, not compromise. If Stage 1 lowers the floor (more
families, less search per family), the *next* seal — sealing is additive; a
second, later range can extend the exam — can be sized then.

### 8.3 Location (proposal)

The most recent contiguous block, ending at the last fully-closed month before
seal date. For: closest to the deployment distribution; unambiguous boundary;
research window stays contiguous. Against (stated, accepted): recent-regime bias —
a candidate tuned on 2017–2024 takes its exam on 2025–2026 conditions, which is
exactly the deployment question. Alternative (two half-size blocks) rejected for
Stage 0: complexity without power gain at one symbol.

### 8.4 The exam protocol

1. Candidate holds `PASS` under the ACTIVE config (binding, §3.3).
2. **Pre-registration (I8 at the finish line):** an Atropos expectation record —
   candidate id, verdict id, the two gate statistics and their thresholds, and the
   written expectation — is committed *before* token construction.
3. One `FinalEvaluationToken(reason=f"{hypothesis_id}/{verdict_id} final exam")`;
   construction and use are logged by the registry (built behavior).
4. One `VERIFICATION` run on the sealed range. Gates (dual, per the probe's
   detection-floor machinery): **PSR(SR* = 0) ≥ 0.95** (N=1 on the holdout — the
   candidate is fixed; SR* floors to 0) AND **HAC t > 1.645** (R4, m per D-R4-m).
5. Outcome appended; PASS ⇒ the Stage 0 promotion artifact (§12); FAIL ⇒ the
   strategy is dead *and the holdout is burned for that hypothesis family*.

### 8.5 The burn ledger (the detail most shops omit)

Every exam sees the holdout. K exams are K trials against the same data; the
K-th candidate's exam faces a multiple-testing problem the first didn't. Rule:
the registry-adjacent `atropos_ledger` counts exams; exam K applies its PSR gate
at Bonferroni-adjusted α/K (K=1: 0.05; K=2: 0.025; …), recorded in the
expectation. When cumulative K makes the exam's power collapse below usefulness
(tracked in the ledger against the power table), the honest options are: seal an
extension range, or stop promoting from families that have burned exams. The
ledger makes the cost of each exam visible *before* it is spent.

---

## 9. The gauntlet's own trust suite (probes; CI-required on `moirai/`)

| # | Probe | Asserts |
|---|---|---|
| G1 | Verdict determinism (I10) | identical inputs + seed, twice, fresh process second time (CI pattern copied from the engine suite) → byte-identical serialized verdicts |
| G2 | Fixed judge (I9) | in-memory threshold mutation → hash mismatch → refusal to judge; no numeric gate literals in `moirai/` outside the config loader |
| G3 | Visible invalidation | verdict under v1; activate v2 → verify script renders INVALIDATED(judge_changed); record bytes untouched |
| G4 | No unlogged judgment (I11) | mid-pipeline crash → per-stage outcomes + ERRORED verdict persisted, exception re-raised |
| G5 | Calibration quarantine | harness refuses production store path; full synthetic ladder leaves production counter + every `compute_search_n` byte-identical |
| G6 | N-honesty | (a) fragmentation fixture → union-N warning; (b) SEARCH-kind refused by ctx.run after stage 4.2; (c) plateau neighbor run ⇒ N+1 ⇒ SR* strictly up |
| G7 | Seal respect (I4) | any stage window touching a sealed range without token → SealedDataError propagates uncaught to the verdict (ERRORED), never swallowed |
| G8 | Unsafe non-promotability | unsafe-flagged result → NON_PROMOTABLE with zero downstream execution, regardless of every score |

Plus the JPM known-answer suite (§4.3) and the promoted
`tests/statistics/` module (the 28 probe checks, first build task) — all
CI-required before any verdict has authority (§1 hard rule).

---

## 10. Register wiring

| Register | Consumed by | Status / action |
|---|---|---|
| **R1** DSR/PSR (Bailey & López de Prado 2014, JPM 40(5) — *primary now in hand*) | 4.3; §8.4 (PSR arm) | **SOURCED** (2026-07-29, Phase 1) — the four §4.3 JPM known-answer assertions pass in CI (`tests/statistics/test_psr_dsr.py`). Build gate cleared. |
| **R3** Lo 2002 | 4.10 reporting; §8.2 sizing | SOURCED (Tables 1 & 2 pinned) |
| **R4** Newey–West 1987 | 4.8 gate (ii); §8.4 (t arm) | SOURCED structurally. **D-R4-m (documented decision, the paper gives none):** m = ⌈T^⅓⌉; evidence brackets at {m/2, 2m}; provisional. |
| **R5** Politis–Romano 1994 | 4.1 bootstrap; (4.9's permutation is design-adjacent, not a bootstrap — no R5 claim) | SOURCED (Lemma 1 pinned). **D-R5-p (documented decision, per the paper's own §5 procedure):** mean block 1/p = smallest lag L at which the research-window returns' sample autocorrelations sit inside the two-sided 95% band for 5 consecutive lags (floor 1, cap T/50), recomputed per evaluation window; evidence brackets at {p/2, 2p}; provisional. |
| **R6** slippage (Assumption) | 4.5's absolute ladder is the range-reporting mechanism | remains §16; drift-neutral re-measurement stays Stage 2 |
| **R7** effective trials (was: demoted, not closed) | 4.3 evidence bracket | **Partial promotion available:** JPM Appendix C gives N̂ = ρ̂ + (1−ρ̂)·M from the average pairwise correlation of trial returns. Guard (the paper's own warning): compute only when M < T/2 (280 < 2,172 ✓ for the standard sweep), else record `effective_n: not_estimable`. Gate stays on raw N (strictly conservative, since N̂ ≤ M); the bracket satisfies the range rule with a sourced formula for the first time. Founder sign-off to move R7 → §15 with this scope note (D-08). |
| **A-MC-1** trade-shuffle bands (new Assumption) | 4.4 | folklore-standard; drawdown gate only; full percentile evidence retained for future back-checking |
| R2 purged CV | — | unchanged, deferred until ML labeling (no ML labels at Stage 0) |

**Search-budget note (from the JPM paper's stopping-rule section, adopted as
culture, not code):** the 1/e rule — sample ~37% of the theoretically-justified
grid, then stop at the first configuration beating all previous — is recorded here
as the recommended search discipline, because every trial permanently raises the
bar the survivor must clear. The enforcement mechanism is not a hard cap; it is
that `param_grid_description` pre-registers the grid, 4.0 flags fragmentation, and
4.3 charges every point. Searching less buys power that no estimator can (D-09).

---

## 11. Failure modes & guards (component-level)

| Failure mode | How it bites | Guard |
|---|---|---|
| Threshold tuned after seeing a result | the judge bends to the contestant | I9 artifact + activation-requires-calibration (§5.2) + G2 |
| cause_of_death read as "the only problem" | ordering artifact mistaken for diagnosis | executed-flag semantics (§3.2) + full-eval mode |
| Search laundered via plateau / walk-forward / fragmentation | N understated → DSR inflated | 4.2 SEARCH accounting + post-4.2 SEARCH refusal (G6b) + 4.8 warning-clause + 4.0 fragmentation screen + T-e forever in CI |
| Annualized Sharpe fed to DSR/PSR | silently wrong by √8760 | Appendix-A rule + JPM known-answers catch it numerically |
| Unfloored SR* at small N | zero-edge passes ~99.9% | floor in code + probe TRAP test + T-d |
| Synthetic data leaks into production accounting | calibration inflates real N / counter | structural store refusal + G5 |
| Verdicts quietly outlive their assumptions | stale conclusions steer capital | staleness table + verify script + INVALIDATED rendering (§5.3) |
| Cost line-item rescaling passed off as a re-run | path-dependence ignored (the −8.6 % lesson) | 4.5 mandates full re-runs; no rescale path exists |
| Holdout silently re-used | final exam becomes another search | token logging + burn ledger + Bonferroni schedule (§8.5) |
| Bootstrap/HAC tuning (p, m) cherry-picked | significance shopping | documented decisions D-R5-p/D-R4-m + mandatory sensitivity brackets in evidence |
| Regime gate at powerless sample sizes | theater presented as rigor | 4.10 deferral with the math on the record |
| Generator unrealism flatters the power curve | instrument grades its own homework | dual-mode calibration + generator self-test + Mode-S probe reconciliation |
| Parallel workers corrupt the JSONL/counter | I6 violation via duplicate indices | single-process rule until E3 (documented; the store is unchanged Mnemosyne stub) |
| Touchstone mis-construction | the whole gauntlet calibrated to a broken reference | Stage 0 §6's own catch: touchstones are reviewed artifacts; injected strength documented; founder judgment load-bearing (unchanged) |

---

## 12. Promotion — what a PASS produces

A `PASS` verdict yields the **promotion artifact**: one record + one committed
markdown (`docs/promotions/<hypothesis_id>-<verdict_id>.md`) containing the full
verdict, every evidence block, the validity coordinates, the Atropos expectation
template pre-filled, and the founder decision checklist (approve exam → D-02
protocol → exam outcome → only then any Stage-2 conversation). Nothing about
capital is decided by the gauntlet; what the gauntlet decides is that the
*conversation* about capital is permitted. The expected steady state at Stage 0
remains: **a logged rejection is a success** — the milestone MA-crossover flowing
end-to-end into a clean, complete, invalidatable FAIL is the Gate 0→1
demonstration, not a disappointment.

---

## 13. Scope wall (build discipline for every session touching this spec)

Do NOT build here: engine or data-layer changes of any kind (E-phases are
post-gate; the gauntlet judges the engine as it exists); Mnemosyne hardening
(E3); parallel execution; a results viewer/UI (deferred until there are results
worth viewing); Stage-1 items (Prometheus debate patterns, Themis veto);
re-litigation of settled forks (spot-only, Decimal, cancel-and-record,
screens-as-non-trials — recorded as final in D-07); any Jesse import; any
statistic without a register row; multi-symbol anything beyond 4.10's single
descriptive trace.

---

## 14. Founder decisions table

Every entry PROVISIONAL until Big Dawg approves; per protocol each carries its
derivation at its §4/§5/§7/§8 definition. Structural decisions first:

| ID | Decision | Proposed | Where argued |
|---|---|---|---|
| D-01 | Verdict bindingness — no override of FAIL; only judge-change with visible invalidation | ADOPT | §3.3 |
| D-02 | Atropos seal execution — end of Phase B, after the measured power curve, by explicit founder act | ADOPT timing; seal size/location per §8.2–8.3 (S=2.0, ~1.6y, most-recent block) | §8 |
| D-03 | Canonical verdict window = full history minus seal; 6-mo window demoted to dev-only | ADOPT | §3.1 |
| D-04 | Adopt capacity + shifted-window as gates; cross-asset descriptive-only; regime deferred-with-math | ADOPT | §4.6/4.7/4.10 |
| D-05 | Cost-stress form: absolute {5,10,25} bps, gate at 10 with margin | ADOPT | §4.5 |
| D-06 | Full-Moirai-in-one-go supersedes 2026-07-28 lite decision (HANDOFF amendment entry) | ADOPT | header |
| D-07 | Screener counting: screens are non-trials (never promote, never count) — recorded as FINAL, closing the §11 loose end from the engine spec | ADOPT | §13 |
| D-08 | R7 partial promotion via JPM App. C with M < T/2 guard; gate stays raw-N | ADOPT | §10 |
| D-09 | 1/e search-discipline as recorded culture, not hard cap | ADOPT | §10 |

Threshold defaults (all provisional; §7 calibration is the arbiter, this table the
sign-off surface): `eligibility.min_round_trips 30` · `fragmentation_window 90d` ·
`null_signal.alpha 0.05, B 2000` · `plateau.median_frac 0.5, max_cliff 0.25,
steps 2` · `dsr.confidence 0.95` · `mc_shuffle 1000, ruin_dd 0.40 (weakest-derived
number in this spec — it is a placeholder for Themis and says so), luck 0.05` ·
`cost_stress [5,10,25]/gate 10/margin 0.005` · `capacity [10,100]/degr 0.3/rem
0.2` · `shift ±1–2w, 4/5, ±50%` · `wf 12mo, 0.6, t 1.645, window-PnL 0.6` ·
`null_bench 200, p95` · `calib ladder {0,…,3.0}, R 500, target FPR ≤ 5%, vol
0.60` · `D-R4-m ⌈T^⅓⌉` · `D-R5-p autocov procedure`.

---

## 15. Acceptance criteria — definition of done (restores the full Gate 0→1 list)

- [ ] `tests/statistics/` in CI: the 28 probe checks + the four JPM known-answers
      green **before any verdict has authority**.
- [ ] All Moirai 4.0–4.10 implemented per contract; probes G1–G8 green,
      CI-required; every threshold read from the hashed config, none hardcoded.
- [ ] Touchstones T-b…T-e CI-pinned (return pre-registered verdicts; any flip fails CI); T-a1/T-a2 DEFERRED to Phase-6 calibration (BLOCKED-ON-PHASE-6-CALIBRATION), not CI-asserted until they pin.
- [ ] Calibration Modes S and E run; Mode S reconciles with the probe's Monte
      Carlo; report committed; thresholds tuned once to target FPR; **power curve
      published** (docs + SESSION_FINDINGS).
- [ ] The 280-point sweep re-run under current code (one `register_search()`
      hypothesis, `kind=SEARCH`) so `compute_search_n` returns a live 280 and T-e
      runs against live records, not legacy ones.
- [ ] Milestone MA-crossover judged end-to-end through the full pipeline; complete
      immutable verdict written; **expected outcome: a clean FAIL — that is the
      success condition.**
- [ ] `scripts/moirai_verify.py` demonstrates visible invalidation across a config
      bump.
- [ ] Atropos: sizing proposal + burn-ledger implemented; expectation template
      ready; **seal executed only on D-02 approval** (may land after gate).
- [ ] Verdicts reproducible from (result coordinates, config hash, moirai SHA,
      seed) — I10 demonstrated cross-process.
- [ ] HANDOFF.md entries: D-06 scope reversion; every D-decision as approved;
      closing handoff to `docs/handoffs/`.

---

## 16. Build sequence (summary; the brief details it post-approval)

1. Promote `chronos_math_probe.py` → `tests/statistics/` + the JPM known-answers
   (R1 → SOURCED). 2. `GauntletConfig` + hashing + ACTIVE pointer + verify script
   skeleton (I9 first — the judge exists before any test does). 3. Pipeline
   skeleton + verdict/outcome records + G1/G4. 4. Moirai cheapest-first
   (4.0 → 4.9), each with its tests; G2/G6/G7/G8 as their stages land.
   5. Touchstones + calibration harness + generator (G5); Mode S reconciliation.
   6. Mode E overnight run; report; threshold tuning round; activation.
   7. Sweep re-run (live N=280); milestone-through-gauntlet; T-e pinned.
   8. Atropos proposal + ledger; founder checkpoint D-02. Protected paths
   diff-first throughout; Opus-class model for invariant-touching work.

---

*End of specification. Questions the founder must answer before Phase B are the
nine D-decisions in §14; everything else is buildable as written and marked
provisional where calibration will have the final word.*
