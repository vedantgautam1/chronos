# S23–S35, Part 1 — vectorbt (S32) and quantstats (S31): tests written before running (V2-D25 rule 2)

Written 2026-11-06 00:45 UTC, after reading the code and before running any test below.

**Batch (founder, 5 Nov):** S23 flowsurface, S24 Elenchev/order-book-heatmap, S25 CSharp-NT8-OrderFlowKit, S26 OrderflowChart, S27 Azhagesan-dev/OrderFlowMap, S28 Zipline (quantopian/zipline and stefan-jansen/zipline-reloaded), S29 RQAlpha, S30 pysystemtrade, S31 quantstats, S32 vectorbt, S33 machine-learning-for-trading, S34 FinRL, S35 gs-quant. Alpaca, Qlib (already S21) and OpenAlice were dropped by the founder. Done in four parts; this is Part 1.

| Item | Repo | Commit | Licence |
|---|---|---|---|
| S32 | polakowo/vectorbt | `c923f74c9e4d` (3 Nov 2026), v1.2.0 | Apache-2.0 + Commons Clause (no selling a product built mainly on it) |
| S31 | ranaroussi/quantstats | `d1a214fb906e` (2 Nov 2026), v0.0.86 | Apache-2.0 |

Both installed editable from those commits into one `uv` venv (Python 3.12, numpy 2.5.4, pandas 3.1.1, numba 0.68.1). Real data: Bitstamp BTC/USD (already in the workspace from the S19–S22 deep pass; MIT; ends 7 Jan 2025, before the 1 Apr 2026 seal). **Toy strategies only; their profits aren't evidence about anything and aren't trials of any Chronos hypothesis.**

Why these tests: VectorBT is the master doc's leaning choice for counted screening (§4 "Screening", COMPONENTS §1). Screening results must carry full venue costs (CLAUDE.md rule 3) and no look-ahead (rule 4), so fills, costs, stops, stats and speed decide whether it stays. quantstats is the library's candidate for reports and a possible cross-check for our ported statistics.

## vectorbt (S32)

- **V1 — its own test suite passes.** `pytest tests/` from the repo root, 40-minute cap. *PASS:* 0 failures and 0 errors; tests needing the network (data downloads) are listed separately.
- **V2 — fill timing.** Synthetic 1-hour candles; one entry signal on bar *t*.
  - (a) Defaults (close only): report the fill price. *Expected:* close of *t* (same bar).
  - (b) Next-bar pattern: entries shifted one bar, `price=open`. *PASS:* fill = open of *t+1* exactly.
- **V3 — costs, against hand calculations** (exact to 1e-9 relative):
  - (a) proportional fee 0.1% per side on a long round trip;
  - (b) fixed fee per order (stands in for a per-contract commission at 1 contract per order);
  - (c) a short round trip (`direction="shortonly"`) with both fees;
  - (d) funding: is there any native way to charge a funding rate per hour held? *Expected:* none in the open-source version; reported, not pass/fail.
- **V4 — stop fills.** Long entry at 100, `sl_stop=0.05`; the next bar opens at 90, its low is 88, and it closes back above 95.
  - (a) open/high/low passed. *PASS (realistic):* exit at 90 (the open).
  - (b) only close passed: report the exit price and bar.
  - (c) with `slippage=0.001` and the default stop exit mode: report whether slippage is applied to the stop exit. *Expected:* not applied (default "stoplimit").
- **V5 — stats.** A long position held through 500 synthetic hourly bars, `freq="1h"`. *PASS:* `pf.stats()` Sharpe equals mean/std(ddof=1)·√8760 of the portfolio's hourly returns, and Max Drawdown equals the hand value, both to 1e-9 relative. Also report what happens when `freq` isn't set.
- **V6 — speed.** 1,000 MA-crossover variants (fast × slow grid; fast < slow) on hourly Bitstamp BTC 2023-01-01 to 2024-12-31, 0.1% fees, next-bar-open fills, one `from_signals` call. *PASS:* indicators + portfolio + total return for all 1,000 in ≤ 60 s wall time on this 2-CPU machine. Peak memory reported. (freqtrade took 3.6 s for *one* such run, S20 B5.)
- **V7 — look-ahead in its indicators.** MA, EMA (`ewm=True`), MSTD, BBANDS, RSI and ATR on the same hourly series, full vs truncated at 200 random cut points (seeded). *PASS:* the value at each cut bar is identical (≤ 1e-9 relative) for every indicator. Warm-up: EMA-200 at the same bar with 500 vs 5,000 bars of prior history; the difference is reported (expected tiny but non-zero).
- **V8 — vectorbt vs quantstats.** The same hourly return series through both, annualised identically (365 × 24). *PASS:* Sharpe agrees to 1e-9 relative.

## quantstats (S31)

- **Q1 — its own test suite passes.** `pytest tests/`. *PASS:* 0 failures, 0 errors.
- **Q2 — metrics against textbook formulas.** Fixed daily returns (seed 20261105, n = 1,000, Student-t, df 4, scaled to 2% sd, mean 0.05%), `periods=365`. Definitions in the script:
  - Sharpe = mean / std(ddof 1) · √P;
  - Sortino = mean / √(Σ min(r,0)² / N) · √P;
  - volatility = std(ddof 1) · √P;
  - CAGR = (Π(1+r))^(P/N) − 1;
  - max drawdown on the wealth path including the starting value 1;
  - Calmar = CAGR / |MDD|.

  *PASS:* each within 1e-9 relative.
- **Q3 — does the annualisation setting reach every metric?** `reports.metrics(returns, periods_per_year=365, mode="full", display=False)` vs direct calls with `periods=365`. *PASS:* every annualised line in the report (CAGR, Sharpe, Sortino, volatility, Calmar, smart variants, PSR) matches its direct call to display rounding. Lines that don't are listed.
- **Q4 — Probabilistic Sharpe Ratio.** *PASS:* equals Bailey & López de Prado's formula Φ(SR / √((1 − γ₃·SR + (γ₄ − 1)/4 · SR²)/(n − 1))) using the same skew and kurtosis estimators, to 1e-9. Report the difference from population-moment estimates and what benchmark Sharpe it tests against.
- **Q5 — HTML tearsheet offline.** Returns only, no benchmark, under a socket guard. *PASS:* file written and 0 network attempts.
- **Q6 — hourly returns.** 2 years of hourly returns with `periods_per_year=8760`. Report whether the report resamples to daily, and whether Sharpe uses √8760.

## What would change the conclusions
- V2b, V3a–c, V4a, V5 and V8 failing would make VectorBT unfit as the screening engine without wrappers. V6 failing would remove its main reason to exist for us.
- V3d is known in advance to matter: if there's no native funding, screening costs need our own funding step on top. That's a design consequence for step 5, not a pass/fail.
- Q2–Q4 failing would rule quantstats out as a cross-check for our statistics; Q3 failing means it must always be called with explicit `periods`.
