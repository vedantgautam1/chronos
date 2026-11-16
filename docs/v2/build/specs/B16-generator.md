```yaml
id: B16
title: Synthetic world generator
size: S
model: opus
who: loop
needs: [B10]
ticks: 2
touches:
  - v2/src/chronos2/fixtures/**
  - v2/tests/fixtures/**
  - v2/tests/known_answers/v1_oracle/**
  - v2/tools/v1_oracle/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B16 — Synthetic world generator

## Why
To know whether a validation check works, you test it on made-up markets where you planted the answer yourself: pure noise, a known edge, a regime that flips. v1's generator makes those markets, reproducibly from a seed. The touchstones (B17) and the whole acceptance test (phase 4) are built on it, so it must produce exactly what v1's produced.

## Read first
- v1 `src/chronos/moirai/calibration/generator.py` (184 lines) and `tests/moirai/test_calibration_generator.py` (78 lines, 5 tests).

## Deliver
1. `fixtures/generator.py`: `GENERATOR_VERSION` (kept `"v1"`: same algorithm), `provenance()`, `generate_frame(...)`, `regime_drift_schedule(...)`, `generate_regime_frame(...)`, `realized_annualized_sharpe(frame)`; same signatures, same random draws in the same order. Output frames pass B10's `validate_frame_shape`.
2. The 5 v1 tests, imports changed only.
3. Oracle: `v2/tools/v1_oracle/dump_generator.py` (v1 environment) writes, for the exact argument sets the six touchstones use (seeds 314, 271, 20260202, 20260303, 20260404; windows and Sharpe targets as in v1's `touchstones.py`) plus 5 small extra cases, the `snapshot_hash` of each generated frame and its realised Sharpe. Added to CI's `v1-oracle` job.
4. `tests/fixtures/test_generator_parity.py`.

## Steps
1. Ported tests + parity test (red). 2. Port. 3. Oracle file. 4. Green. 5. Docs, report.

## Known answers and checks
- The 5 ported tests pass.
- **Parity:** for every oracle case, v2's frame has the same `snapshot_hash` as v1's (exact). If hashes differ only because numpy's random methods changed between the two environments, that is the halt condition below, not something to paper over.
- **Determinism:** the same seed twice gives the same hash; a different seed gives a different one.
- **The planted answer is there:** for a 3-year hourly frame with target annual Sharpe 3.0 and seed 314's arguments, `realized_annualized_sharpe` is within the band v1's own test asserts.
- **Quarantine:** `fixtures/` has no function that writes into a data root; frames are returned in memory. A test asserts `generate_*` creates no files.

## Not in this build
Touchstone definitions (B17) · intraday-style planted edges (phase 4, B47: new worlds, pre-registered there).

## Halt if
- Hash parity fails because of a numpy version difference in random number methods. Report which method and both versions. The options (pin numpy for fixtures; commit generated frames as files; accept statistical equivalence and re-pin every touchstone) are not equivalent, and the founder's reviewer-of-record for statistics (Claude under V2-D25) decides with the evidence at a gate, not inside the build.

## Doc rows to update
`COMPONENTS.md` §2 "Touchstones + regime generator": generator ported in B16.
