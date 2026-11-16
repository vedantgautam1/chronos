```yaml
id: B12
title: Data III — the data door, seal guard, footprints, Kraken candle loader
size: M
model: opus
who: loop
needs: [B09, B11]
ticks: 3
touches:
  - v2/pyproject.toml
  - v2/uv.lock
  - v2/src/chronos2/oceanus/**
  - v2/tests/oceanus/**
  - docs/v2/BUILD_NOTES.md
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B12 — Data III: the data door

## Why
"Research never reads sealed data" is only true if there is exactly one way to read data and that way refuses. This is that one way. It also hands back, with every read, the footprint the trial store needs: what was actually read, up to when, and whether anything was missing.

## Read first
- v1 `src/chronos/oceanus/access.py` (188), `seal.py` (149); tests `test_access.py`, `test_seal.py`, `test_acceptance.py` (for the shape of the tests).
- Master doc §6 "Sealed final block", §10 V2-D34, V2-D38, V2-D42, V2-D46. `BUILD_NOTES.md` §1 (the bare-date bullet), §2 (sealed holdouts), §6 (the V2-D42 traps).

## The rules (fixed here)
- `get_bars(key, start, end, *, purpose)` is the only public read. `purpose` is `"research"` or `"sealed_look"`.
- **Research reads are refused if `end` is later than the instrument's `sealed_from`** (read from `mnemosyne.seal`, B09). Refused means an exception; never a silently shortened answer.
- **`"sealed_look"` is refused always in this build.** The one-look path arrives with the ledger in B41. Until then nothing can read sealed data: fail closed.
- An instrument with no seal row can't be read at all.
- The mapping from `instrument_id` to the seal's `instrument` (for example `XBTUSD` on Kraken and a nano BTC future both map to `BTC`) is a table in code, tested; an unmapped instrument is refused.
- **Bars are stamped by their open time.** A read is legal exactly when every bar returned opens before `sealed_from`. `Footprint.max_timestamp_read` is the **open time of the last bar actually returned**, computed from the data, not from the request. B09's `audit_seal` treats `max_timestamp_read >= sealed_from` as a breach; the two rules agree.

## Deliver
1. `oceanus/door.py`: `get_bars(...) -> BarsResult(frame, footprint)`, `available_range(key)`, `SealedDataError`, `DataIntegrityError`. Reads go through B10's store and B11's validation; gaps found become `Footprint.gaps` and set `partial = True`.
2. `oceanus/instruments.py`: the instrument → seal-asset mapping for the spot pairs and futures named in the master doc §3.
3. `oceanus/loaders/kraken_ohlcvt.py`: reads one Kraken OHLCVT CSV into the bar schema, records the file's SHA-256, validates, stores. Flag `VERIFIED_AGAINST_REAL_FILE = False` with a test that fails the day someone sets it true without adding the real-file check's evidence file.
4. A test that no module under `v2/src/` other than `oceanus/door.py` and the loaders imports `oceanus.store`.
5. `duckdb` added as a dependency **only if** it is used here; otherwise leave it for the build that needs it.

## Steps
1. Tests (red). 2. `instruments.py`. 3. `door.py`. 4. Loader with a synthetic sample file. 5. The import-boundary test. 6. Docs, report.

## Known answers and checks
Synthetic hourly `BTC` data from 2026-03-25 to 2026-04-05, seal at 2026-04-01T00:00Z.

| Request `[start, end)` | Purpose | Expected |
|---|---|---|
| 03-30T00:00Z → 04-01T00:00Z | research | 48 bars; the last opens 03-31T23:00Z; `max_timestamp_read == 2026-03-31T23:00:00Z`; `partial == False` |
| 03-30T00:00Z → 04-01T00:00:01Z | research | `SealedDataError` |
| 03-30T00:00Z → 04-02T00:00Z | research | `SealedDataError` |
| 04-01T00:00Z → 04-02T00:00Z | sealed_look | `SealedDataError` ("no sealed looks before B41") |
| any range, instrument with no seal row | research | refused |
| any range, instrument not in the mapping | research | refused |
| `end = date(2026, 3, 31)` | research | raises (bare date) |

A result stored with the first row's footprint passes B09's `audit_seal`; the same result with its footprint moved to `2026-04-01T00:00:00Z` fails it (cross-check between B09 and B12).

Further checks:
- **No look-back parameter:** the door has no argument that takes a number of bars; callers ask for explicit ranges, so a rolling window can't pull a bar from beyond the range it asked for.
- **Gaps:** remove 3 bars from the stored data → the result has `partial = True` and one gap range; nothing interpolated.
- **Footprint hash:** `snapshot_hashes` equals `snapshot_hash` (B10) of the frame returned.
- **Loader:** a synthetic CSV in the documented Kraken layout (`timestamp` in whole seconds, `open, high, low, close, volume, trades`) [Likely — layout from Kraken's support page; not yet checked against a real file] loads to the expected frame; a file with a non-monotonic timestamp is rejected with the row number; the file hash is stored.
- **Boundary:** the import-boundary test fails when a temp module imports `oceanus.store` directly.

## Not in this build
The sealed-look ledger (B41) · post-seal series windows (V2-D46, B41) · trades, funding, quotes · downloading anything.

## Halt if
- The open-time rule conflicts with anything in the master doc or in B09 as built. (Then one of them is fixed in its own pull request first.)
- A real Kraken file is available and its layout differs from the documented one.

## Doc rows to update
`BUILD_NOTES.md` §6: the footprint is the last bar's open time. `COMPONENTS.md` §2 "Holdout seal": date guard in B12, look ledger in B41.
