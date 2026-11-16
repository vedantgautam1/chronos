```yaml
id: B16
title: Costs — venue fee schedules, cost components, 2x and adverse-funding stress
size: M
model: opus
who: loop
needs: [B11]
ticks: 3
touches:
  - v2/src/chronos2/costs/**
  - v2/config/venues/**
  - v2/tests/costs/**
  - docs/v2/BUILD_NOTES.md
  - docs/v2/COMPONENTS.md
may_modify_tests: []
```

# B16 — Costs

## Why
At a few trades a day, costs are the same size as the edge. The fees on the contract we plan to trade are fixed dollars per contract, so in percentage terms they change with the BTC price: about 9.7 basis points a round trip at $64,000 and 6.2 at $100,000, before spread and slippage [Certain — arithmetic, pre-build audit]. A cost model that gets this wrong makes every later result wrong. Each cost is kept as its own number so the stress tests can double the right ones and only those (V2-D35).

## Read first
- Master doc §3 row "Crypto execution"; §6 "Cost stress per component"; §10 V2-D35, V2-D39. `BUILD_NOTES.md` §5 bullets on nano fees, the cost model, MBT vs nano; §2 bullet "Positive at 1× and 2× costs".
- v1 `src/chronos/hephaestus/costs.py` and `tests/hephaestus/test_costs.py`: for the "no path around costs" idea only. Don't reuse a number.

## Deliver
1. `v2/config/venues/*.yaml`, one per contract, each value with `source` (URL) and `read_on` (date): 
   - `ibkr_coinbase_nano_btc`: multiplier 0.01 BTC; per contract per side: commission 0.20, exchange fee 0.10, regulatory fee 0.01 USD; funding: hourly accrual.
   - `ibkr_coinbase_nano_eth`: multiplier 0.1 ETH; same three fees (marked `unverified: true` for ETH until read from IBKR's page).
   - `ibkr_cme_mbt`: multiplier 0.1 BTC; commission 0.85, exchange 1.15, regulatory 0.02 (`approximate: true`); no funding.
   - `ibkr_cme_bff`: multiplier 0.02 BTC; commission 0.25, exchange 0.35, regulatory `unknown` → the loader refuses to price it until filled.
2. The stress settings are **read** from the protected file created in B02 (`stress_friction_multiplier`, `adverse_funding_hourly_rate`) through `core.protected` (B11). This build doesn't change that file.
3. `costs/venue.py`: load and validate a venue file; refuse `unknown` values; expose `fees_per_side(contracts)`.
4. `costs/model.py`: `CostBreakdown` with exactly these seven Decimal fields: `commission`, `exchange_fee`, `regulatory_fee`, `spread`, `slippage`, `funding`, `basis` (the same names B11's `Trade` uses; this build adds a test that the two sets of names are equal) and `price_trade(venue, side, contracts, entry_price, exit_price, hours_held, half_spread, slippage_per_side, funding_rate_path, basis_at_entry, basis_at_exit) -> CostBreakdown`.
5. `costs/stress.py`: `stress(breakdown, mode, config)` for `mode` in `x1`, `x2_frictions`, `adverse_funding`.
6. `costs/units.py`: `fees_in_bps(venue, price)`: round-trip fixed fees as basis points of notional at a given price.
7. A test that every public function in `costs/` returns a full `CostBreakdown`: no function returns a P&L without one (the "no cost-free path" rule).

## Steps
1. Tests (red). 2. Venue files + loader. 3. `model.py`. 4. `stress.py`. 5. `units.py`. 6. Docs, report.

## Known answers and checks
**Fees in basis points** (nano BTC, round trip = 2 sides × 0.31 = 0.62 USD per contract):
- at 64,000: `0.62 / (0.01 × 64,000) × 10,000 = 9.6875` bps
- at 100,000: `6.2` bps
- MBT at 100,000: `2 × 2.02 / (0.1 × 100,000) × 10,000 = 4.04` bps
- nano is dearer per BTC than MBT at any price: `31 USD` vs `20.2 USD` per BTC of notional per side.

**One trade, by hand.** Long 3 nano BTC, entry 100,000, exit 100,500, held 5 hours, half-spread 2.50 USD of price, slippage 1.00 USD of price per side, funding 0.001% per hour paid by longs, no basis.
- gross = `3 × 0.01 × 500 = 15.00`
- commission `3 × 2 × 0.20 = 1.20`; exchange `0.60`; regulatory `0.06`
- spread `3 × 0.01 × 2.50 × 2 = 0.15`; slippage `3 × 0.01 × 1.00 × 2 = 0.06`
- funding `3 × 0.01 × 100,000 × 0.00001 × 5 = 0.15`
- net at 1× = `15.00 − 2.22 = 12.78`
- net at 2× frictions = `15.00 − (2 × 2.07) − 0.15 = 10.71` (the 2.07 of frictions doubles; funding doesn't)

**The V2-D35 fixture** (a result that looks good only because income was doubled). Per trade: gross `+0.10`, frictions `0.30`, funding `−0.50` (income).
- 1×: `0.10 − 0.30 + 0.50 = +0.30`
- naive "double every cost": `0.10 − 0.60 + 1.00 = +0.50` (better than 1×: the trap)
- `x2_frictions`: `0.10 − 0.60 + 0.50 = 0.00` → **not above zero**
- `stress(..., "x2_frictions")` must return exactly the third line; a test asserts it is **not** the second.

**Adverse funding.** Same trade as "by hand", adverse hourly rate 0.004%: funding becomes `3 × 0.01 × 100,000 × 0.00004 × 5 = 0.60`, charged whatever the side. With the real protected file (no rate set for the contract yet), `stress(..., "adverse_funding")` raises `FundingLevelNotSet`; the test for the 0.60 figure passes its own rate explicitly. With a contract that has no funding (MBT), the mode returns the 1× breakdown unchanged and says so.

**Short side:** the same trade short with the price falling 500 has the same gross and fees; funding at +0.001% for longs is **income** for the short (`−0.15`).

**Refusals:** pricing BFF raises (regulatory fee unknown). Zero or negative contracts raise. A fractional contract count raises.

**No double counting of the spread:** `spread` is half the quoted spread, paid on each side; `slippage` is what a market order pays **beyond** that by walking the book (B17 measures it net of the spread). The 2× run doubles each exactly once.

## Not in this build
Measuring spread or slippage from data (B17) · wiring costs into any engine (B25, B43) · basis modelling before the contract existed (proposal P-15) · choosing the cheaper contract by size (phase 4, sizing).

## Halt if
- Any fee on IBKR's pages has changed since 16 Nov (re-read the two source pages first; if a page can't be reached from the session, keep the 16 Nov values and say so).
- The half-spread and slippage conventions (per side, in price units) don't fit how B11's `Trade` stores them.

## For the gate
`BUILD_NOTES.md` §5 (this build edits it): "v2 cost model: `costs/` (B16); venue fees live in `v2/config/venues/` with source and date". `COMPONENTS.md` §2 "Cost and slippage measurement".
