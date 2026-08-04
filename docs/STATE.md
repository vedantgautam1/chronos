# STATE.md — Chronos Living Dashboard

**This is the always-current answer to "where are we." Read it first, every
session. Update it last, every session. One page. If it's longer than one
screen, cut history out to HANDOFF.md.**

---

## THE DOCUMENTATION SYSTEM — what each file is for (read this once)

Chronos uses the repo itself as the single source of truth. Nothing is
"decided" until it is committed here — not in a chat, not in anyone's head.
Every session inherits context by reading these files instead of being
re-explained to. The files and their ONE job each:

| File | Its one job | Update rhythm |
|---|---|---|
| `CLAUDE.md` (root) | Rules of engagement — invariants, protected paths, conventions. Every Claude Code session auto-reads it. | Rarely; only when a rule changes. |
| `docs/STATE.md` (this file) | The living dashboard. Where are we: built / in-progress / next / blocked. The FIRST thing any session reads. | End of every session. Always current. Keep it to one page. |
| `HANDOFF.md` (root) | The dated decisions log — the append-only history of WHY things are the way they are. | Append a dated entry for every decision. Never rewrite or delete. |
| `docs/SPEC_*.md` | The specifications — WHAT to build, at full rigor (HEPHAESTUS done; MOIRAI done and approved). | When a component is designed or amended. |
| `MOIRAI_BUILD_BRIEF.md` (root) | The phased build sequence for the gauntlet — the spec is the contract, this is the order. | When a phase's scope changes. |
| `SESSION_FINDINGS.md` (root) | The empirical results — the NUMBERS measured on real project data. | When a new measurement is produced. |
| `docs/calibration/CAL-*.md` | The versioned calibration reports — the measured power curve per config version. | One per activated GauntletConfig. |
| `docs/handoffs/YYYY-MM-DD-*.md` | The full closing handoff for each session — heavy, complete, permanent. The deep context a new chat reads when STATE.md isn't enough. | One per session, at close. Never edited after. |

**The loop that ends re-explaining:**
- *Start a Claude CHAT (thinking/spec):* upload STATE.md + the relevant
  SPEC + HANDOFF.md + task papers → "read these, tell me the weakest part
  of the current state, then begin [task]."
- *Start a Claude CODE session (building):* it auto-reads CLAUDE.md; just
  say what to build. It reads HANDOFF.md itself if it needs the why.
- *End any session:* update STATE.md, append to HANDOFF.md, save the
  closing handoff to docs/handoffs/, commit everything.

**Precedence when documents disagree:** STATE.md and the newest dated
handoff/HANDOFF.md entry win over any older planning document. Older Stage
0/1/2 plans predate recent decisions and are archived, not authoritative.
If you find a contradiction, surface it and argue it — do not silently
follow the stale side.

---

Last updated: 2026-08-04 (Phase 4c session 2 — sub-period 4.8, null benchmark 4.9, descriptive 4.10, probe G7 — Phase 4c COMPLETE)
Test suite: **303 passing** (152 + 51 statistics + 100 moirai)
Current stage: **Stage 0 — building the instrument. Gauntlet Phases 0–4c done; the full eleven-stage pipeline (4.0–4.10) exists.**

---

## The one-line status

`docs/SPEC_MOIRAI.md` is **approved and final**; D-01 through D-09 are
founder-decided; `MOIRAI_BUILD_BRIEF.md` sequences the build in nine
phases. Phases 0 (housekeeping), 1 (statistics → CI, R1 SOURCED), 2
(GauntletConfig hashed artifact, I9 enforcement), 3 (pipeline skeleton,
verdict/outcome records, probes G1/G4), 4a (the free stages 4.0/4.3/4.4,
probe G8), 4b (signal null 4.1, plateau 4.2, N finalization, probe G6), and **4c
(session 1: cost stress 4.5, capacity 4.6, shifted-window 4.7 + the shared re-run
helper; session 2: sub-period 4.8, null benchmark 4.9, descriptive 4.10, probe G7)**
are **done** — the **full eleven-stage pipeline (4.0–4.10) now exists**. **Next: Phase 5
— touchstones, the calibration harness, and throughput measurement.** Build runs on
Opus throughout.

## Scope note — there is no "lite" gauntlet

The 2026-07-28 Moirai-lite / v2 split is **REVERTED** (D-06, founder
decision 2026-07-28, reaffirmed 2026-07-29). The full Moirai — every
stage, the touchstones, the calibration harness, and the published power
curve — is specified and built as **one deliverable**. Rationale: a
gauntlet with unmeasured thresholds is a plausible gate, not an honest
one, and "honest" in Chronos means measured. Any document still
describing a lite v1 is stale; this line wins.

