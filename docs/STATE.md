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

Last updated: 2026-07-30 (Phase 3 — pipeline skeleton, verdict records, G1/G4)
Test suite: **213 passing** (152 + 34 statistics + 27 moirai)
Current stage: **Stage 0 — building the instrument. Gauntlet Phases 0–3 done.**

---

## The one-line status

`docs/SPEC_MOIRAI.md` is **approved and final**; D-01 through D-09 are
founder-decided; `MOIRAI_BUILD_BRIEF.md` sequences the build in nine
phases. Phases 0 (housekeeping), 1 (statistics → CI, R1 SOURCED), 2
(GauntletConfig hashed artifact, I9 enforcement), and 3 (pipeline skeleton,
verdict/outcome records, probes G1/G4) are **done**. **Next: Phase 4a — the
free stages: 4.0 eligibility, 4.3 DSR, 4.4 trade-shuffle.** Build runs on
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
  partial outcomes + `ERRORED` verdict) green. Two throwaway no-op Moirai
  exercise the DAG; deleted in Phase 4a.

## In progress

- Nothing mid-edit. Clean stopping point after Phase 3, before Phase 4a.

## Next task (owns the next Claude Code session)

**Phase 4a of `MOIRAI_BUILD_BRIEF.md`** — the free stages (zero engine runs):
4.0 eligibility & breadth, 4.3 deflated Sharpe at honest N, 4.4 trade-shuffle
Monte Carlo. These share one pattern — read the `BacktestResult`, compute,
compare to a config threshold. Consumes `moirai/statistics.py` (Phase 1) for
4.3 — no reimplementation. Stage 4.0's unsafe-flag path sets
`evidence["terminal_status"] = "NON_PROMOTABLE"` (the Phase 3 terminal-status
signalling mechanism); its breadth gate uses `INSUFFICIENT_BREADTH`. Adds
probe G8 (unsafe non-promotability). **Deletes the Phase 3 no-op Moirai.**
Protected path (`moirai/`) — full diff and founder approval before it lands.

## Blocking / needed

- **Bailey & López de Prado (2014) JPM paper** — R1's primary. The four
  known-answer values are already transcribed into SPEC_MOIRAI §4.3 and
  the brief's Phase 1, so Phase 1 is not blocked on obtaining the PDF;
  the paper is needed to *audit* those values, not to use them.
- **The Phase 6 calibration budget decision** — the spec's compute
  estimate does not account for stage 4.9's ~200 null runs per candidate
  under full-evaluation mode; the gap is roughly three orders of
  magnitude. Phase 5 now measures actual engine throughput and the
  founder picks a resolution (options A/B/C in the brief) before Phase 6
  is scoped. **This is the one genuinely open item in the build.**
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
