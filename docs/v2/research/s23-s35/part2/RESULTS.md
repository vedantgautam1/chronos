# S23–S35, Part 2 — results: pysystemtrade (S30), Zipline (S28), RQAlpha (S29)

Run 6 Nov 2026 against the rules in `PREREGISTERED.md` (commit `bc851d8`, pushed before any test ran). Machine: 2 CPUs, Python 3.12 (except Z0). Each repo has its own `uv` venv. Toy strategies only: no profit figure here is evidence of anything.

## Summary

| Test | Result | One line |
|---|---|---|
| **P1** pysystemtrade suite | **PASS** | 103 pass, 0 fail, 40 skip (30 Windows-only, 10 need `--runslow`, 3 file-path variants), 3 xfail. The 10 slow example tests were then run with `--runslow`: 17 pass (154 s). None needed MongoDB, IB or the network. |
| **P2** 24/7 → business days | **PASS** (no move lost) | Friday's label holds **Sunday 23:00's** price, as expected. Saturday and Sunday labels don't exist. Sum of daily changes = 671 = sum of hourly changes. |
| **P3a** cost formula | **PASS** | 9.14 = 2 × 13.0 × 0.1 + 2 × 3.27, exact. |
| **P3b** costs inside a backtest | **FAIL** (as written) | System 6,849.36 vs hand 6,452.84 (+6.1%). Cause found (exploratory, below): two defaults. With both switched off the system gives **6,452.84, exact**. |
| **P4** sizing formula | **PASS** | Last date's subsystem position 7.14013582061782 vs hand 7.140135820617821 (forecast 4.93). Daily cash vol target 3,125 = 250,000 capital × 20% / 16 (the chapter-15 config's values). |
| **P5a** overrides | **PASS** | Reduce-only: growing → 0, shrinking → unchanged, flip −5 at +3 → **−3** (clipped to flat). Close → −3. No trading → 0. Float 0.5 on +2 at 3 → −1. |
| **P5b** trade limit | as expected: **clips** | 3/day, 2 used, proposed 5 → **1**. |
| **P5c** position limit | as expected: **clips** | limit 4, at 3, proposed +3 → **+1**. |
| **P6** back-adjustment | **PASS** | 26,900 of 26,900 hourly rows match (Dec 2017 – Mar 2024); 74 rolls; largest roll gap 965 points. |
| **P7** speed | report | BTC-only chapter-15 backtest: **0.72 s**. |
| **P8** IBKR config | report | `BITCOIN → MBT, CME, USD, 0.1` and `ETHER-micro → MET, CME, USD, 0.1` present (584 instruments). No Coinbase Derivatives contract. No funding concept anywhere in the code. |
| **Z0** original Zipline | **FAIL** (expected) | No Python 3.6/3.7 available through `uv`; on 3.8 `zipline==1.4.1` is unsatisfiable (needs `pandas<=0.22`, no wheels, metadata unparsable). Judged from reading only. |
| **Z1** zipline-reloaded suite | **PASS** | 3,313 pass, 0 fail, 17 skip, 5 xfail, 1 xpass (218 s). |
| **Z2** fill + costs | **PASS** | Order on day *t* fills on *t+1* at close × 1.0005 = 103.781865; commission $0.10. |
| **Z3** volume cap | as expected | 2,000 a day × 5 days = 10,000 (10% of volume). |
| **Z4** short round trip | **PASS** | P&L −145.5035 = hand, to 1e-12; slippage and commission on both fills. |
| **Z5** no peeking | **PASS** | 60 of 60 days: `history` and `current` end at close(*t*). |
| **Z6** 24/7 calendar | **FAIL** | Ingests, but the run crashes at the year end (`IndexError` in the metrics tracker). Works only with three workarounds (exploratory, below). |
| **Z7** speed | report | 1-year daily 24/7 run (with workarounds): **0.42 s**. |
| **R1** RQAlpha suites | **FAIL** (cause: data) | Unit: 103 pass, 6 fail, 18 error, 1 skip; integration: 9 pass, 93 fail, 17 error. Every failure and error is a missing data bundle. |
| **R2** data bundle | cannot download here | URL is plain HTTP (`http://bundle.assets.ricequant.com/bundles_v4/rqbundle_YYYYMM.tar.bz2`), no checksum, extracted with `tarfile.extractall` and no filter (`rqalpha/cmds/bundle.py` lines 132–133, 145). |
| **R3** risk validators | **reject** (by default) | `environment.py` `can_submit_order`: the first validator that returns a reason fails the order. But an opt-in backtest setting, `partial_fill_on_insufficient_cash`, removes the cash validator and lets the matcher fill part of the order instead: a clip, and only outside live trading (`rqalpha_mod_sys_risk/mod.py`). |

