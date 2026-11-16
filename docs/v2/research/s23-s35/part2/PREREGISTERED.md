# S23–S35, Part 2 — pysystemtrade (S30), Zipline (S28), RQAlpha (S29): tests written before running (V2-D25 rule 2)

Written 2026-11-06 05:45 UTC, after reading the code and before running any test below.

| Item | Repo | Commit | Licence |
|---|---|---|---|
| S30 | pst-group/pysystemtrade | `bbf5cf823e16` (2 Nov 2026) | GPL-3.0 |
| S28 | quantopian/zipline (original) | `014f1fc` (last commit 14 Oct 2020) | Apache-2.0 |
| S28 | stefan-jansen/zipline-reloaded | `5dd9fef` (2 Nov 2026), PyPI 3.2.1 | Apache-2.0 |
| S29 | ricequant/rqalpha | `0bf04946e825` (27 Oct 2026) | Apache-2.0 **for non-commercial use**; other use needs Ricequant's permission |

Each repo is installed into its own `uv` venv from the commit above (the original Zipline from PyPI, since its source needs a 2017-era build chain). Run from outside the repos, except each repo's own test suite, which runs from its root as documented (BUILD_NOTES §1). Real BTC data: the repo's own CME Micro Bitcoin CSVs (pysystemtrade, to 28 Mar 2024) and the Bitstamp file already in the workspace (to 7 Jan 2025); both before the 1 Apr 2026 seal. **Toy strategies only; profits are not evidence and are not trials of any Chronos hypothesis.**

Why these tests: pysystemtrade already trades CME Micro Bitcoin (MBT) and Micro Ether (MET) through IBKR in production, so it is a possible reference for — or rival to — our engine, sizing (Themis), guard (Nemesis) and reports. Zipline and RQAlpha are older event-driven engines; the question is whether any of their parts belong in our architecture.

## pysystemtrade (S30)

- **P1 — its test suite.** `pytest` from the repo root (60-minute cap). *PASS:* 0 failures, 0 errors; tests that need MongoDB, IB or the network are listed separately.
- **P2 — 24/7 data folded into business days.** Backtests build daily prices with `resample("1B").last()`. Feed `resample_prices_to_business_day_index` a synthetic 24/7 hourly series (4 weeks; price = hours since start, so each value shows when it was printed).
  - *Report:* which hour the Friday, Saturday and Sunday values come from.
  - *PASS:* no price movement is lost (sum of daily changes = first-to-last change).
  - *Expected:* Friday's value is Sunday 23:00.
- **P3 — costs are exact.**
  - (a) `instrumentCosts` for BITCOIN (repo config: 3.27 per contract, spread cost 13.0, multiplier 0.1): 2 contracts at 60,000. *PASS:* cost = 2 × 13.0 × 0.1 + max(2 × 3.27, 0, 0) = 9.14.
  - (b) A BTC-only run of the chapter-15 system (`futures_system`, `instruments: [BITCOIN]`). *PASS:* the total cost in its account curve equals Σ over position changes of the (a) formula at that day's price, to 1e-6 relative. If the accounts use a different cost basis, report which.
- **P4 — position sizing matches the documented formula.** In the same run, the last date's subsystem position. *PASS:* hand calculation from its own intermediate values equals `get_subsystem_position` to 1e-9 relative:
  - position = forecast / 10 × volatility scalar;
  - volatility scalar = daily cash vol target / instrument value vol (in base currency);
  - daily cash vol target = capital × vol target / 16.
- **P5 — production controls, on their own objects (no database).**
  - (a) Overrides: reduce-only on a trade that grows the position → 0; on a trade that shrinks it → unchanged; "close" → trade to flat; "no trading" → 0; float 0.5 → report. *PASS:* each matches the docs.
  - (b) Trade limit 3 per day with 2 already used; a proposed 5 → *report* the allowed trade. *Expected:* 1 (clipped).
  - (c) Position limit 4 contracts at position 3; a proposed +3 → *report* the trade the limit allows. *Expected:* +1 (clipped).
  
  (b) and (c) are compared with our rule "block, don't clip" (BUILD_NOTES §11, S16).
- **P6 — back-adjusted BTC prices are consistent.** BITCOIN `adjusted_prices` vs `multiple_prices` (current contract). *PASS:* on every timestamp where the current contract didn't change, adjusted change = current-contract change to 1e-6, for ≥ 99.9% of such rows. Report the number of rolls and the largest roll gap.
- **P7 — speed.** Wall time of the BTC-only chapter-15 backtest (P3b) on this 2-CPU machine. Report.
- **P8 — read only:** what an IBKR futures instrument needs in config (`ib_config_futures.csv`: symbol, exchange, currency, multiplier); whether a Coinbase Derivatives contract could be added by config alone. Reported, not pass/fail.

## Zipline (S28)

- **Z0 — the original still runs?** In a Python 3.6 venv (its newest supported version), install `zipline==1.4.1` from PyPI and run a buy-and-hold algorithm on a synthetic `csvdir` bundle. *PASS:* imports and completes. *Expected:* fails to install (2017-era compiled dependencies). Either way, its architecture is judged from reading.
- **Z1 — zipline-reloaded's test suite.** `pytest tests` from its root (60-minute cap). *PASS:* 0 failures, 0 errors.
- **Z2 — fill price and costs (reloaded), defaults.** One synthetic stock on the NYSE calendar via a `csvdir` bundle, volume 1,000,000 a day; `order(asset, 100)` on day *t*. *PASS:* fills on day *t+1* at close(*t+1*) × 1.0005 with commission 100 × $0.001 = $0.10 (its stated defaults: 5 bps slippage, $0.001/share).
- **Z3 — volume cap.** Volume 20,000 a day; order 10,000. *Report* fills per day. *Expected:* 2,000 a day over 5 days (10% volume limit).
- **Z4 — short round trip.** Short 100 on *t*, cover on *t+3*. *PASS:* P&L = hand calculation with slippage and commission on both fills, to 1e-6.
- **Z5 — no peeking.** In `handle_data` on day *t*, `data.history(asset, "close", 2, "1d")` ends at close(*t*); `data.current` = close(*t*). *PASS:* true on every day of a 60-day run.
- **Z6 — 24/7 calendar.** Bitstamp BTC daily bars for 2023 in a `csvdir` bundle on the `24/7` calendar; buy-and-hold run. *PASS:* ingests and the performance output has 365 daily rows.
- **Z7 — speed.** Wall time of a 1-year daily backtest (Z6). Report.

## RQAlpha (S29)

- **R1 — test suites.** `tests/unittest` from the repo root. *PASS:* 0 failures, 0 errors. Integration tests: report whether they can run offline (they may need Ricequant's data bundle).
- **R2 — data.** Can its data bundle be downloaded from here? Report.
- **R3 — risk validators.** Read `rqalpha_mod_sys_risk` and run its validator unit tests. *Report:* does an order failing a check get **rejected** or **reduced**?

## What would change the conclusions
- P3–P6 failing would rule pysystemtrade out as a sizing or cost reference.
- P5 behaving as expected (clipping) doesn't rule it out: it is a design difference to note against V2-D36/V2-D40, not a bug.
- If any engine passes Z2–Z6 / R1–R3 and also covers what Nautilus is meant to do (IBKR, Coinbase/CME futures, minutes-to-hours holds), that would be a fallback candidate for the spike. Otherwise these are references only.
