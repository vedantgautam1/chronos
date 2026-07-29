# CHRONOS — Moirai Build Brief (`MOIRAI_BUILD_BRIEF.md`)

**Audience:** every Claude Code session that builds the validation gauntlet.
**Contract:** `docs/SPEC_MOIRAI.md`. **This document is the sequence; the spec is
the contract. Where they disagree, the spec wins** — and you stop and flag the
disagreement rather than picking a side.
**Companion pattern:** `HEPHAESTUS_BUILD_BRIEF.md` built the engine in eight
phases with a founder-verifiable checkpoint each. This does the same for the
gauntlet.

> **Model routing for this build: Opus throughout.** Founder decision
> 2026-07-29. Essentially every phase touches `moirai/`, `configs/gauntlet/`,
> or `tests/statistics/` — all protected or authority-bearing paths. There is
> no "mechanical, Sonnet-safe" sub-task in this component. Do not downgrade.

> **Protected-path discipline applies to every phase.** `moirai/`,
> `configs/gauntlet/`, `tests/statistics/`, and everything under
> `tests/hephaestus/invariants/` require a full diff shown to the founder and
> explicit approval before the change lands. Diff first. Wait. Then commit.

---

## 0. Standing rules for every session in this build

These restate CLAUDE.md at the points this build is most likely to violate it.
Read them once; they bind every phase.

1. **The judge exists before the trial.** `GauntletConfig` (Phase 2) lands
   before any Moira (Phase 4). No threshold is ever a numeric literal in gate
   code. Probe G2 greps for exactly this and it is meant to catch you.
2. **`kind=` is explicit at every `ctx.run` call site.** Only stage 4.2 may
   emit `SEARCH`. Everything else is `VERIFICATION`. After 4.2 completes, the
   context refuses `SEARCH` structurally (G6b) — this is not a convention, it
   is a raised exception.
3. **N comes from `compute_search_n()`.** Never from `trial_counter.txt`.
   Never from `len(records)`. Never from a count you maintained yourself.
4. **DSR/PSR consume the NON-annualized Sharpe** at native H1 frequency. `SR*`
   is floored at 0. The JPM known-answer tests exist because every prior model
   instance has tripped on this at least once.
5. **No global RNG.** Every stochastic element draws from the single injected
   `ctx.rng`. `import random` and `np.random.seed` do not appear anywhere in
   `moirai/`. Probe G1 is byte-comparison and it will fail loudly.
6. **Never loosen a test to make it pass.** If a known-answer test disagrees
   with the implementation, the implementation is wrong until proven otherwise
   against the primary source.
7. **Stop-and-flag beats guessing.** If a phase's instructions fork into
   non-equivalent options, present both with their consequences and wait. This
   has been correct every single time it has happened on this project.
8. **"Tests green" ≠ "it works."** Every phase's checkpoint requires running a
   real script and reading real output, not a green pytest line.
9. **Read files fresh before editing.** Never edit from memory of an earlier
   view in the same session.
10. **Never backfill legacy records** (trial_index ≤ 284). They predate the
    `kind` field and the 1 bps cost default. `compute_search_n` already
    excludes them by construction; do not "helpfully" repair them.

---

## PHASE 0 — Decisions of record and repo housekeeping

**Goal:** the repo stops contradicting itself before a single line of gauntlet
code is written. This phase is documentation only — no `src/` changes.

**Do:**

* Commit the approved specification to `docs/SPEC_MOIRAI.md`.
* **Replace `docs/STATE.md`** with the updated version. The current file still
  says "Moirai-lite is the decided v1 gauntlet" and lists the touchstone /
  power-curve machinery as deferred to v2. That is now false. Diff the
  replacement against the live file before committing — do not assume the
  version handed to you is a superset of what is on disk.
* **Append the dated decisions entry to `HANDOFF.md`** (never rewrite; append
  only) recording: the D-06 scope reversion, and D-01 through D-09 as approved
  by the founder on 2026-07-29.
* **Amend `CLAUDE.md`** — three surgical insertions, nothing rewritten:
  - Add **I10 (verdict determinism)** and **I11 (every judgment recorded)** to
    the invariant list, in the exact wording of `SPEC_MOIRAI.md` §1.
  - Extend hard rule 1's protected-path list with `configs/gauntlet/` and
    `tests/statistics/`. (`moirai/` is already listed as "when it exists" — it
    now exists; drop the parenthetical.)
  - Add to the documentation-system section: `docs/calibration/CAL-*.md` (the
    versioned calibration reports) and `docs/promotions/` (promotion
    artifacts).