## Built and green

- **Oceanus** — data layer, one door (`get_bars`), 67 tests. Sealed-range
  registry in place (I4 enforceable; **nothing sealed yet**).
- **Hephaestus** — event-driven engine + cost model, 7 invariant probes
  CI-required. Milestone MA-crossover run twice (−15.40% at old costs,
  −9.08% under measured 1 bps costs — trial #285).
- **Mnemosyne (stub)** — append-only JSONL, execution counter, full
  per-bar returns stored (no pre-baked statistics, by design).
- **RunKind machinery** — SEARCH/VERIFICATION on every run;
  `compute_search_n()` derives the DSR's N from the log;
  `register_search()` for sweeps.
- **`src/chronos/moirai/statistics.py`** — the pure-math core (Lo,
  Newey-West, Politis-Romano, PSR/DSR + calibration support), no
  engine/data/I/O imports. Promoted from the probe in Phase 1; pinned by
  **34 CI-required known-answer tests** in `tests/statistics/`, including
  the four JPM (2014) assertions. **R1 SOURCED.** The original
  `chronos_math_probe.py` remains at repo root as a historical artifact,
  unchanged (still runs 28/28 standalone).
- **`GauntletConfig` v001 (I9)** — the judge as a frozen, hashed artifact.
  `configs/gauntlet/v001.json` (all §4 thresholds at §14 provisional
  defaults) + `ACTIVE` pointer; canonical serialization → sha256
  `fd65c274…0a827d`. **Uncalibrated → every verdict stamps `NO_AUTHORITY`**
  until Phase 6 produces `CAL-001.md` (the §5.2 activation guard, working
  as designed). `scripts/moirai_verify.py` renders verdict validity at read
  time; probes G2 (fixed judge) and G3 (visible invalidation) green.
- **Moirai pipeline skeleton (Phase 3)** — the machine that runs tests,
  records everything on every exit path, and is byte-deterministic before any
  real test exists. `moirai/types.py` (`TestOutcome`, `GauntletVerdict`,
  `serialize_verdict`, `verdict_determinism_view`); `moirai/context.py`
  (`GauntletContext`, `ctx.run` — forces explicit `kind=`, stamps
  `gauntlet_config_hash` closing the I9 anchor, holds the post-4.2 SEARCH
  refusal flag); `moirai/pipeline.py` (`Moira` protocol, DAG runner,
  short-circuit + full-eval, five statuses, try/finally on every exit path).
  Un-executed stages recorded `executed=false` (unknown, not passed); verdicts
  stamped `NO_AUTHORITY` until Phase 6. Probes **G1** (verdict determinism,
  cross-process byte-compare) and **G4** (no unlogged judgment, crash persists
  partial outcomes + `ERRORED` verdict) green. Two no-op Moirai kept as
  generic DAG-mechanics test scaffolding (see 4a handoff — brief said delete,
  but test_pipeline.py's probes depend on them).
- **Moirai free stages (Phase 4a)** — the three zero-engine-run gates.
  `moirai/stages/eligibility.py` (4.0 — completeness → unsafe→NON_PROMOTABLE →
  provisional flag → data-quality → breadth→INSUFFICIENT_BREADTH → warn-only
  fragmentation screen with union N); `moirai/stages/deflated_sharpe.py` (4.3 —
  DSR at raw N gated on `dsr.confidence`, N/V from SEARCH records, N̂ evidence
  under the D-08 guard, all math from `statistics.py`); `moirai/stages/
  trade_shuffle.py` (4.4 — p95 shuffled maxDD gate + sequence-luck warn, full
  percentile table, order-invariance/proportional-sizing limitations stamped).
  `moirai/round_trips.py` (shared FIFO round-trip reconstruction). N̂ estimator
  (`effective_trials`, `mean_pairwise_correlation`, `per_bar_sharpe`, sample
  moments) added to `statistics.py` with 10 known-answer tests. Probe **G8**
  (unsafe → NON_PROMOTABLE, zero downstream even in full-eval) green. Milestone
  judged end-to-end: FAIL at 4.3 (DSR 0.349 at honest N=1), authority
  NO_AUTHORITY (see SESSION_FINDINGS).
- **Moirai re-run stages 4.1 + 4.2 (Phase 4b)** — the two stages with genuinely
  new machinery. `moirai/stages/signal_null.py` (4.1 — `SignalCapture` wrapper via
  the real `on_bar` `_DecisionRecorder` pattern, emits no orders; θ̂ =
  mean(s·(fr−fr̄)); stationary-bootstrap null with the D-R5-p block length
  `statistics.block_p_from_returns`; mandatory {p/2, 2p} bracket +
  `fragile_to_block_length`; `ctx.rng` only). `moirai/stages/plateau.py` (4.2 — the
  ONLY stage that spends N: ±1/±2 grid neighbors, reads existing SEARCH neighbors
  free, runs missing ones `kind=SEARCH`, then `ctx.freeze_search()` on every exit;
  branches: flat-plateau PASS, overfit FAIL, `grid_unparseable`,
  `no_neighborhood_defined` PASS, `undeclared_search_breadth` FAIL). 4.3 now stamps
  `n_frozen = ctx.search_frozen`. `run_gauntlet` recomputes the verdict's frozen N
  post-loop and enforces a divergence invariant (verdict N == 4.3's N == post-freeze
  `compute_search_n`, else `VerdictNMismatch`). Candidate re-run bundle
  (`context.Candidate`) carries strategy+base config+hypothesis for re-run stages.
  Probe **G6** (a fragmentation union-N, b SEARCH refused after 4.2, c neighbor
  run ⇒ N+1 ⇒ 4.3 reads FROZEN N ⇒ SR* strictly up) green. Milestone 4.1 and the
  synthetic 4.2→4.3 demo measured (SESSION_FINDINGS). +24 tests → 258.
- **Moirai re-run gates 4.5/4.6/4.7 (Phase 4c session 1)** — the first three re-run
  gates, all sharing ONE helper. `moirai/rerun.py` (`rerun_candidate` → a single
  `kind=VERIFICATION` engine re-run of `ctx.candidate` at a caller-modified RunConfig,
  wall-clock timed; `net_return`/`per_bar_sharpe` from the returns series as-is; raises
  with no candidate; data-supply verbatim with 4.1/4.2). `moirai/stages/cost_stress.py`
  (4.5 — 3 VERIFICATION re-runs at absolute slippage {5,10,25} bps, spread scaled in
  proportion, taker held; NEVER a `cost_summary` rescale — a CI spy proves 3 real
  `ctx.run` calls with distinct config hashes / one data hash; margin criterion active
  under `provisional_cost_constants`; `non_monotone_cost_response` when a dominated
  level fails). `moirai/stages/capacity.py` (4.6 — 10×/100× cash scaled in Decimal;
  Sharpe-degradation floor + remainder-notional fraction via order_id→fill-price
  matching; 100× reporting-only). `moirai/stages/shift.py` (4.7 — ±1/±2-week shifts,
  pass-fraction-of-Sharpe gate on v001 keys; forward guards REFUSE sealed / past-data
  shifts, never clip; spec §4.7 sign-agreement sub-gate built **dormant** — reads
  `shift.min_sign_agree`, absent under v001 so inactive, activated + calibrated at
  v002). Read-only `oceanus.access.available_range` added for the past-data guard (I7).
  Milestone judged end-to-end through 4.0–4.7 in full-eval mode; per-run wall-clock
  measured (SESSION_FINDINGS). +26 tests → 284.
- **Moirai re-run gates 4.8/4.9/4.10 + probe G7 (Phase 4c session 2)** — the pipeline
  completes. `moirai/stages/subperiod.py` (4.8 — 12-month partition, gate (i)
  positive-Sharpe fraction, gate (ii) one-sided HAC t via `statistics.newey_west` at
  m=⌈K^⅓⌉ with {m/2,2m} bracket, gate (iii) window-PnL concentration; K<2 →
  `insufficient_subperiods`; N-laundering warning carried verbatim; **gate (ii) is an
  OPEN/UNRATIFIED methodology decision** — per-window-means as built, pooled-per-bar
  rejected for warmup-seam contamination, quant ratifies at v002/Phase 6).
  `moirai/nulls.py` + `moirai/stages/null_bench.py` (4.9 — `place_null_entries` is
  **price-blind by construction** (no price parameter) and deterministic under
  `ctx.rng`; 200 cadence-matched nulls via the shared helper's strategy/hypothesis
  override, tagged `:null:`; gate = candidate net > the 95th percentile, read as a
  percentile not a fraction). `moirai/stages/descriptive.py` (4.10 — never gates;
  per-year + guarded 200d-MA regime, guarded cross-asset, Lo Eq.22 + naive annualized
  naming their window, Appendix-A metrics). Probe **G7** (`tests/moirai/
  test_seal_respect.py`): a sealed evaluation window → `SealedDataError` propagates
  uncaught → verdict ERRORED (distinct from 4.7's graceful shift refusal). `rerun.py`
  gained keyword-only `strategy`/`hypothesis` overrides for the nulls. Full 11-stage
  checkpoint measured (SESSION_FINDINGS). +19 tests → 303.

## In progress

- Nothing mid-edit. Clean stopping point: Phase 4c complete, before Phase 5.

## Next task (owns the next Claude Code session)

**Phase 5 of `MOIRAI_BUILD_BRIEF.md`** — the touchstones (the regression set, §6), the
calibration harness (§7 — synthetic-path power curve across `calibration.ladder_S`),
and throughput measurement feeding the Phase 6 calibration-budget decision. The full
eleven-stage gauntlet now exists to calibrate. Protected path (`moirai/`,
`configs/gauntlet/`) — full diff and founder approval before it lands.
(feasible); the Phase 5/6 calibration budget should size against that number.

## Blocking / needed

- **Bailey & López de Prado (2014) JPM paper** — R1's primary. The four
  known-answer values are already transcribed into SPEC_MOIRAI §4.3 and
  the brief's Phase 1, so Phase 1 is not blocked on obtaining the PDF;
  the paper is needed to *audit* those values, not to use them.
- **The Phase 6 calibration budget decision** — the spec's compute
  estimate does not account for stage 4.9's ~200 null runs per candidate
  under full-evaluation mode. **Throughput now measured over 207 real
  re-runs (Phase 4c s2): median ≈ 0.566 s/engine-run** (faster than s1's
  1.4 s — the nulls trade at random cadence and run warm). A single 4.9
  (~200 runs) ≈ **1.9 min**; the wall is calibration's nested loop
  (calibration.R=500 × 7 ladder points × ~200 nulls × 0.566 s ≈ **~4.5
  days naive**, down from the ~11-day figure at 1.4 s). Founder picks a
  resolution (options A/B/C in the brief), now sized against 0.566 s,
  before Phase 6 is scoped. **The one genuinely open item in the build.**
- **Stage 4.8 gate (ii) statistical form — OPEN/UNRATIFIED methodology
  decision** (founder 2026-08-04). As built: one-sided HAC t on the K
  per-window mean returns (T=K) — at K≈6 the Newey–West is near-empty. The
  pooled-per-bar alternative is more powered but contaminated by K−1
  warmup-reset seams (splicing artifacts into the autocorrelation), the
  worse failure for this project, so it was NOT defaulted to. The quant
  ratifies the form AND calibrates the threshold at v002/Phase 6; gate (ii)
  is reported but provisional until then (gates (i)/(iii) and the {m/2,2m}
  bracket stand).
- **Every §14 threshold is provisional until Phase 6 calibrates it.** The
  weakest-derived numbers, flagged honestly: `mc_shuffle.ruin_dd 0.40`
  (a placeholder for Themis), `capacity.max_degradation_frac 0.3`,
  `capacity.max_remainder_frac 0.2`, `eligibility.min_round_trips 30`.

## Deferred (deliberately, not forgotten)

- **The Atropos seal** — protocol and sizing proposal land in Phase 8;
  the seal itself is a separate founder act, gated on Phase 6's measured
  power curve (D-02 as amended 2026-07-29). Sealing is one-way.
- **E-phases** (E1 1m ground truth, E2 intrabar fills, E3 Mnemosyne
  hardening + parallelism, E4) — all post-Gate 0→1.
- **Results-viewer UI** — until there are results worth viewing.
- **R2 purged/embargoed CV** — until ML labelling exists (no ML labels at
  Stage 0).
- **Stage 1** — Prometheus debate patterns, Themis veto. Out of scope.

---

## The founder's non-negotiables (for any model reading this)

Blunt feedback, weakest-part-first, no flattery. Confidence tags
[Certain]/[Likely]/[Guessing] on factual claims. Challenge decisions with
a concrete failure mode; don't re-litigate settled forks. The repo is the
single source of truth — nothing is "decided" until committed here.

---

## How to use this system (the loop that ends re-explaining)

**Start a Claude CHAT (thinking/spec):** upload STATE.md + the relevant
SPEC + HANDOFF.md + task papers. First message: "read these, tell me the
weakest part of the current state, then begin [task]."

**Start a Claude CODE session (building):** it auto-reads CLAUDE.md. Just
say what to build. It reads HANDOFF.md itself if it needs the "why."

**End any session:** update THIS file, append a dated entry to HANDOFF.md
for any decision, save the closing handoff to docs/handoffs/YYYY-MM-DD-*.md,
commit all. The next session inherits everything.
