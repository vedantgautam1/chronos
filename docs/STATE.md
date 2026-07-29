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

Last updated: 2026-07-29 (Moirai spec approved; build brief written)
Test suite: **152 passing**
Current stage: **Stage 0 — building the instrument. Gauntlet build begins.**

---

## The one-line status

`docs/SPEC_MOIRAI.md` is **approved and final**; D-01 through D-09 are
founder-decided; `MOIRAI_BUILD_BRIEF.md` sequences the build in nine
phases. **Next: Phase 0 (repo housekeeping), then Phase 1 (statistics to
CI).** Build runs on Opus throughout.

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
- **chronos_math_probe.py** — 28 known-answer checks (Lo, Newey-West,
  Politis-Romano, PSR/DSR). Still at repo root; **promotion to
  `tests/statistics/` is Phase 1.**

## In progress

- Nothing mid-edit. Clean stopping point before Phase 0.

## Next task (owns the next Claude Code session)

**Phase 0 of `MOIRAI_BUILD_BRIEF.md`** — documentation only, no `src/`
changes: commit the spec, replace this file, append the D-decisions to
HANDOFF.md, amend CLAUDE.md (add I10/I11; extend protected paths with
`configs/gauntlet/` and `tests/statistics/`), create the directory
skeleton. Then Phase 1: promote the math probe into CI and add the four
JPM known-answer assertions — R1 goes FORMULA-SOURCED → SOURCED.

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