* Create the empty directory skeleton with `.gitkeep` files so later phases
  never have to guess layout: `src/chronos/moirai/`,
  `src/chronos/moirai/calibration/`, `tests/moirai/`, `tests/statistics/`,
  `configs/gauntlet/`, `docs/calibration/`, `docs/promotions/`.

**Tests:** none (documentation phase). The existing 152 must still pass — if
they don't, something in the housekeeping touched code, which it must not.

**CHECKPOINT:** the founder reads STATE.md and finds no reference to a "lite"
gauntlet anywhere in the repo; `grep -ri "moirai-lite\|moirai lite" .` returns
nothing outside `HANDOFF.md`'s historical entries (which are append-only and
stay).

**Commit:** `docs(moirai): commit spec, record D-01..D-09, retire lite scope`

---

## PHASE 1 — `tests/statistics/` and the JPM known-answers (R1 → SOURCED)

**Goal:** the statistical foundations become CI-required *before* anything has
authority to judge. Nothing downstream is trustworthy until this is green.

**Do:**

* Promote `chronos_math_probe.py` (repo root, 28 known-answer checks) into
  `tests/statistics/` as proper pytest modules. Suggested split — group by
  source, not by convenience: `test_lo_2002.py`, `test_newey_west_1987.py`,
  `test_politis_romano_1994.py`, `test_psr_dsr.py`. Each assertion keeps its
  primary-source citation in a docstring. **The numbers do not change.** If any
  check fails after the port, the port is wrong.
* The *implementations* those tests exercise move into
  `src/chronos/moirai/statistics.py` — a pure-math module with no engine
  imports, no data imports, no I/O. This is the module every Moira calls for
  anything statistical. The root probe script stays where it is as a historical
  artifact; it is no longer the source of truth.
* Add the **four JPM known-answer assertions** from `SPEC_MOIRAI.md` §4.3.
  Paper's worked example: N=100, annual V=0.5 at 250 obs/yr (per-bar
  V = 0.002), T=1250, skew −3, raw kurtosis 10, SR̂ = 2.5/√250 ≈ 0.158114.
  - `SR*` (non-annualized) = **0.1132** (tolerance ±0.0002)
  - `DSR` = **0.9004** (±0.0005)
  - counterfactual N=46, same moments → DSR = **0.9505** (±0.0005)
  - counterfactual N=88, normal returns (skew 0, kurtosis 3) → DSR = **0.9505**
    (±0.0005)
* Add the retained property tests: DSR monotone decreasing in N; `SR*`
  proportional to √V; floor behavior at small N (the TRAP test — an unfloored
  `SR*` passes zero-edge strategies ~99.9% at N=1; assert the floor prevents
  this).
* Wire `tests/statistics/` into CI as a **required** check.

**Tests:** 28 ported checks + 4 JPM assertions + the property tests, all green
in CI, run twice (fresh process the second time) to catch machine dependence.

**CHECKPOINT:** the founder sees 32+ statistics checks green in CI and R1's
register row updated FORMULA-SOURCED → **SOURCED** in `docs/SPEC_MOIRAI.md`
§10. If the JPM assertions do not reproduce the published values, **stop the
build and report** — that is a genuine finding about the implementation, not a
tolerance to widen.

**Commit:** `test(statistics): promote probe to CI, add JPM known-answers (R1 SOURCED)`

---

## PHASE 2 — `GauntletConfig`, hashing, ACTIVE pointer, verify script (I9)

**Goal:** the judge is a hashed artifact before any test exists to be judged by
it. I9 enforcement, which the engine spec deliberately deferred to this
component, lands here.

**Do:**

* `moirai/config.py`: the frozen `GauntletConfig` dataclass per spec §2 —
  `version`, `thresholds`, `pipeline_order`, `full_evaluation_mode`,
  `cost_defaults_version`, `calibration_report`. Canonical serialization
  identical in mechanism to `serialize_result()` (sorted keys, no whitespace,
  Decimals as strings, datetimes ISO) → sha256 = `gauntlet_config_hash`.
* `configs/gauntlet/v001.json` — every threshold key named in spec §4, at the
  provisional defaults listed in §14. Git-tracked, protected path.
