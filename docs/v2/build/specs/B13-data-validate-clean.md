```yaml
id: B13
title: Data II — validate and clean
size: M
model: opus
who: loop
needs: [B12]
ticks: 3
touches:
  - v2/src/chronos2/oceanus/**
  - v2/tests/oceanus/**
may_modify_tests: []
```

# B13 — Data II

## Why
Bad data makes fake edges. v1's policy is the right one and already tested: detect problems and report them; never invent prices to fill a gap; mark outliers instead of deleting them; drop only rows that are provably impossible, and say which. This build ports it unchanged.

## Read first
- v1 `src/chronos/oceanus/validate.py` (140), `clean.py` (121); tests `test_validate.py` (68), `test_clean.py` (80), `corrupted_fixture.py` (65).
- `BUILD_NOTES.md` §4: "Never forward- or back-fill a stacked multi-asset frame", "A feed recorder must detect gaps".

## Deliver
1. `oceanus/validate.py`: `Issue`, `ValidationReport`, `validate(frame, key)`: the same issue kinds as v1 [Certain — read]: `naive_timestamp`, `duplicate`, `out_of_order`, `gap`, `impossible_value` (non-positive price, negative volume), `ohlc` (high below low; open or close outside low–high), and the outlier flag.
2. `oceanus/clean.py`: `CleaningPolicy` (v1's defaults: `drop_broken_rows=True`, `drop_outliers=False`, `fill_gaps=False`), `CleaningResult`, `clean(frame, report, policy)`: same behaviour as v1. The result lists every dropped row with its reason and every gap as a `[start, end)` range. Those gap ranges are what later becomes `Footprint.gaps` (B11/B14).
3. Ported tests and fixture, imports changed only, plus the tests below.

## Steps
1. Ported tests + new tests (red). 2. `validate.py`. 3. `clean.py`. 4. Report.

## Known answers and checks
- All ported v1 tests pass: 7 in `test_validate.py`, 7 in `test_clean.py`.
- **Never interpolates:** for a frame with a 3-bar gap, the cleaned frame has the same 3 bars missing, `CleaningResult.gaps` holds exactly one range covering them, and no row in the output has a timestamp inside it. Asserted for every fixture: the set of output timestamps is a subset of the input's.
- **Never fills:** `CleaningPolicy(fill_gaps=True)` raises, as in v1. A scan of `oceanus/` for `ffill`, `bfill`, `fillna`, `interpolate` finds nothing (test).
- **Reports every drop:** on v1's corrupted fixture, `len(dropped) + len(output) == len(input)`, and each dropped row carries one of the documented reasons.
- **Outliers are flagged, not removed:** a bar 40% away from both neighbours stays in the output with a flag.
- **Deterministic:** cleaning twice gives the same frame and the same `snapshot_hash` (B12).

## Not in this build
The data door (B14) · any exchange-specific rule (Kraken's file quirks arrive with its loader in B15) · trades.

## Halt if
- A v1 test depends on Binance-specific behaviour that has no v2 meaning. List it and stop; don't drop a test silently.

## For the gate
`COMPONENTS.md` §2 row "Data validation/cleaning policy": ported in B13. (Not in this build's `touches`; the line goes in the report.)
