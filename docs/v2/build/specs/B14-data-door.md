```yaml
id: B14
title: Data III — the data door, seal guard, footprints
size: M
model: opus
who: loop
needs: [B11, B13]
ticks: 3
touches:
  - v2/src/chronos2/oceanus/door.py
  - v2/src/chronos2/oceanus/instruments.py
  - v2/tests/oceanus/test_door.py
  - v2/tests/oceanus/test_instruments.py
  - v2/tests/oceanus/test_boundary.py
  - docs/v2/BUILD_NOTES.md
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B14 — Data III: the data door

## Why
"Research never reads sealed data" is only true if there is exactly one way to read data and that way refuses. This is that one way. It also hands back, with every read, the footprint the trial store needs: what was actually read, up to when, and whether anything was missing.

## Read first
- v1 `src/chronos/oceanus/access.py` (188), `seal.py` (149); tests `test_access.py`, `test_seal.py`, `test_acceptance.py` (for the shape of the tests).
- Master doc §6 "Sealed final block", §10 V2-D34, V2-D38, V2-D42, V2-D46. `BUILD_NOTES.md` §1 (the bare-date bullet), §2 (sealed holdouts), §6 (the V2-D42 traps).

## The rules (fixed here)
- `get_bars(key, start, end, *, purpose)` is the only public read. `purpose` is `"research"` or `"sealed_look"`.
- **Research reads are refused if `end` is later than the instrument's seal date** (read from the protected file through `core.protected.load_validation()`, B11). Refused means an exception; never a silently shortened answer.
- **`"sealed_look"` is refused always in this build.** The one-look path arrives with the ledger in B46. Until then nothing can read sealed data: fail closed.
- An instrument with no seal date can't be read at all.
- The mapping from `instrument_id` to the seal's asset (for example `XBTUSD` on Kraken and a nano BTC future both map to `BTC`) is a table in code, tested; an unmapped instrument is refused.
- **Bars are stamped by their open time.** A read is legal exactly when every bar returned opens before the seal date. `Footprint.max_timestamp_read` is the **open time of the last bar actually returned**, computed from the data, not from the request; `Footprint.assets` is the seal asset of the instrument read, from the mapping in `instruments.py`. B11's `audit_seal` treats `max_timestamp_read >=` the seal date as a breach; the two rules agree.

## Deliver
1. `oceanus/door.py`: `get_bars(...) -> BarsResult(frame, footprint)`, `available_range(key)`, `SealedDataError`, `DataIntegrityError`. Reads go through B12's store and B13's validation; gaps found become `Footprint.gaps` and set `partial = True`.
2. `oceanus/instruments.py`: the instrument → seal-asset mapping for the spot pairs and futures named in the master doc §3. Its tests assert that each listed mapping exists and that an unknown instrument is refused; they don't assert that the list is complete (B15 adds a series, and existing test files are frozen).
3. A test that no module under `v2/src/` other than `oceanus/door.py` and `oceanus/loaders/` imports `oceanus.store`, and that nothing outside `oceanus/` calls a parquet reader directly. (This is a test, not an operating-system barrier: it catches accidents, not determination.)

## Steps
1. Tests (red). 2. `instruments.py`. 3. `door.py`. 4. The import-boundary test. 5. Report.

## Known answers and checks
Synthetic hourly `BTC` data from 2026-03-25 to 2026-04-05, seal at 2026-04-01T00:00Z.

| Request `[start, end)` | Purpose | Expected |
|---|---|---|
| 03-30T00:00Z → 04-01T00:00Z | research | 48 bars; the last opens 03-31T23:00Z; `max_timestamp_read == 2026-03-31T23:00:00Z`; `partial == False` |
| 03-30T00:00Z → 04-01T00:00:01Z | research | `SealedDataError` |
| 03-30T00:00Z → 04-02T00:00Z | research | `SealedDataError` |
| 04-01T00:00Z → 04-02T00:00Z | sealed_look | `SealedDataError` ("no sealed looks before B46") |
| any range, instrument with no seal date | research | refused |
| any range, instrument not in the mapping | research | refused |
| `end = date(2026, 3, 31)` | research | raises (bare date) |

A result stored with the first row's footprint passes B11's `audit_seal`; the same result with its footprint moved to `2026-04-01T00:00:00Z` fails it (cross-check between B11 and B14).

Further checks:
- **No look-back parameter:** the door has no argument that takes a number of bars; callers ask for explicit ranges, so a rolling window can't pull a bar from beyond the range it asked for.
- **Gaps:** remove 3 bars from the stored data → the result has `partial = True` and one gap range; nothing interpolated.
- **Footprint hash:** `snapshot_hashes` equals `snapshot_hash` (B12) of the frame returned.
- **Boundary:** the import-boundary test fails when a temp module imports `oceanus.store` directly.

## Not in this build
File loaders (B15) · the sealed-look ledger (B46) · post-seal series windows (V2-D46, B46) · trades, funding, quotes.

## Halt if
- The open-time rule conflicts with anything in the master doc or in B11 as built. (Then one of them is fixed in its own pull request first.)

## For the gate
`BUILD_NOTES.md` §6 (this build edits that line): the footprint is the open time of the last bar read. `COMPONENTS.md` §2 "Holdout seal": date guard in B14, look ledger in B46.
