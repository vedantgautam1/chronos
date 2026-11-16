# S23–S35 Part 1 — vectorbt (S32) and quantstats (S31): results (5 Nov 2026)

Rules: `PREREGISTERED.md` (commit `acde253`, before anything ran). Scripts: `s32_vectorbt_checks.py`, `s31_quantstats_checks.py`. Raw output: `s32_results.json`, `s31_results.json`, `test_suites.json`. Python 3.12, vectorbt 1.2.0 and quantstats 0.0.86 installed editable from the commits in the pre-registration, numpy 2.5.4, pandas 3.1.1, numba 0.68.1. Two harness errors of mine were found after the first run and corrected (listed under V2 and Q3); no vectorbt or quantstats result changed because of them.

## Summary

| Test | Rule | Result | Verdict |
|---|---|---|---|
| **V1** vectorbt test suite | 0 failures/errors | 1,472 tests: **1,269 passed, 1 failed, 202 skipped**. Skips: 200 need the optional `vectorbt-rust` engine, 2 need `pandas-ta`. The failure is `test_to_timezone`: it expects `to_timezone("+05")` to raise, and with this pandas/zoneinfo it doesn't (a date utility, not backtest maths) | **FAIL** (1, utility) |
| **V2** fill timing | (a) report; (b) next-bar open exact | (a) default fills at the **signal bar's close**. (b) shifted signals + `price=open`: entry 102 = next open, exit 105 = next open | (a) reported; (b) **PASS** |
| **V3** costs | exact to 1e-9 | proportional fee, fixed per-order fee, short round trip: all exact. **Funding: no native parameter** in the open-source version | **PASS** (a–c); (d) none |
| **V4** stop fills | (a) gap fills at the open | (a) with open/high/low passed: exit at **90 (the open)**. (b) **close only: the stop never fired**; the bar that opened at 90 with a low of 88 closed at 96, so the trade stayed open. (c) the default stop exit **ignores the slippage setting** (exit 95.00, not 94.905) | (a) **PASS**; (b), (c) reported (optimistic) |
| **V5** stats | Sharpe, MDD = hand to 1e-9 | Sharpe 6.5551 = hand; MDD 5.3524% = hand. Without `freq`, Sharpe is **silently left out** of `stats()` (no error) | **PASS** |
| **V6** speed | 1,000 variants ≤ 60 s | 1,000 MA-crossover variants on 17,544 hourly BTC bars (2023–24), fees, next-open fills: **7.0–10.7 s** including first-time compile; portfolio alone **2.8 s** when compiled; peak memory **1.5 GB** | **PASS** |
| **V7** indicator look-ahead | 0 mismatches at 200 cut points | MA, EMA, MSTD, BBANDS, RSI, ATR: **0 mismatches** each. EMA-200 with 500 vs 5,000 bars of warm-up differs by 4.2e-5 relative (~$4 at $93k) | **PASS** |
| **V8** vs quantstats | Sharpe equal to 1e-9 | 6.555066842313936 in both | **PASS** |
| **Q1** quantstats test suite | 0 failures/errors | **225 passed**, 0 failed | **PASS** |
| **Q2** textbook formulas | each to 1e-9 | Sharpe, Sortino, volatility, CAGR, max drawdown, Calmar: all exact at `periods=365`. **Default `periods` is 252**: on daily crypto it reports Sharpe 0.42 instead of 0.50 and CAGR 8.5% instead of 12.5% | **PASS** (with explicit periods) |
| **Q3** periods reach every metric | report = direct to rounding | Sharpe, Sortino, smart variants, Calmar, PSR, CAGR, volatility all match at 365 | **PASS** |
| **Q4** PSR | formula to 1e-9 | 0.794230 = formula (same estimators); vs population moments 2.9e-6 apart. **Tests SR > 0 only**; no deflation for the number of trials | **PASS** |
| **Q5** HTML offline | file + 0 network | 591 KB tearsheet written; 0 network attempts | **PASS** |
| **Q6** hourly | report | Uses hourly returns as given: Sharpe −0.28 = √8760 version (−0.2843), not the daily-resampled one (−0.305) | Reported |

## Deviations and harness errors
- **V2b:** the first run's script expected the exit at 106 (bar 3's *close*); the rule is next-bar *open*, 105. vectorbt filled at 105 both times. Corrected in the script (commented) and rerun; the entry check was right both times.
- **Q3:** the first run compared report percentages with direct values ×100. With `display=False`, `reports.metrics` returns fractions (0.12, not 12.47). Corrected (commented) and rerun; every line matches.
- **V1/Q1** use the repos' own test command from their roots (not `-I`; see BUILD_NOTES §1).

## What the results mean for v2

**vectorbt (screening engine, Leaning):**
- Its maths is right (V3, V5, V7, V8) and it is fast enough for counted sweeps (V6: ~1,000 variants in seconds, against freqtrade's ~1 hour).
- Five of its defaults are **optimistic or silent**, and each must be fixed in a thin wrapper our screening code always goes through:
  1. **Same-bar-close fills** (V2a) → always shift signals one bar and fill at the next open.
  2. **Stops checked against the close only** unless open/high/low are passed (V4b): a bar that gapped to 90 and traded at 88 left the trade open → always pass OHLC.
  3. **Stop exits ignore slippage by default** (V4c) → use `stop_exit_price="stopmarket"` so slippage applies.
  4. **No funding** (V3d) → add funding per trade from the trade records (entry/exit time × size × hourly funding, V2-D39's adverse level in the stress run). Without it a screen breaks hard rule 3 ("no cost-free path") for perpetual-style contracts.
  5. **No `freq` → Sharpe silently missing** (V5); `year_freq` defaults to 365 days (right for crypto, wrong for equities later).
- **Memory:** 1.5 GB for 1,000 variants × 17,544 bars. At 5-minute bars (~12× more) a 1,000-variant grid would need roughly 12× the memory [Likely]: split grids into chunks.
- **Licence:** Commons Clause. Fine for our own research; Chronos code that depends on it can't be sold as a product [Certain — licence text].

**quantstats (reports, cross-check):**
- Correct formulas and an offline HTML tearsheet: usable for Argus's paper/live reports and as an independent cross-check in the known-answer tests for our ported Sharpe/Sortino/PSR.
- **Always pass `periods` (365 daily, 8760 hourly for crypto).** The 252 default silently misstates crypto results.
- Its PSR tests against SR = 0 only; DSR (deflation for the number of trials) is not in it, so v2 still ports DSR from v1.
