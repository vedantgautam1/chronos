# CHRONOS — Moirai Session Handoff: Phase 3

**Date:** 2026-07-30. **Author:** Claude Code session (Opus), with the founder
(non-technical, blunt-feedback preference, confidence tags required).
**Scope:** Phase 3 of `MOIRAI_BUILD_BRIEF.md` — the pipeline skeleton, verdict/
outcome records, and probes G1 (verdict determinism, I10) and G4 (no unlogged
judgment, I11). The spec contract is `docs/SPEC_MOIRAI.md` §2, §3, §9.

The one-sentence summary: **the machine that runs tests now exists, records
everything on every exit path, and is byte-deterministic across a fresh process —
before a single real test exists to run in it.** An empty pipeline at full rigor.

---

## 1. What landed

Three production modules under `src/chronos/moirai/`, one test-only fixtures
module, and one protected-path probe suite.

- **`types.py`** — `TestOutcome` and `GauntletVerdict` (frozen dataclasses,
  spec §2), plus `serialize_verdict()` (the faithful canonical record) and
  `verdict_determinism_view()` (the byte-compare form for G1). Serialization reuses
  `config._canonical` (which is byte-pinned to `run._canonical`), so there is no
  third copy of the mechanism. Status/authority/terminal-signal constants live here
  as module-level strings (no enum — keeps serialization trivially canonical and
  avoids numeric literals the G2 grep would flag).
- **`context.py`** — `GauntletContext` (the injected, never-global state: one seeded
  `rng`, the store, the config + its hash, the gauntlet seed, `is_calibrated`) and
  the `ctx.run` wrapper. `ctx.run` (a) forces explicit `kind=` (keyword-only, no
  default → `TypeError` if omitted), (b) stamps `gauntlet_config_hash` into the
  derived `RunConfig`, closing the I9 anchor the engine left as `None` (§5.4), and
  (c) refuses `kind=SEARCH` once `freeze_search()` has been called
  (`SearchFrozenError`) — the structural mechanism stage 4.2 and probe G6b (Phase 4b)
  will rely on. Two constructors: `make_context()` wires from the ACTIVE pointer via
  `load_active_config` (carrying `is_calibrated`); `context_for_config()` wraps an
  explicit in-test config.
- **`pipeline.py`** — the `Moira` protocol and `run_gauntlet()`, the DAG runner.
  Runs stages in `ctx.config.pipeline_order`; short-circuits on the first non-pass
  unless `full_evaluation_mode`; writes one `gauntlet_outcome` record per EXECUTED
  stage plus exactly one `gauntlet_verdict` record on every exit path including
  crashes (try/finally, mirroring `run_experiment()`); returns the verdict. A crash
  mid-pipeline persists the outcomes gathered so far plus an `ERRORED` verdict
  carrying the error text, then re-raises.
- **`tests/moirai/_noop.py`** — `AlwaysPass` / `AlwaysFail` (the two throwaway
  no-ops, **DELETED IN PHASE 4a**), `CrashMoira`, `NonPromotableMoira`,
  `InsufficientBreadthMoira`, and deterministic fixture builders
  (`build_fixture_result`, `build_config`). Importable by name so G1's subprocess can
  rebuild identical inputs.
- **`tests/moirai/test_pipeline.py`** (protected) — 16 tests: G1 (+ strip-set), G4,
  DAG ordering, missing-moira error, short-circuit placeholders, full-eval failure
  list, both terminal statuses, all-pass, the three `ctx.run` guarantees, both
  authority stamps, and coordinate presence.

**Records:** appended to the existing Mnemosyne stub (`records/runs.jsonl`) with
`type: "gauntlet_outcome"` / `type: "gauntlet_verdict"`. No new storage machinery
(Mnemosyne hardening is E3, post-gate).

Tests: **197 → 213** (+16). Full suite green; no global RNG in `moirai/`.

---

## 2. The two design forks, decided

### 2a. `verdict_determinism_view` strip-set (the single most important decision)

**Stripped** (bookkeeping / wall-clock, legitimately varies between two identical
judgments): `verdict_id`, `judged_at`, and each outcome's `runtime_s`.
**Byte-compared** (everything else): `status`, `cause_of_death`, every outcome's
`passed`/`score`/`evidence`/`executed`, all five judged-result coordinates,
`gauntlet_config_hash`, `moirai_code_version`, `gauntlet_seed`, `search_n`,
`effective_n`, `evaluation_window`, `authority`.