## Deviations from the pre-registration

1. **Timestamp.** `PREREGISTERED.md` says "Written 2026-11-06 05:45 UTC"; the commit is 05:35 UTC (00:35 −05:00). The header was a typo; the file was committed and pushed before any test ran.
2. **Z0 ran on Python 3.8, not 3.6.** `uv` offers no 3.6/3.7 build here. Result stands either way: it doesn't install.
3. **Z6 harness, two fixes before the recorded run** (both in comments in `s28_zipline_checks.py`):
   - the `24/7` calendar had to be passed to `run_algorithm` too, not just to the bundle;
   - start moved from 2 Jan to 3 Jan 2023 (it needs one prior session in the data).
   
   After both, the run still failed at the year end. That is the recorded result.
4. **RQAlpha test-only dependencies** (`mypy`, `TA-Lib 0.8.3`) were installed after the first collection errors. That changed nothing pre-registered.
5. **zipline-reloaded's pytest** needed `-o cache_dir=<temp>`: its `--ff` addopt conflicts with `-p no:cacheprovider`.

## Exploratory follow-ups (after the results; not pre-registered)

**P3b — where the extra 6.1% comes from.** pysystemtrade's defaults are `vol_normalise_currency_costs: True` and `multiply_roll_costs_by: 0.5`. The first rescales every trade's cost by the ratio of today's volatility to the average; the second adds roll "pseudo-trades" (equally spaced roll dates, average holding, half weight). With both switched off (`s30_pysystemtrade_checks.py`, follow-up 2), the account's total cost is 6,452.84, identical to the hand sum of commission plus spread on the 589 real position changes. (Follow-up 1 was my own wrong reconstruction of the roll term, 26,686; it is kept in `s30_results.json` but means nothing.)

So the per-trade formula is exact; the default *accounting* is not "the real venue's costs". With defaults on, a backtest's cost line is a smoothed estimate, which is defensible for Carver's purpose (comparing rules across decades) and breaks our hard rule 3 if borrowed as-is.

**Z6 — what makes 24/7 work** (`s28_z6_explore.py`). End 31 Dec: the beta calculation breaks (363 returns vs 362 benchmark rows). End 30 Dec: the cumulative-returns array is one short. With a **benchmark series of zeros covering every calendar day** passed as `benchmark_returns`, the run completes: 363 rows, all seven weekday names, 0.42 s. So zipline-reloaded handles 24/7 data only with three workarounds: calendar passed to the run, start one session after the data, own benchmark series.

## What this means against the pre-registered "what would change the conclusions"

- **pysystemtrade:** P3a, P4 and P6 pass, and P3b's gap is fully explained by documented defaults. So it stays usable **as a reference** for sizing and back-adjustment arithmetic. P5 clips, as expected: a design difference from our "block, don't clip" (V2-D40), not a bug.
  - It does **not** cover what Nautilus is meant to do:
    - it is a daily-frequency system (24/7 data folded into business days);
    - it has no funding concept, so Coinbase's perpetual-style nanos can't be costed properly;
    - it has no Coinbase Derivatives contract;
    - holds of minutes to hours are out of scope by design.
  
  Not a fallback candidate.
- **zipline-reloaded:** fills, costs, volume cap, shorts and no-peeking are correct. But it is equity-first, needs three workarounds for 24/7, and has no IBKR or futures execution path in the repo. Not a fallback candidate.
- **Original Zipline:** dead (doesn't install). Reading only.
- **RQAlpha:** its validators reject, which fits our design. But:
  - the licence is non-commercial;
  - its data is Chinese markets over plain HTTP with no checksum;
  - its backtest can be switched to clip while live rejects.
  
  Not a candidate.

No engine here passes the bar to be a Nautilus fallback.

## Files

- `PREREGISTERED.md`: rules, written before running.
- `s30_pysystemtrade_checks.py`, `s30_results.json`: P2–P7, plus follow-ups 1–2 (exploratory, labelled in the file).
- `s28_zipline_checks.py`, `s28_results.json`: Z2–Z6/Z7.
- `s28_z6_explore.py`, `s28_z6_explore.json`: Z6 follow-up (exploratory).
- `test_suites.json`: suite counts for P1, Z0, Z1, R1, R2.

Third-party code is not copied here (pysystemtrade is GPL-3.0); the scripts only import the installed packages.
