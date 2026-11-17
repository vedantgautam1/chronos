```yaml
id: B12
title: Data I — bar schema, Parquet store, snapshot hash
size: M
model: opus
who: loop
needs: [G1]
ticks: 3
touches:
  - v2/src/chronos2/oceanus/**
  - v2/tests/oceanus/**
  - v2/tests/known_answers/v1_oracle/**
  - v2/tools/v1_oracle/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B12 — Data I

## Why
Every later result must be able to say exactly which data it saw. That needs one definition of a price bar and a fingerprint (hash) of any table of bars that is the same on every machine. v1 has both, tested. This build ports them and makes the fingerprint fast enough for years of one-minute data.

*Scope note: the data layer is in step 2 by V2-D47 (locked by the founder on 16 Nov).*

## Read first
- v1 `src/chronos/oceanus/model.py` (101), `store.py` (147); tests `tests/oceanus/test_model.py` (88), `test_store.py` (125).
- Master doc §4 row "Oceanus". `BUILD_NOTES.md` §1 (time rules), §4 (the bullets on stacked frames and precision).

## Deliver
1. `oceanus/schema.py`: `Timeframe` (as v1), `BAR_COLUMNS` = v1's columns, and the v2 identity of a series: `SeriesKey(instrument_id, source, asset_class, timeframe)`. Bars stay float64 (v1 decision, kept). `validate_frame_shape(frame)`: columns, dtypes, tz-aware UTC `open_time`, sorted, unique.
2. `oceanus/store.py`: `store_bars(root, key, frame)`, `load_stored(root, key)`, `get_range(root, key, start, end)` (half-open, tz-aware, raises on bare dates), `snapshot_hash(frame)`. Layout: `root/<source>/<instrument_id>/<timeframe>/…parquet`, one series per folder, never a stacked multi-asset file.
3. `snapshot_hash` **vectorised**, producing exactly v1's hash.
4. Oracle: `v2/tools/v1_oracle/dump_snapshot_hashes.py` (run in the v1 environment) writes `v2/tests/known_answers/v1_oracle/snapshot_hashes.json`: for seeds 2000–2019, a synthetic frame (10 to 5,000 bars, including zero volume, repeated prices, one `is_final = False` row, values like `0.1 + 0.2`) and v1's hash of it. Added to CI's `v1-oracle` job.
5. Ported tests, imports changed only, plus the tests below.

## Steps
1. Ported tests + new tests (red). 2. `schema.py`. 3. `store.py` with v1's row-by-row hash first → oracle parity green. 4. Vectorise; parity must stay green. 5. Timing. 6. Docs, report.

## Known answers and checks
- All ported v1 tests pass: 11 in `test_model.py`, 8 in `test_store.py` (any that exercise the Binance fetch path are listed in the report and replaced by a store-only equivalent, not dropped).
- **Hash parity:** 20 of 20 oracle frames, exact string equality. The empty frame's hash equals v1's.
- **Hash properties:** changing one price by one unit in the last place changes the hash; reordering rows before hashing doesn't (it sorts by `open_time`); a frame written to Parquet and read back hashes the same.
- **Speed:** hashing 1,000,000 bars takes under **5 seconds** on the CI runner (v1's loop is far slower; measure and report both).
- **Half-open ranges:** hourly bars for 2026-03-30 and 2026-03-31; `get_range(start=2026-03-31T00:00Z, end=2026-04-01T00:00Z)` returns exactly 24 bars, the last opening at 23:00. Passing `date(2026, 3, 31)` raises.
- **Never stacked:** `store_bars` refuses a frame with more than one instrument.
- `oceanus/` imports nothing from `mnemosyne/`, and no `ccxt`.

## Not in this build
Fetching anything from an exchange · validation and cleaning (B13) · the data door and the seal (B14) · trades, funding, non-price tables.

## Halt if
- The vectorised hash can't reproduce v1's exactly for some float (for example a formatting difference between `repr` and a vectorised formatter). Don't change the hash definition: keep v1's row-by-row version for correctness, report the timing, and stop for a decision.

## For the gate
`COMPONENTS.md` §2 (this build edits it): new row "Bar schema and Parquet store — ported in B12".