This mirrors the engine's `determinism_view` (strips `run_id`/`trial_index`, keeps
the rest). The one structural difference: the engine's view RECOMPUTES `candidate_n`
at read time because that coordinate isn't in the serialized result; the verdict
instead carries `search_n` as a stored, byte-compared field (finalized by stage 4.2),
so the verdict view recomputes nothing. Strip too much and G1 proves nothing; strip
too little and G1 flakes on wall-clock noise — the three-field set is the honest
minimum, verified by `test_g1_strip_set_is_exactly_three_fields`.

### 2b. Terminal-status signalling

A Moira signals NON_PROMOTABLE / INSUFFICIENT_BREADTH (vs plain FAIL) by stamping
`evidence["terminal_status"] = "<STATUS>"` (constant `types.TERMINAL_STATUS_KEY`).
Chosen over a new `TestOutcome` field/enum because it keeps `TestOutcome` at exactly
the spec §2 shape, rides the already-audited-and-serialized `evidence` channel, and
lets Phase 4a's stage 4.0 set one dict key rather than threading a new type through
every Moira. Runner semantics:

- **NON_PROMOTABLE** is terminal even under `full_evaluation_mode` — zero downstream
  execution (spec §3.2 "terminal at stage 4.0").
- **INSUFFICIENT_BREADTH** is a non-passing outcome: short-circuits in default mode,
  continues under full-eval like any failure, but elevates the verdict status.
- Status precedence over EXECUTED outcomes only: NON_PROMOTABLE > INSUFFICIENT_BREADTH
  > FAIL > PASS. `executed=false` placeholders never count as failures.

**Phase 4a's stage 4.0 depends on this key.** Keep it consistent.

---

## 3. Two notes for the next session (imprecisions in the brief, not bugs)

1. **The brief says to copy the engine determinism probe's "subprocess pattern."**
   The engine's `test_probe_3` actually re-runs IN-PROCESS. The real cross-process
   pattern in the repo is `test_config.py::test_config_hash_cross_process`
   (`subprocess.run([sys.executable, "-c", code])`). G1 copies that — a genuine fresh
   interpreter — which satisfies spec §9's "fresh process second time." Don't go
   looking for a subprocess in probe 3; there isn't one.
2. **The engine-door guard is a naive substring grep** for `_execute`/`_RUN_TOKEN`
   over all of `src/`. The Phase 3 helper `_not_executed` contained `_execute` and
   tripped it; fixed the cause (renamed to `_skipped_outcome`), never the test.
   Future `moirai/` code must avoid those two substrings.

---

## 4. Checkpoint evidence (real records, not just green tests)

Ran the no-op pipeline against a fixture `BacktestResult` into an isolated temp
store and read the actual JSONL. The `gauntlet_verdict` line carried every
reproducibility coordinate: `gauntlet_config_hash`, `moirai_code_version`
(`…-dirty`, honest), `engine_core_version` + `data_snapshot_hash` (copied from the
judged result), `gauntlet_seed`, `search_n=280`, `effective_n`, `evaluation_window`
(ISO pair), `judged_at`, `authority=NO_AUTHORITY`, and both stage outcomes with
`executed=true`. A CrashMoira placed after AlwaysPass produced: the AlwaysPass
`gauntlet_outcome` persisted, exactly one `gauntlet_verdict` with `status=ERRORED`
and `cause_of_death="RuntimeError: gauntlet probe crash"`, the partial outcome intact
inside it, the exception re-raised to the caller, and NO PASS verdict written.

---

## 5. What Phase 3 did NOT do

No real Moira implementations (4.0–4.10 are Phase 4). No calibration. The only
Moirai here are the two throwaway no-ops, deleted in Phase 4a. Every verdict written
before Phase 6 is honestly stamped `NO_AUTHORITY` — a smoke test, not a judgment.

**Next: Phase 4a** — the free stages (4.0 eligibility & breadth, 4.3 deflated Sharpe
at honest N, 4.4 trade-shuffle Monte Carlo), consuming `statistics.py`, adding probe
G8, and deleting the no-op Moirai.