* `configs/gauntlet/ACTIVE` — one-line pointer file, git-tracked.
* **The activation guard (§5.2):** loading a config as ACTIVE requires its
  `calibration_report` path to resolve to an existing file. v001 will *fail*
  this check until Phase 6 produces the report — **and that is correct
  behavior.** Until then the gauntlet runs in an explicit, loudly-labelled
  `uncalibrated` mode that stamps `NO_AUTHORITY` into every verdict it writes.
  A verdict written before calibration is a smoke test, not a judgment.
* `scripts/moirai_verify.py`: reads every verdict record, computes validity at
  read time per the §5.3 staleness table, renders stale verdicts as
  `INVALIDATED(<reason>)` with the diff-of-coordinates. Skeleton now; it grows
  as records start existing.
* **Probe G2** (fixed judge): in-memory threshold mutation → hash mismatch →
  refusal to judge. Plus the literal-grep: no numeric literals adjacent to
  comparison operators in gate code outside the config loader.
* **Probe G3** (visible invalidation): write a verdict under v001, activate a
  v002, assert the verify script renders `INVALIDATED(judge_changed)` and the
  original record bytes are untouched.

**Tests:** G2, G3, config round-trip determinism (same config → same hash
across processes), ACTIVE pointer resolution, dangling-calibration-report
refusal.

**CHECKPOINT:** the founder runs `uv run python scripts/moirai_verify.py`, sees
it execute cleanly against an empty verdict set, then hand-edits a threshold in
`v001.json` and watches the hash change and G2 fail as designed.

**Commit:** `feat(moirai): I9 enforcement — hashed config artifact, ACTIVE pointer, verify script`

---

## PHASE 3 — Pipeline skeleton, verdict records, G1 and G4

**Goal:** the machine that runs tests exists, records everything, and is
deterministic — before any actual test exists. Empty pipeline, full rigor.

**Do:**

* `moirai/types.py`: `TestOutcome` and `GauntletVerdict` per spec §2, frozen
  dataclasses, canonical serialization shared with the engine's mechanism.
* `moirai/context.py`: `GauntletContext` — injected `rng`
  (`np.random.Generator`, seeded from `gauntlet_seed`), `store`, `config`, and
  `run`. **`ctx.run` is a thin wrapper over `run_experiment()`** that (a)
  forces explicit `kind=`, (b) stamps `gauntlet_config_hash` into the
  `RunConfig` — closing the I9 anchor the engine left as `None` — and (c) holds
  the post-4.2 SEARCH refusal flag.
* `moirai/pipeline.py`: the `Moira` protocol
  (`evaluate(result, ctx) -> TestOutcome`), the DAG runner with short-circuit
  semantics, `full_evaluation_mode`, the five verdict statuses (`PASS`, `FAIL`,
  `NON_PROMOTABLE`, `INSUFFICIENT_BREADTH`, `ERRORED`), and `cause_of_death`
  writing.
* **Un-executed stages are recorded with `executed: false`** — the record must
  state plainly that downstream verdicts are *unknown*, not passed. This is the
  ordering-artifact resolution from the 2026-07-18 handoff; do not skip it.
* Records append to the existing Mnemosyne stub (`records/runs.jsonl`) with
  `type: "gauntlet_outcome"` and `type: "gauntlet_verdict"`. **No new storage
  machinery** — Mnemosyne hardening is E3, post-gate.
* try/finally on every exit path, exactly as `run_experiment()` does. A crash
  mid-pipeline persists per-stage outcomes plus an `ERRORED` verdict, then
  re-raises.
* Register two trivial no-op Moirai (always-pass, always-fail) purely to
  exercise the DAG. They are deleted in Phase 4a.
* **Probe G1** (I10 verdict determinism): identical inputs + seed, run twice,
  second run in a fresh process → byte-identical serialized verdicts. Copy the
  CI pattern from the engine's determinism probe.
* **Probe G4** (I11 no unlogged judgment): deliberate mid-pipeline crash →
  per-stage outcomes + `ERRORED` verdict persisted, exception re-raised.

**Tests:** G1, G4, DAG ordering matches `config.pipeline_order`, short-circuit
stops execution and marks the rest `executed: false`, full-eval mode runs
everything and produces an ordered failure list.

**CHECKPOINT:** the founder sees a `gauntlet_verdict` record land in
`records/runs.jsonl` from the no-op pipeline, containing all reproducibility
coordinates; then sees a deliberately-crashed run produce an `ERRORED` verdict
with the partial outcomes intact.

**Commit:** `feat(moirai): pipeline DAG, verdict records, determinism and logging probes`

