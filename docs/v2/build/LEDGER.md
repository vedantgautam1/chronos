# LEDGER — estimate vs actual

One row per build. The reviewer fills the "actual" columns when a build merges. Gates G1 and G2 re-size the rest of the ladder from these numbers (BLUEPRINT 2.7).

**How to read it.** *Build ticks* = sessions the builder needed (an M build is allowed 3; a fourth is an overrun and a halt). *Review rounds* = 1 if it passed first time, 2 if it needed a fix. *Lines* = code + tests added. *Halts* = why, in three words.

The estimates are guesses until B01–B05 have run [Guessing]. That is the point of this file.

**† B01 merged on a `CHANGES` verdict, by mistake.** The review (`reviews/B01-r1.md`, 18 Nov)
found `content_hash` non-deterministic on unknown dict keys and set the status to
`changes_requested`; pull request #18 was then merged into `v2-build` at `78298f3` before
the fix. `main` was not touched. The defect is fixed by **B01A**, and until B01A lands,
`v2-build` carries it. Two consequences for the numbers above: B01's "1 review round" is
not a clean pass, so it must not be read as evidence that one round is typical; and
proposal **P-24** (cheap builder, Opus reviewer) has **no usable measurement** from B01 —
the first clean one will be B01A or B02. Recorded rather than tidied away because G1
re-sizes the whole ladder from this table and the gate audit checks every review against
the record (CHRONOS_V2 §14 rule 5: asymmetric findings stated asymmetrically).

