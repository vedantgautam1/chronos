```yaml
id: B15
title: Data IV — file loaders (Kraken candles, Bitstamp minute set)
size: S
model: opus
who: loop
needs: [B14]
ticks: 2
touches:
  - v2/src/chronos2/oceanus/loaders/**
  - v2/src/chronos2/oceanus/instruments.py
  - v2/tests/oceanus/loaders/**
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B15 — Data IV: file loaders

## Why
The door (B14) can only hand out data that has been loaded into the store. Two loaders are needed before any real number can be computed: Kraken's candle files (the signal history the master doc names), and the public Bitstamp minute set the pre-build audit used, as a stand-in until the founder supplies a Kraken file. Each loader records exactly which file it read, so a result can always be traced to its bytes.

## Read first
- `BUILD_NOTES.md` §1 (download over HTTPS or check a published checksum; never unpack without a filter), §4 (Kraken history; never deduplicate trades on timestamp; precision). `COMPONENTS.md` §1 "Kraken".
- `docs/v2/research/pre-build-audit.md`: which Bitstamp set was used and its licence.

## Deliver
1. `oceanus/loaders/kraken_ohlcvt.py`: reads one Kraken OHLCVT CSV (`timestamp` in whole seconds, `open, high, low, close, volume, trades`) [Likely — layout from Kraken's support page; not yet checked against a real file] into the bar schema; records the file's SHA-256 in the stored snapshot's metadata; validates (B13); stores (B12).
2. `oceanus/loaders/bitstamp_minute.py`: the same for the Bitstamp minute set (`ff137/bitstamp-btcusd-minute-data`, MIT), with `source = "bitstamp"`.
3. `oceanus/instruments.py`: add the Bitstamp BTC/USD series, mapped to the `BTC` seal asset.
4. Each loader has `VERIFIED_AGAINST_REAL_FILE = False` and a test that fails if the flag is true without an evidence file (`tests/oceanus/loaders/evidence/<loader>.json`: file name, SHA-256, row count, first and last timestamp, who checked and when).
5. Tests on synthetic sample files in both layouts.

## Steps
1. Tests (red). 2. Kraken loader. 3. Bitstamp loader + mapping. 4. Evidence-flag tests. 5. Report.

## Known answers and checks
- A 1,440-row synthetic Kraken file loads to 1,440 bars with the expected first and last open times; the stored metadata holds the file's SHA-256 (computed in the test).
- A file with a non-monotonic timestamp is rejected with the row number; one with a duplicated timestamp is rejected (candles, unlike trades, have one row per interval).
- Loading the same file twice stores nothing new and leaves the snapshot hash unchanged.
- **The seal still holds:** a file containing bars from 1 Apr 2026 onward loads completely (the store keeps everything), and reading those bars back through the door for research is refused.
- After loading the Bitstamp sample, `get_bars` for the Bitstamp series works for pre-seal ranges and its footprint names `source = "bitstamp"`.
- Setting either flag to true without its evidence file fails the suite.

## Not in this build
Downloading anything (exchange sites are blocked from cloud sessions; files arrive through the founder's connected folder, or the Bitstamp set through a repository clone) · trades, funding, quotes (phase 3) · the multi-year Kraken history load (B42).

## Halt if
- A real Kraken file is available and its layout differs from the documented one.

## For the gate
`COMPONENTS.md` §1 "Kraken" row (this build edits it): loader built, real-file check pending. A new row for the Bitstamp minute set (MIT; stand-in only).