---

## PHASE 4a — The free stages: 4.0 eligibility, 4.3 DSR, 4.4 trade-shuffle

**Goal:** every test that needs zero engine runs. These share one pattern —
read the `BacktestResult`, compute, compare to a config threshold.

**Do:**

* **4.0 Eligibility & breadth** per spec §4.0, checks in order: completeness →
  unsafe flags (→ `NON_PROMOTABLE`, terminal) → `provisional_cost_constants`
  (sets the context flag that makes 4.5 require margin) → data-quality warnings
  into evidence → round-trip count vs `eligibility.min_round_trips` (→
  `INSUFFICIENT_BREADTH`) → search-fragmentation screen (warn-only, stamps
  sibling ids and union N).
* **4.3 Deflated Sharpe at honest N** per spec §4.3. Consumes
  `moirai/statistics.py` from Phase 1 — no reimplementation. Evidence must
  carry: DSR at raw N, DSR at N̂ when estimable (D-08 guard: only when
  M < T/2, else `effective_n: not_estimable`), DSR at union-N if 4.0 flagged
  fragmentation, and V's measurement window alongside the verdict window.
  **The gate is raw N.** N̂ is evidence only.
* **4.4 Trade-shuffle Monte Carlo** per spec §4.4. Two outputs: the p95
  drawdown gate, and the sequence-luck warn flag. Both honest limitations
  stamped into the record — terminal equity is order-invariant (so this test
  contains zero information about returns), and the reconstruction assumes
  proportional sizing.
* **Probe G8** (unsafe non-promotability): unsafe-flagged result →
  `NON_PROMOTABLE` with zero downstream stages executed, regardless of every
  other score.
* Delete the Phase 3 no-op Moirai.

**Tests:** 29-trade fixture → `INSUFFICIENT_BREADTH`; constructed fragmentation
scenario (two hypotheses, adjacent grids, same class) → warning with correct
union N; G8; the hand-built 4-trade shuffle fixture whose distribution is
enumerable exactly (4! = 24 paths, computed by hand — the fixtures tradition
continues); terminal-equity-invariance assertion across all shuffles.

**CHECKPOINT:** the founder feeds the milestone MA-crossover result through
these three stages alone and reads a real DSR at the current honest N, with the
evidence dict showing both the raw-N and effective-N figures.

**Commit:** `feat(moirai): eligibility, deflated Sharpe, trade-shuffle Monte Carlo`

---

## PHASE 4b — Signal null and plateau: 4.1, 4.2, and the finalization of N

**Goal:** the two stages with genuinely new machinery. 4.1 introduces the
signal-capture wrapper; 4.2 is the only stage permitted to spend N, and it
freezes N for the verdict.

**Do:**

