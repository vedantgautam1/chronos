# LEDGER — estimate vs actual

One row per build. The reviewer fills the "actual" columns when a build merges. Gates G1 and G2 re-size the rest of the ladder from these numbers (BLUEPRINT 2.7).

**How to read it.** *Build ticks* = sessions the builder needed (an M build is allowed 3; a fourth is an overrun and a halt). *Review rounds* = 1 if it passed first time, 2 if it needed a fix. *Lines* = code + tests added. *Halts* = why, in three words.

The estimates are guesses until B01–B03 have run [Guessing]. That is the point of this file.

| Build | What | Size | Est. build ticks | Est. review rounds | Actual build ticks | Actual review rounds | Lines (code / tests) | Halts | Merged (UTC) |
|---|---|---|---|---|---|---|---|---|---|
| **G0** | **Blueprint approved** | gate | — | — | | | | | |
| B01 | v2 project scaffold, automatic tests, the guards | M | 2–3 | 1 | | | | | |
| B02 | The loop: ladder reader, next-action script, agents, commands | M | 2–3 | 1 | | | | | |
| B03 | First unattended run, schedule, notifications | S | 1–2 | 1 | | | | | |
| **G1** | **The loop is proven** | gate | — | — | | | | | |
| B04 | Statistics I: ported core + v1 known-answer tests + v1 oracle | M | 2–3 | 1 | | | | | |
| B05 | Statistics II: math probe as tests, mid-rank counters, floating-point tie case | M | 2–3 | 1 | | | | | |
| B06 | Statistics III: cross-checks against outside libraries | S | 1–2 | 1 | | | | | |
| B07 | Trial store I: Postgres harness, migrations, append-only, audit | M | 2–3 | 1 | | | | | |
| B08 | Trial store II: ids, code coordinate, hypotheses, SEARCH/VERIFICATION, honest N | M | 2–3 | 1 | | | | | |
| B09 | Trial store III: returns, trades, footprint, compare guard, seal audit | M | 2–3 | 1 | | | | | |
| B10 | Data I: bar schema, Parquet store, snapshot hash | M | 2–3 | 1 | | | | | |
| B11 | Data II: validate and clean | M | 2–3 | 1 | | | | | |
| B12 | Data III: the data door, seal guard, footprints, Kraken candle loader | M | 2–3 | 1 | | | | | |
| B13 | Costs: venue fees, components, 2x and adverse-funding stress | M | 2–3 | 1 | | | | | |
| B14 | Slippage and spread measurement method | S | 1–2 | 1 | | | | | |
| B15 | Search-fragmentation warning | M | 2–3 | 1 | | | | | |
| B16 | Synthetic world generator | S | 1–2 | 1 | | | | | |
| B17 | Touchstones as pre-registered fixtures | M | 2–3 | 1 | | | | | |
| B18 | Costs vs typical price moves by holding time (P-12) | S | 1–2 | 1 | | | | | |
| **G2** | **Foundations audit (step 2 done)** | gate | — | — | | | | | |
| B19 | Spike prep: pinned Nautilus, data in, MA strategy | M | 2–3 | 1 | | | | | |
| B20 | Criterion (a): parity with v1 engine; five fill tests on two engines | M | 2–3 | 1 | | | | | |
| B21 | Criterion (b): our cost model in the engine | S | 1–2 | 1 | | | | | |
| B22 | IBKR paper hookup on the Mac; find the nano contract | S | 1–2 | 1 | | | | | |
| B23 | Criterion (e): paper-trade nano both ways; funding and fees | M | 2–3 | 1 | | | | | |
| B24 | Criterion (f): broker precautions; second connection | S | 1–2 | 1 | | | | | |
| B25 | Criterion (d): two strategies, two venues, one node | S | 1–2 | 1 | | | | | |
| B26 | Criterion (c): several days unattended across a Monday re-login | S | 1–2 | 1 | | | | | |
| B27 | Spike report | S | 1–2 | 1 | | | | | |
| **G3** | **Engine decision** | gate | — | — | | | | | |
| B28 | Server up: hardening, Postgres, backups, UTC | M | 2–3 | 1 | | | | | |
| B29 | Budget guard for paid APIs (V2-D41) | M | 2–3 | 1 | | | | | |
| B30 | Collector frame: schedule, raw files, gaps, alerts | M | 2–3 | 1 | | | | | |
| B31 | Kraken trade recorder (V2-D26) | M | 2–3 | 1 | | | | | |
| B32 | Kraken bulk trade files; side check | M | 2–3 | 1 | | | | | |
| B33 | News catalog import (AGPL), headline recorder | M | 2–3 | 1 | | | | | |
| B34 | GDELT collector | S | 1–2 | 1 | | | | | |
| B35 | Grok/X collector, both scorers logged | M | 2–3 | 1 | | | | | |
| B36 | Macro actuals with release times | S | 1–2 | 1 | | | | | |
| B37 | IBKR spread snapshots | M | 2–3 | 1 | | | | | |
| **G4** | **Collection audit** | gate | — | — | | | | | |
| B38 | Screening wrapper: five fixes, every variant a counted trial | M | 2–3 | 1 | | | | | |
| B39 | Look-ahead test kit: slice, warm-up, nudge | M | 2–3 | 1 | | | | | |
| B40 | Null benchmark (V2-D21) + four known-answer tests | M | 2–3 | 1 | | | | | |
| B41 | Sealed-look ledger, series windows; refusal in the database | M | 2–3 | 1 | | | | | |
| B42 | Edge check I: frozen config, data sufficiency, DSR, cost runs | M | 2–3 | 1 | | | | | |
| B43 | Edge check II: neighbourhood, sealed confirm, warnings, fixtures | M | 2–3 | 1 | | | | | |
| B44 | Change check + fixtures (V2-D32) | M | 2–3 | 1 | | | | | |
| B45 | Sizing v0: drawdown budget, ruin formula, bootstrap check | M | 2–3 | 1 | | | | | |
| B46 | Run the touchstones against their pre-registered verdicts | M | 2–3 | 1 | | | | | |
| B47 | Planted-edge calibration: write the criteria | S | 1–2 | 1 | | | | | |
| B48 | Planted-edge calibration: run and choose the rule | M | 2–3 | 1 | | | | | |
| B49 | Acceptance report | S | 1–2 | 1 | | | | | |
| **G5** | **Acceptance test passed (protected)** | gate | — | — | | | | | |

## Cost per tick (measured in B03)

| Kind of tick | Share of a five-hour window (Pro) | Wall-clock | Measured on |
|---|---|---|---|
| Build tick (M build, Opus) | | | |
| Review tick (Opus) | | | |
| Idle tick (nothing to do) | | | |

## Re-sizing log

| Date | Gate | What the numbers said | What changed in the ladder |
|---|---|---|---|
