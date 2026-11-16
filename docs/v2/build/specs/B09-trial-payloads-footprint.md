```yaml
id: B09
title: Trial store III — returns, trades, data footprint, compare guard, seal audit
size: M
model: opus
who: loop
needs: [B08]
ticks: 3
touches:
  - v2/migrations/**
  - v2/src/chronos2/mnemosyne/**
  - v2/tests/mnemosyne/**
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B09 — Trial store III

## Why
A trial that stores only its summary number can't be re-examined later. This build stores what each trial actually produced (its daily returns and its trades, with each cost kept separate) and a **footprint**: the latest data timestamp it really read, the hash of that data, the code version, and whether it was complete. The footprint is what lets an audit prove, mechanically, that nothing ever read sealed data.

It also defines the one shape every engine must hand results over in (proposal P-17), so the checks built later don't care which engine ran.

## Read first
- `BUILD_NOTES.md` §6, bullets on V2-D33, V2-D42, the comparison guard and "Reproduce on demand". Master doc §10: V2-D33, V2-D38, V2-D42.

## Deliver
1. `mnemosyne/result.py`: frozen dataclasses
   - `Trade`: `entry_at`, `exit_at`, `side`, `contracts`, `entry_price`, `exit_price`, `gross_pnl`, and one field per cost component: `commission`, `exchange_fee`, `regulatory_fee`, `spread`, `slippage`, `funding`, `basis` (money as `Decimal`; a positive cost reduces P&L; funding and basis may be negative, i.e. income).
   - `Footprint`: `max_timestamp_read`, `snapshot_hashes` (tuple), `code_coordinate`, `partial` (bool), `gaps` (tuple of `[start, end)`), `series` (optional tag, for V2-D46).
   - `TrialResult`: `trial_id`, `calendar` (`start`, `step`, `n`), `net_returns` (float64 array of length `n`), `trades` (tuple of `Trade`), `footprint`.
2. `0003_payloads.sql`: `mnemosyne.trial_returns` (one row per trial: calendar + `float8[]`), `mnemosyne.trial_trade`, `mnemosyne.trial_footprint`; all append-only, hashed, journaled, keyed to `trial`.
3. `0004_seal.sql` under `v2/migrations/protected/`: table `mnemosyne.seal` (`instrument`, `sealed_from timestamptz`), seeded with exactly two rows: `BTC` and `ETH`, `2026-04-01T00:00:00Z` (V2-D38). Append-only.
4. `mnemosyne/store.py`: `store_result(TrialResult)`, `load_result(trial_id)`, `compare(a, b)`, `audit_seal(conn)`.
5. Tests.

## Steps
1. Tests (red). 2. `result.py`. 3. Migrations. 4. `store.py` → green. 5. Size measurement. 6. Docs, report.

## Known answers and checks
- **Round trip:** a `TrialResult` with 800 daily returns and 37 trades, stored and loaded, is equal field by field; returns are bit-identical; Decimals keep their exact strings.
- **Net P&L identity:** for every stored trade, `net = gross − (commission + exchange_fee + regulatory_fee + spread + slippage + funding + basis)`, and the sum of trade nets equals the stored total to the cent. A trade whose components don't add up is refused.
- **Footprint is about what was read:** storing a result whose `max_timestamp_read` is later than its `calendar` end is allowed and kept as given (this is the "a rolling window read one bar further" trap: the store records it, B12 prevents it, `audit_seal` catches it).
- **`audit_seal`:** with trials on `BTC` whose footprints end at `2026-03-31T23:59:00Z`, returns nothing. Add one trial with `max_timestamp_read = 2026-04-01T00:00:00Z` → returns exactly that trial. Add one on an instrument with no seal row → reported as "no seal defined", never silently passed.
- **`compare`:** refuses, with the reason, when either result is `partial`; when dataset hashes, windows, cost-config hashes, seeds or baselines differ. Accepts two complete results that match on all five.
- **Partial can't pose as complete:** a result with `gaps` non-empty and `partial = False` is refused at `store_result`.
- **One calendar per dataset:** two trials on the same dataset hash with different calendars → the second is refused.
- **Size:** 5,000 trials × 800 daily returns occupy less than **60 MB** in `trial_returns` (measured with `pg_total_relation_size`; BUILD_NOTES estimates ~32 MB).
- **Seal is protected:** the `protected` guard (B01) fails on any pull request that edits `0004_seal.sql` or adds another migration touching `mnemosyne.seal` without the founder's label. (This build creates it, so this pull request itself needs the label: **stop at step 3 and ask**; that is the guard working.)
- **Attacks:** 8 of 8 refused on each new table.

## Not in this build
`reproduce()` (needs an engine; its five statuses are listed in BUILD_NOTES §6 and arrive with B38) · the sealed-look ledger (B41) · set-level tests over stored returns.

## Halt if
- Step 3: always (protected value: the seal date). Resume when the founder approves.
- Arrays over a few thousand elements make inserts or loads slow enough to matter (more than 50 ms per trial): propose the alternative and stop.

## Doc rows to update
`BUILD_NOTES.md` §6: "V2-D33 and V2-D42 implemented in B09; the engine-neutral result shape is `mnemosyne/result.py`."
