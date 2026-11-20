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
| B02 | The guards: tripwire checks on every pull request, protected values, code owners | M | 2–3 | 1 | 2 | 2 — r1 **CHANGES** (the gate could not go red), r2 **PASS** ◊ | 2243 / 1747 | none | 2026-11-19 19:26 |
| B03 | The loop's decision core: ladder reader, next action, locks | M | 2–3 | 1 | 2 | 2 — r1 **CHANGES** (the emergency stop could be switched off by the automation), r2 **PASS** ◆ | 1712 / 1954 | none | 2026-11-20 14:51 |
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

**◊ B02: two rounds, one defect, and the defect was real.** Round 1 found the guards job reporting `success` on GitHub while printing "does not pass the guards" — a gate that could not turn red, which is blocking by any reading (`reviews/B02-r1.md` finding 1). Round 2 fixed it, and **the fix was proved on GitHub**: the same workflow watched failing on `305b419` (run `44550344464`) and passing on `f50a1fc` (run `44553126335`), both confirmed against the Actions API by the round-2 reviewer. Round 2 also found and fixed two further guard defects on the builder's own initiative, neither of them in the review, both arising from the loop's second lap (a branch merging its base; a builder returning after `changes_requested`).

**Round 2 produced zero blocking findings** and eleven non-blocking ones (`reviews/B02-r2.md`): six record defects, four coverage or precision gaps in merge cases no spec row covers, and one wording gap in reviewer rule 5 that the `roles` guard caught the round-2 reviewer falling into. **So "B02 took two review rounds" means the build failed review once, in round 1, for a real defect in its own code — not that the paperwork failed.** For re-sizing: this is the second clean Opus-build / Opus-review measurement after B01A, and the first where V2-D51 did what it was locked for — a round that found only non-blocking findings passed instead of costing a build round. The size overrun recorded against B01A's note applies here too: an M build produced ~2,250 lines of code against BLUEPRINT 2.7's 400, so G1 should re-size M or give infrastructure builds a class of their own.

**◆ B03: two rounds, one defect, and it was the emergency stop.** Round 1's one blocking finding was that the `chronos-halt` stop — the switch that is meant to freeze the loop until the founder lifts it — could be switched off by the automation itself, because the collector read each issue's *current* labels and the rule it fed read the timeline (`reviews/B03-r1.md` finding 1). Round 2 fixed it, then swept for the same shape and found **three more fail-open paths in the same function**: only the first page of each feed was read, so a stop recorded further back was invisible; any `unlabeled` event counted as the stop being lifted, so removing an unrelated label cancelled a stop; and an unreadable label name failed open. It also found a fourth collector defect outside the review's remit — a gate's move pull request could never be returned, because only `base=v2-build` was queried and a branch cannot target itself, which made decision-table rows 8 and 8b unreachable through `gather()`. Each was verified against the live API and each break re-run by the round-2 reviewer. **Round 2 produced eight non-blocking findings and no blocking one, so the build passed** (`reviews/B03-r2.md`) — the third time V2-D51 has stopped a round of findings from costing a build round, and the first where two of the findings were in code rather than in the record. Two are worth carrying forward: the round-2 reviewer found a fail-open hole in the round's own new pagination helper, where `x or []` runs before an `isinstance` guard so a `null` or `{}` page silently truncates the halt feed (patch written out, unreachable with anything these endpoints return today); and **round 1's finding 3 is declined but its ground has shifted** — `gather` never fetches, so on a stale clone four facts read empty and a twice-failed build is told to resume where row 17 says halt, which the round-2 reviewer reproduced with real git. Round 1 called that non-blocking partly on a defence-in-depth argument that round 2 disproved; it stays non-blocking because the spec states no freshness precondition and B04 owns the loop's clone discipline. **B05 must not run anything unattended until it is closed.** And the stop still has nothing live behind it: the `chronos-halt` label does not exist in this repository, and — correcting a figure in the report — this repository has never had an issue of any kind, so neither half of the switch has ever been exercised. For re-sizing, the new information for G1 is the *shape* of the overrun rather than its existence: B03 is 2.9× the code cap and 2.0× the test cap, but round 2 moved tests four times as far as code (+320 strict against +43), and files touched went past the cap for the first time at **16 against 14**. Re-sizing M from code lines alone would miss where the model actually breaks. *Lines are raw totals for the whole build, matching B01 and B02's rows: code 1,712 raw / 1,163 excluding blanks, comments and docstrings; tests 1,954 raw / 1,198, plus 238 raw lines of YAML fixtures not counted in either column.*

## Re-sizing log

| Date | Gate | What the numbers said | What changed in the ladder |
|---|---|---|---|