* **4.1 Signal-only null gate** per spec §4.1. A `SignalCapture` wrapper
  strategy calls `inner.on_bar(view, ctx)`, records intended direction, emits
  **no orders** — this is the existing `_DecisionRecorder` pattern from the
  invariant probes. **No engine change.** Because no orders are emitted the
  portfolio stays flat throughout, so views assume a flat portfolio: exact for
  portfolio-state-independent strategies, approximate otherwise. Evidence
  stamps `flat_portfolio_assumption: true`. Null distribution via the
  **stationary bootstrap** (Politis–Romano, from Phase 1's module) — not i.i.d.
  resampling. Sensitivity bracket at {p/2, 2p} mandatory in evidence.
* **4.2 Parameter plateau** per spec §4.2. Neighbors already in the store as
  SEARCH records are read free. Neighbors *not* yet run are executed as
  `kind=SEARCH` — **N increases, and that is the point.** Do not optimize this
  away; the spec says so explicitly to stop exactly that.
* **Freeze N after 4.2.** `search_n = compute_search_n(hypothesis_id)` is
  final for the verdict. `ctx.run` refuses `kind=SEARCH` from this point on —
  structurally, as a raised exception, not a comment.
* Grid-geometry parsing of `param_grid_description` is stringly. Add a
  structured `param_grid` sidecar for new searches; accept legacy strings with
  a documented parser; **ambiguous geometry → `executed: true, passed: false`
  with reason `grid_unparseable`.** Never guess the geometry.
* **Probe G6**: (a) fragmentation fixture → union-N warning; (b) SEARCH-kind
  refused by `ctx.run` after stage 4.2; (c) a plateau neighbor run ⇒ N+1 ⇒
  `SR*` strictly up.

**Tests:** G6a/b/c; injected-drift synthetic series → p-value below α at
calibrated power; pure-noise series → empirical rejection rate ≈ α over 200
seeded repetitions (a mini-calibration inside CI, tolerance ±2σ); p-value
invariant to detrending constant; deterministic under fixed seed; synthetic
flat-plateau fixture passes.

**CHECKPOINT:** the founder watches a plateau neighbor run execute, sees
`compute_search_n` increment by exactly 1, and sees 4.3's `SR*` rise as a
direct consequence — the honesty machinery working end to end, visibly.

**Commit:** `feat(moirai): signal-only null gate, parameter plateau, N finalization`

---

## PHASE 4c — The re-run stages: 4.5 through 4.10

**Goal:** every stage that derives a modified `RunConfig` and calls
`ctx.run(..., kind=VERIFICATION)`. One shared pattern, six parameterizations.
Split across two sessions if context degrades — 4.5/4.6/4.7 then 4.8/4.9/4.10.

**Do:**

* **4.5 Cost stress** — absolute levels {5, 10, 25} bps, spread scaled in
  proportion, fees held at the published schedule. Gate at 10 bps. **Three full
  re-runs. Never a rescale of line items — costs are path-dependent** (the
  −8.6% linear prediction vs −9.08% actual re-run is this project's own scar
  tissue). Margin criterion active whenever 4.0 saw
  `provisional_cost_constants`, which at Stage 0 is always. Non-monotone cost
  response → fail with reason `non_monotone_cost_response`.
* **4.6 Capacity** — re-run at 10× and 100× `initial_cash`. Gate at 10×;
  100× reporting-only. Evidence carries the remainder fraction per run.
* **4.7 Shifted-window stability** — window start shifted {−2w, −1w, +1w, +2w},
  length preserved, **never crossing the seal boundary**.
* **4.8 Sub-period stability** — K contiguous non-overlapping year-long
  sub-windows. Three gates: positive-Sharpe fraction, pooled HAC t (Newey–West
  from Phase 1's module, m per D-R4-m, sensitivity bracket at {m/2, 2m}), and
  the max-single-window-PnL-fraction gate. **Carry the N-laundering warning
  comment verbatim from the spec into the module docstring** — the path from
  "walk-forward" to hidden search is exactly one lazy implementation away, and
  that sentence is the guard.
* **4.9 Full-engine null benchmark** — ~200 cadence-matched random strategies
  through the real engine with real costs, hypothesis id
  `<candidate>:null:<i>`. All `VERIFICATION`. Nulls consult only the bar index,
  never prices — zero look-ahead by construction.
* **4.10 Descriptive reporting** — no gates. Regime tables (per-calendar-year,
  above/below 200d MA), the single ETH/USDT cross-asset trace, Lo Eq. 22
  AR(1)-corrected annualization alongside the naive √k version (both labelled
  reporting-only), plus turnover / profit factor / CAGR / Sortino / maxDD.
* **Probe G7** (I4 seal respect): any stage whose window touches a sealed range
  without a token → `SealedDataError` propagates **uncaught** to the verdict
  (`ERRORED`). Never swallowed, never caught-and-continued.

**Tests:** monotone non-increasing net return across cost levels (violations
flagged); the three cost runs carry distinct config hashes and identical data
hashes; `REMAINDER_CANCELLED` events appear as size grows on a constructed
thin-volume fixture; a constructed edge-artifact fixture (one giant trade at
the window edge) fails 4.7; windows partition the research window exactly
(half-open, no overlap, no gap); a one-regime-wonder fixture fails 4.8's gate
(iii); fixed seed → identical null placements; G7.

**CHECKPOINT:** the founder runs the full eleven-stage pipeline against the
milestone MA-crossover on a short window and reads a complete verdict record
with every stage's outcome present.

**Commit:** `feat(moirai): cost stress, capacity, shifted-window, sub-period, null benchmark, descriptive`

---

## PHASE 5 — Touchstones, the calibration harness, and the throughput measurement

**Goal:** the regression set that pins the gauntlet's behavior forever, plus
the machinery that will measure it. **And — before Phase 6 is scoped — the
actual measured cost of a full-window engine run.**

**Do:**

* **Touchstones T-a … T-e** per spec §6, each `build() -> (data, Strategy)`
  deterministic from a seed, each with its immutable pre-registered verdict and
  rationale committed beside the code. CI-required; **any flipped verdict fails
  CI.** Runtime budget for the set: ≤ 10 minutes (T-a/T-b/T-d use short
  synthetic windows).
* **T-e gets special care** — the 280-sweep winner's returns judged at N=1 vs
  honest N, asserting DSR@N=1 > `dsr.confidence` > DSR@N=280. This pins the
  project-defining counterfactual (0.563 vs 0.054 on real data) into CI
  permanently. Note it runs against *legacy* records until Phase 7 re-runs the
  sweep live; mark that dependency in the test docstring.
* **`moirai/calibration/generator.py`** — Oceanus-valid synthetic H1 OHLCV
  frames per spec §7.2. Versioned; the version string enters every calibration
  report and stamps `data_provenance: synthetic:<version>` into every synthetic
  run's warnings.
* **Generator self-test (known-answer):** over 1,000 seeded draws at each
  ladder rung, the realized-Sharpe distribution centers on target S within
  ±0.05 annualized.
* **Structural quarantine** — the harness constructor takes a store path and
  **raises if it resolves inside the production records directory.** Synthetic
  frames enter `run_experiment()` only via the existing `data_root=`/`exchange=`
  test-override parameters, pointed at `records/calibration/`.
* **Probe G5** (calibration quarantine): the harness refuses the production
  store path; a full synthetic ladder leaves the production `trial_counter.txt`
  and every `compute_search_n()` output **byte-identical**.
* **Mode S calibration run** (statistics-level, no engine). Its numbers must
  reproduce the existing probe's Monte Carlo: detection ≈ 0.3% at true S=1.0
  after a 280-wide search (±0.5 pp), ~40–50% pre-registered (±10 pp), floor
  ≈ 2.3 (±0.2). **Divergence means the shipped statistics differ from the
  verified probe — that is a stop-the-build finding, not a tolerance to widen.**
* **THE THROUGHPUT MEASUREMENT (new, and blocking for Phase 6):** benchmark and
  report, in `SESSION_FINDINGS.md`: (a) wall-clock seconds for one full-window
  (~65,000-bar) engine run; (b) wall-clock seconds for one complete
  eleven-stage pipeline evaluation in short-circuit mode; (c) the same in
  full-evaluation mode. **Do not proceed to Phase 6 until these three numbers
  exist and the founder has seen them.** See §"The Phase 6 budget problem"
  below for why.

**Tests:** T-a…T-e return their pre-registered verdicts; G5; generator
self-test; Mode S reconciliation against the probe.

**CHECKPOINT:** the founder reads the Mode S reconciliation (three numbers
matching the probe within tolerance) and the three throughput numbers, and
makes the Phase 6 scoping decision described below.

**Commit:** `feat(moirai): touchstones, calibration generator, quarantine probe, Mode S`

---

## PHASE 6 — Mode E, the calibration report, threshold tuning, activation

**Goal:** the instrument measures itself, publishes its power curve, and only
then acquires authority.

**⚠ THIS PHASE IS NOT FULLY SCOPED. See "The Phase 6 budget problem" below.
The founder makes a scoping decision at the end of Phase 5, and that decision
is appended to `HANDOFF.md` before this phase begins.**

**Do (subject to that decision):**

* `scripts/calibrate_gauntlet.py` — the overnight job.
* **Mode E ladder** per spec §7.3: S ∈ {0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0}
  annualized, R realizations per rung (R = 500 as specified, subject to the
  budget decision), two search postures — pre-registered (N=1) and searched
  (honest N=280). **Both lines are published or the curve lies by omission.**
* The searched posture's compute resolution per spec §7.5: run the search on
  the *screener*, promote only the selected cell to a real engine run. This is
  the one documented place untrusted code participates in calibration; Mode S
  covers the pure-engine counterfactual.
* **What gets measured** (§7.4): full-pipeline pass rate per rung × posture
  (the power curve; at S=0 it *is* the FPR), and per-stage marginal rejection
  rates under full-evaluation mode (the attribution table telling the founder
  which gates bind and which are decorative).
* **One threshold tuning round, documented**, targeting `calib.target_fpr`
  ≤ 0.05 full-pipeline at S=0, searched posture. Resulting power at each rung
  is **accepted and published, not tuned toward.** Stage 0 proves the
  instrument; it does not promise the instrument is sensitive.
* `docs/calibration/CAL-001.md` — config hash, generator version, both curves
  (table + regenerable PNG), FPR, per-stage attribution, runtimes, and the
  machine-readable sidecar JSON the activation protocol checks. Headline
  numbers appended to `SESSION_FINDINGS.md`.
* **Activation:** bump to `configs/gauntlet/v002.json` carrying the tuned
  thresholds and the calibration report path, update `ACTIVE`, re-pin the
  touchstone regression set to the new config, full CI green. The
  `NO_AUTHORITY` stamp from Phase 2 disappears — **this is the moment the
  gauntlet becomes a judge.**

**Tests:** the §5.2 activation guard passes only with a resolving report;
touchstones re-pinned and green under v002; Mode S re-run under v002 still
reconciles.

**CHECKPOINT:** the founder reads the published power curve and can answer, in
one sentence, "what effect size can this instrument detect, and how often does
it cry wolf." If that sentence cannot be spoken from the report, the report is
incomplete.

**Commit:** `feat(moirai): Mode E calibration, published power curve, v002 activation`

---

## PHASE 7 — Live sweep, milestone through the gauntlet, T-e pinned live

**Goal:** the gauntlet judges something real, under live records, and produces
the Gate 0→1 demonstration.

**Do:**

* **Re-run the 280-point sweep under current code** — one `register_search()`
  hypothesis reused across all 280 points, every point `kind=SEARCH`, so
  `compute_search_n` returns a live 280 rather than reading legacy records.
  One hypothesis. Not 280. The 280-near-duplicate-hypotheses pattern is the
  laundering pattern; refuse it if any instruction seems to ask for it.
* Re-pin **T-e against live records** and remove the legacy-dependency note
  from its docstring.
* **Judge the milestone MA-crossover end to end** through the full eleven-stage
  pipeline on the canonical research window, writing a complete immutable
  verdict.
* **Expected outcome: a clean FAIL. That is the success condition, not a
  disappointment.** A logged, complete, invalidatable rejection flowing end to
  end *is* the Gate 0→1 demonstration.
* Demonstrate visible invalidation: bump the config, run
  `scripts/moirai_verify.py`, watch the milestone verdict render
  `INVALIDATED(judge_changed)` with its record bytes untouched.
* Demonstrate I10 cross-process: reproduce the verdict byte-identically from
  (result coordinates, config hash, moirai SHA, seed) in a fresh process.

**Tests:** full CI green; every acceptance criterion in `SPEC_MOIRAI.md` §15
checked off or explicitly deferred with a reason.

**CHECKPOINT:** the founder reads a complete verdict record for the milestone
strategy — cause of death, every executed stage's evidence, every
reproducibility coordinate — and can trace exactly why it died.

**Commit:** `feat(moirai): live sweep, milestone judged end-to-end, Gate 0→1 demonstration`

---

## PHASE 8 — Atropos: proposal, burn ledger, founder checkpoint

**Goal:** the final exam's protocol exists and is ready. **Nothing is sealed
without an explicit founder act.**

**Do:**

* Implement the **burn ledger** — `atropos_ledger` counts exams; exam K applies
  its PSR gate at Bonferroni-adjusted α/K, recorded in the expectation. The
  ledger makes the cost of each exam visible *before* it is spent.
* Implement the **expectation record** (I8 at the finish line): candidate id,
  verdict id, the two gate statistics and their thresholds, and the written
  expectation — committed *before* token construction.
* Implement the exam protocol per spec §8.4: PASS under ACTIVE config → commit
  expectation → one `FinalEvaluationToken` → one `VERIFICATION` run on the
  sealed range → dual gates (PSR(SR*=0) ≥ 0.95 AND HAC t > 1.645) → outcome
  appended.
* Write the **sizing proposal** into `docs/` as a founder-decision artifact:
  the power table, the ~1.6-year / S=2.0 / most-recent-block recommendation,
  and the honest statement of the recent-regime-bias tradeoff.
* **D-02 CHECKPOINT — HARD STOP.** Per the founder's 2026-07-29 amendment: the
  seal is executed only after the Mode E calibration report exists and the
  founder has read the measured end-to-end detection floor. If Phase 6's
  measured floor differs materially from the ~2.3 that the 1.6-year sizing
  assumed, **re-derive the sizing before sealing.** Sealing is one-way. There
  is no unseal method and there never will be.
* Do not call `seal()`. Present the proposal and wait.

**Tests:** ledger arithmetic (K-th exam gets α/K); expectation-before-token
ordering enforced structurally; token construction and use logged with reason.

**CHECKPOINT:** the founder reads the sizing proposal alongside the measured
power curve and makes the seal decision as a separate, deliberate act with
nothing else on the agenda.

**Commit:** `feat(moirai): Atropos protocol, burn ledger, sizing proposal (unsealed)`

---

## The Phase 6 budget problem — the open item this brief will not paper over

**The spec's compute estimate does not account for stage 4.9 under
full-evaluation mode, and the discrepancy is roughly three orders of
magnitude.**

Spec §7.5 estimates the pre-registered Mode E posture at "500 × 7 = 3,500
engine runs ≈ 3–5 laptop hours." That counts one engine run per realization —
the candidate's own run. But:

1. **Stage 4.9 executes ~200 null runs per candidate judged.** Under
   short-circuit semantics only survivors reach 4.9, so at a 5% target FPR the
   S=0 rung adds roughly 0.05 × 500 × 200 = 5,000 null runs. Tolerable.
2. **But §7.4 requires full-evaluation mode for the per-stage attribution
   table** — and full-eval runs *every* stage on *every* realization
   regardless of failure. That is 3,500 × 200 = **700,000 null engine runs**
   for the pre-registered posture alone, before the searched posture is
   considered.
3. **Stages 4.5–4.8 add ~16 further VERIFICATION runs per candidate**, i.e.
   another ~56,000 runs under full-eval.
4. **And the per-run cost is itself unmeasured.** The milestone was ~4,344
   bars; the canonical research window is ~65,000 bars — roughly 15× larger.
   If a full-window run costs even 30 seconds, 3,500 candidate runs alone is
   ~29 hours, not 3–5. The spec's estimate appears to assume a much cheaper
   run than the canonical window implies. *(This is an inference from bar
   counts, not a measurement — which is exactly why Phase 5 now measures it.)*

**None of this breaks the design.** It means the ladder's parameters (R,
`n_nulls` during calibration, synthetic window length, and whether attribution
runs on a subsample) must be set from *measured* throughput rather than the
spec's estimate. Setting them by guess would produce either an infeasible
overnight job or a quietly-truncated calibration whose power curve overstates
what was actually measured — and a power curve that overstates its own basis is
precisely the failure this component exists to prevent.

**Three candidate resolutions, for the founder's Phase 5 checkpoint:**

| Option | Shape | Cost | What it gives up |
|---|---|---|---|
| **A — Split modes** | Headline FPR/power curve from short-circuit mode at full R=500; attribution table from a 50-realization subsample in full-eval mode | Headline cheap; attribution ~1/10 of full-eval | Attribution table has wide error bars; per-stage rates are indicative, not precise |
| **B — Reduce `n_nulls` during calibration** | Calibration runs 4.9 at n_nulls=50 rather than 200, documented in the report | ~4× cheaper on the dominant term | 4.9's calibrated percentile is noisier than production's; the report must say so |
| **C — Shorten the synthetic window** | Calibrate on 2-year synthetic paths rather than full-length | ~3× cheaper per run | The measured floor is the floor *at 2 years*, not at the verdict window — and V shrinks with T, so this biases the measurement. Weakest option; listed for completeness |

**Recommendation: A + B combined, with C rejected.** A and B both degrade
precision in ways the report can state honestly; C degrades *validity* by
measuring the instrument on a window that is not the window it judges on.
Final parameters set from Phase 5's measured throughput, and the chosen option
appended to `HANDOFF.md` before Phase 6 begins.

---

## Session hygiene — how to close every phase

Non-negotiable, per CLAUDE.md's documentation system:

1. Update `docs/STATE.md` — built / in-progress / next / blocked. One page.
2. Append a dated entry to `HANDOFF.md` for every decision made. Append only;
   never rewrite.
3. New measured numbers → `SESSION_FINDINGS.md`.
4. Write the closing handoff to `docs/handoffs/YYYY-MM-DD-moirai-phase-N.md`.
5. Commit everything.

**End a session early — do not push through — if:** context is visibly
degrading (re-asking settled questions, contradicting earlier turns in the same
session), or a protected-path change is pending founder approval, or a phase's
checkpoint has not been demonstrated with real output. A degraded session doing
invariant-touching work is the single highest-risk state this build can be in.

---

*End of brief. The spec is the contract; this is the sequence. Phase 5's
throughput measurement gates Phase 6's scope, and Phase 6's power curve gates
Phase 8's seal — those two dependencies are the load-bearing ones. Everything
else is order of convenience.*
