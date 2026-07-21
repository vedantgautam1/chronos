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
| `docs/SPEC_*.md` | The specifications — WHAT to build, at full rigor (HEPHAESTUS done; MOIRAI next). | When a component is designed or amended. |
| `SESSION_FINDINGS.md` (root) | The empirical results — the NUMBERS measured on real project data. | When a new measurement is produced. |
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

Last updated: 2026-07-18 (end of the Oceanus/Hephaestus hardening + R6 session)
Test suite: **152 passing**
Current stage: **Stage 0 — building the instrument. Nearly at Gate 0→1.**

---

## The one-line status

Hephaestus and Oceanus are built and hardened; the trial-ontology, seal,
and five invariant amendments are done and tested; R6 is measured and
closed. **Next: specify and build the Moirai (the validation gauntlet).**

## Built and green

- **Oceanus** — data layer, one door (`get_bars`), 67 tests. Sealed-range
  registry added (I4 now enforceable; nothing sealed yet).
- **Hephaestus** — event-driven engine + cost model, invariant probes in
  CI. Milestone MA-crossover run twice (−15.40% at old costs, −9.08% under
  measured 1bps costs — trial #285).
- **Mnemosyne (stub)** — append-only JSONL, execution counter, full
  per-bar returns stored (no pre-baked stats).
- **RunKind machinery** — SEARCH/VERIFICATION on every run;
  `compute_search_n()` derives the DSR's N from the log;
  `register_search()` for sweeps.
- **chronos_math_probe.py** — 28 known-answer checks (Lo, Newey-West,
  Politis-Romano, PSR/DSR). Not yet promoted to `tests/statistics/`.

## In progress

- Nothing actively mid-edit. Clean stopping point.

## Next task (owns the next chat)

**Specify then build the Moirai.** Full brief:
`docs/handoffs/2026-07-18-moirai.md`. Spec in a Claude chat → approval →
build in Claude Code. Deliverables: `docs/SPEC_MOIRAI.md`,
`MOIRAI_BUILD_BRIEF.md`, then the phased build.

## Blocking / needed before or during that task

- **Bailey & López de Prado (2014) JPM paper** — R1's primary source;
  build phase gates on its worked example. Big Dawg to obtain.
- **Promote chronos_math_probe.py → tests/statistics/** — early build task.
- **Cost-stress form decision** (R6 closure created this): 2×/5× of 1bps
  is weak stress; decide multipliers-on-base vs absolute levels.
- **~12 open threshold decisions** — see the Moirai handoff §8. Protocol:
  propose a default WITH derivation, mark provisional, founder approves.

## Deferred (deliberately, not forgotten)

- Results-viewer UI — until the gauntlet produces results worth viewing
  (revisit after Gate 0→1).
- Drift-neutral slippage re-measurement (mid-price, both book sides) —
  Stage 2, needs live fills.
- Stages 1 (Prometheus/Metis research) and 2 (execution) — not started.
- Multi-symbol Stage 0 — killed: 20 correlated majors ≈ 1.23 independent
  bets. Single-symbol is correct for now.

## Gate 0→1 checklist (when this is all green, Stage 0 is done)

- [ ] All invariant probes green and CI-required (7 numbered probes in
      tests/hephaestus/invariants/ cover the core invariants; I4/I7/I8
      are enforced by tests elsewhere in the suite; I9 is anchor-only,
      enforcement is a Moirai deliverable — note: probe count ≠
      invariant count, do not assume 9 numbered probes).
- [ ] Moirai built; all planned tests implemented.
- [ ] Touchstones return pre-registered verdicts; flipping any fails CI.
- [ ] Every register method (R1,R3,R4,R5) passing known-answer tests in CI
      before it influences any verdict.
- [ ] Milestone runs end-to-end THROUGH the full gauntlet, writing a
      complete immutable record (expected: a logged rejection = success).
- [ ] Detection-floor power curve published.
- [ ] Reproducible from the five coordinates.

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