| Build | What | Size | Est. build ticks | Est. review rounds | Actual build ticks | Actual review rounds | Lines (code / tests) | Halts | Merged (UTC) |
|---|---|---|---|---|---|---|---|---|---|
| **G0** | **Blueprint approved** | gate | — | — | | | | | |
| B01 | v2 project scaffold, core helpers, automatic tests | M | 2–3 | 1 | 1 | 1 — **CHANGES**, merged anyway † | 131 / 263 | none | 2026-11-18 05:29 † |
| B01A | canonical.py: dict keys validated like values; the fingerprint made deterministic | S | 1–2 | 1 | 1 | 2 — r1 **CHANGES** (tests too weak), r2 **PASS** ‡ | 5 / 91 | none | 2026-11-18 20:30 |
| B02 | The guards: tripwire checks on every pull request, protected values, code owners | M | 2–3 | 1 | | | | | |
| B03 | The loop's decision core: ladder reader, next action, locks | M | 2–3 | 1 | | | | | |
| B04 | The loop's hands: agent definitions, commands, templates | M | 2–3 | 1 | | | | | |
| B05 | The automation's own GitHub identity, GitHub rules, attack tests, first unattended run | M | 2–3 | 1 | | | | | |
| **G1** | **The loop is proven** | gate | — | — | | | | | |
| B06 | Statistics I: the ported core, its known-answer tests, the v1 oracle | M | 2–3 | 1 | | | | | |
| B07 | Statistics II: the 28-check probe as tests, mid-rank counters, the floating-point tie case | M | 2–3 | 1 | | | | | |
| B08 | Statistics III: cross-checks against three outside libraries | S | 1–2 | 1 | | | | | |
| B09 | Trial store I: Postgres harness, migrations, append-only, audit | M | 2–3 | 1 | | | | | |
| B10 | Trial store II: ids, code coordinate, hypotheses, SEARCH/VERIFICATION, honest N | M | 2–3 | 1 | | | | | |
| B11 | Trial store III: returns, trades, data footprint, compare guard, seal audit | M | 2–3 | 1 | | | | | |
| B12 | Data I: bar schema, Parquet store, snapshot hash | M | 2–3 | 1 | | | | | |
| B13 | Data II: validate and clean | M | 2–3 | 1 | | | | | |
| B14 | Data III: the data door, seal guard, footprints | M | 2–3 | 1 | | | | | |
| B15 | Data IV: file loaders (Kraken candles, Bitstamp minute set) | S | 1–2 | 1 | | | | | |
| B16 | Costs: venue fee schedules, cost components, 2x and adverse-funding stress | M | 2–3 | 1 | | | | | |
| B17 | Slippage and spread measurement method | S | 1–2 | 1 | | | | | |
| B18 | Search-fragmentation warning | M | 2–3 | 1 | | | | | |
| B19 | Synthetic world generator | S | 1–2 | 1 | | | | | |
| B20 | Touchstones as pre-registered fixtures (written down, not run) | M | 2–3 | 1 | | | | | |
| B21 | Costs vs typical price moves by holding time (P-12) | S | 1–2 | 1 | | | | | |
| B22 | Sabotage harness: break the code on purpose, count what the tests miss | S | 1–2 | 1 | | | | | |
| **G2** | **Foundations audit (step 2 done)** | gate | — | — | | | | | |
| B23 | Spike prep: pinned NautilusTrader, data in, the v1 test strategy re-implemented | M | 2–3 | 1 | | | | | |
| B24 | Criterion (a): match v1's engine; five fill tests on two engines | M | 2–3 | 1 | | | | | |
| B25 | Criterion (b): our cost model plugged into the engine | S | 1–2 | 1 | | | | | |
| B26 | IBKR paper hookup on the Mac; find the nano contract | S | 1–2 | 1 | | | | | |
| B27 | Criterion (e): paper-trade nano both ways; funding, fees, nano contract bars | M | 2–3 | 1 | | | | | |
| B28 | Criterion (f): broker refuses an oversize order; a second connection can flatten | S | 1–2 | 1 | | | | | |
| B29 | Criterion (d): two strategies, two venues, one node | S | 1–2 | 1 | | | | | |
| B30 | Criterion (c): several days unattended, across a Monday re-login | S | 1–2 | 1 | | | | | |
| B31 | Spike report | S | 1–2 | 1 | | | | | |
| **G3** | **Engine decision** | gate | — | — | | | | | |
| B32 | Server up: hardening, Postgres, backups, UTC | M | 2–3 | 1 | | | | | |
| B33 | Budget guard for paid APIs (V2-D41) | M | 2–3 | 1 | | | | | |
| B34 | Collector frame: schedule, raw files and hashes, gap rows, alerts | M | 2–3 | 1 | | | | | |
| B35 | Kraken trade recorder (V2-D26) | M | 2–3 | 1 | | | | | |
| B36 | Kraken bulk trade files; side check against the recorder | M | 2–3 | 1 | | | | | |
| B37 | News catalog import (AGPL licence), headline recorder | M | 2–3 | 1 | | | | | |
| B38 | GDELT collector | S | 1–2 | 1 | | | | | |
| B39 | Grok/X collector, both scorers logged | M | 2–3 | 1 | | | | | |
| B40 | Macro actuals with release times | S | 1–2 | 1 | | | | | |
| B41 | IBKR spread snapshots (IB Gateway on the server) | M | 2–3 | 1 | | | | | |
| **G4** | **Collection audit** | gate | — | — | | | | | |
| B42 | Load the full Kraken 1-minute history; real-file check of the loader | S | 1–2 | 1 | | | | | |
| B43 | Screening wrapper: five fixes, every variant a counted trial | M | 2–3 | 1 | | | | | |
| B44 | Look-ahead test kit: slice, warm-up, nudge | M | 2–3 | 1 | | | | | |
| B45 | Null benchmark (V2-D21) with its four known-answer tests | M | 2–3 | 1 | | | | | |
| B46 | Sealed-look ledger, series windows; refusal enforced in the database | M | 2–3 | 1 | | | | | |
| B47 | Edge check I: frozen config, data sufficiency, DSR at honest N, cost runs, basis check (P-15) | M | 2–3 | 1 | | | | | |
| B48 | Edge check II: neighbourhood, sealed-look confirm, warnings, one fixture per test | M | 2–3 | 1 | | | | | |
| B49 | Change check with its fixtures (V2-D32) | M | 2–3 | 1 | | | | | |
| B50 | Sizing v0: drawdown budget, ruin formula, bootstrap check | M | 2–3 | 1 | | | | | |
| B51 | Run the touchstones against their pre-registered verdicts | M | 2–3 | 1 | | | | | |
| B52 | Planted-edge calibration: write the criteria (before running) | S | 1–2 | 1 | | | | | |
| B53 | Planted-edge calibration: run it, pick the rule by the written criteria | M | 2–3 | 1 | | | | | |
| B54 | Acceptance report | S | 1–2 | 1 | | | | | |
| **G5** | **Acceptance test passed (protected)** | gate | — | — | | | | | |

**‡ B01A round 2 found no code defect.** Its one blocking finding was a false statement in the build report — an asserted founder approval that had not been given — plus a CHANGELOG bullet contradicting the report. Both corrected in the review round (`reviews/B01A-r2.md`). The round-1 review file was never committed and is present only as a marked reconstruction (`reviews/B01A-r1.md`); the session that wrote it had no push access. **For P-24:** DeepSeek V4 Pro produced correct code and an inaccurate record — two Opus review rounds against one Opus build. First clean measurement; B02–B06 are all specified `model: opus`, so there is no scheduled second one. The round that cost nothing but paperwork is what V2-D51 now prevents.

## Re-sizing log

| Date | Gate | What the numbers said | What changed in the ladder |
|---|---|---|---|
