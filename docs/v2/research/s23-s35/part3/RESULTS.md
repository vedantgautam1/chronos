# S23–S35, Part 3 — results: gs-quant (S35), FinRL (S34), Machine Learning for Trading (S33)

Run 15–16 Nov 2026 against the rules in `PREREGISTERED.md` (commit `cb70a0a`, pushed before any test ran). Machine: 2 CPUs, Python 3.12 (3.13 for the two ML4T library suites, which `uv sync` built from their lockfiles). Each repo has its own venv. No profit figure here is evidence of anything.

## Summary

| Test | Result | One line |
|---|---|---|
| **G1** gs-quant suite | **FAIL** (as written) | 1,568 pass, 2 fail, 3 skip. The 2 failures aren't credentials or network: they're the close-market roll tests, which **fail only when the machine's time zone is New York/Toronto** (pass under UTC and London, exploratory rerun). |
| **G2** annualisation | **PASS** (formula) | Matches its formula exactly. On 365 calendar days of BTC it applies **252**: 36.65% annual vol instead of 44.11% (√365). Hourly data raises an error ("multiple data points on same date"). An `annualization_factor=365` argument exists and gives 44.11%. |
| **G3** mid-rank ties | **PASS** | 50.0, after a harness fix (below). |
| **G4** look-ahead clock | **FAIL** (predicted) | At 10:00 a request for 11:00 the same day is refused. A request for **today's date-keyed end-of-day price is returned** (2222.0): the guard compares dates for date-keyed data. |
| **G5** TWAP + cost | **FAIL** | TWAP = mean over **(start, end]**: start excluded, end included (656.5); not our half-open [start, end). The fixed per-unit transaction cost on `AddTradeAction` is **ignored** by the offline engine: 0.00 booked vs 5.00 set. |
| **G6** MCP server | report | 16 tools, all read-only: market data, Marquee dashboards/widgets, user lookups. No order tools. Doesn't start without Goldman Sachs credentials. Default bind 0.0.0.0 (all network interfaces). |
| **F1** FinRL suite | **FAIL** (as written, one item) | 69 pass, 7 fail (all Yahoo/Alpaca downloads: network), 1 collection error: an environment module imports `gym`, which FinRL's own install doesn't provide. It stops the whole run unless `--continue-on-collection-errors` is passed. |
| **F2** fill timing | **FAIL** (predicted) | Buys at the close shown in the observation the agent acted on (100.0, not the next bar's 110.0). |
| **F3** costs | **PASS** | Cash 1,000,097.90 and cost 2.10 = hand. |
| **F4** slice test | **PASS** | 0.0 difference in every column on days ≤ 600. |
| **F4b** survivorship | **FAIL** (predicted) | A ticker missing only on the last 10 days is **dropped from all 790 days**: future data decides the past universe. |
| **F5** crypto env | report | Fills at the **next** bar (better than the stock env). Fees exact. Whole units only (2 BTC, not 0.01). **Can't short.** No funding. The action scale depends on how the first price prints: 16547.5 → 1, 16547.500001 → 10⁻⁵. |
| **F6** PPO on noise | report: hypothesis formally met (in > out; out within 2 SE of 0), but not the way expected | 5 seeds, FinRL's PPO defaults, 20,000 steps. **Mean in-sample Sharpe −0.26, out-of-sample −0.48** (SE 0.29). Two seeds never traded (final value exactly 1,000,000; probably the deterministic actions truncate to 0 shares, not checked). The other three **lost in-sample too**. Within this budget it neither found nor faked an edge on noise; it paid costs. |
| **M1** ML4T library suites | **PASS** | ml4t-backtest 0.2.0: **3,162 pass, 0 fail**, 123 skip (29 need `ml4t-data`, 4 need a cross-framework flag, the rest optional). ml4t-diagnostic 0.2.1: **9,047 pass**, 997 skip (optional pyfolio/alphalens/empyrical/LightGBM, missing test data). 4 fail: browser tests where Plotly's script didn't load ("Plotly is not defined": no network to its CDN). 11 errors: install-index tests that build a wheel and can't fetch `hatchling`. |
| **M2.1** next-bar open | **PASS** | Signal at bar 0 → filled at bar 1's open (102). |
| **M2.2** fees both sides | **PASS** | 100,038.96 = hand. **Default commission and slippage are both none** (a warning is printed). |
| **M2.3** gap through stop | **PASS** | A STOP at 95 on a bar opening at 90 fills at **90**. The `StopLoss` rule does the same. |
| **M2.4** stop and target in one bar | **PASS** (documented) | Decided by the **order the rules are listed in** ("first non-HOLD wins"), not by price path. Stop first → 95; target first → **105** (optimistic). |
| **M2.5** funding | **PASS** | −0.01 exactly (long, rate +0.0001, mark 100). A funding event at the entry bar's own timestamp isn't charged (the fill comes after it). Funding **is** modelled; its LIMITATIONS.md says it isn't (stale doc). |
| **M2.6** control blocks | **PASS** | An order of 3 against `max_order_quantity=1` raises `TradingControlViolation`; no fill; position 0. Blocks, doesn't clip. |
| **M2.7** multiplier 0.01 | **PASS** | P&L 10.00 exactly. |
| **M2.8** 24/7 year | **PASS** | 8,592 of 8,592 hourly bars from a Saturday to a Saturday; 0.76 s. |
| **M3a** DSR, N = 1 | **FAIL** (as written) | Not the 2014 formula. It equals, to 0.0, the formula **with the Sharpe variance evaluated at the threshold (0)**, so **skewness and kurtosis are ignored** when testing against zero. v1 also uses T−1 where it uses T. |
| **M3b** DSR, N > 1 | report | Higher than v1 at N = 10 and 100 (e.g. 0.94 vs 0.82); lower at N = 1,000 (0.35 vs 0.44). |
| **M3c** rescaling table | **FAIL** (one K) | Exact to < 0.1% for K = 2, 5, 10, 100. **The table stops at 100**: for K = 1,000 it uses K = 100's value (0.429 vs true 0.351, 22% off). |
| **M3d** size under the null | **PASS** (both) | Rejection at 95%: **v1 (2014) 0.0%**, **ml4t 2.6%** (2,000 worlds, K = 20); limit 5.97%. Its raw-returns API: 2.8% (first 500 worlds). |
| **M4** RAS | **(a) FAIL, (b) PASS** (predicted) | Usage as in its docstring: **500 of 500 pure-noise worlds** had a "significant" strategy. Standardised usage: 0 of 500. |
| **M5** White's Reality Check | **PASS** | 4.4% rejection (limit 6.95%). Tie rule: p = mean(null ≥ statistic), no +1; not mid-rank. |
| **M6** purged walk-forward | **PASS** | 0 overlaps in 5 folds; 5 rows purged before each test block. |
| **M7** ml4t-live IBKR | report | `IBBroker` builds `Stock('MBT', 'SMART', 'USD')`: **US stocks only, no futures.** Defaults include dollar limits ($50k position, $10k order, $5k daily loss). Kill switch off. A startup reconciliation mismatch **doesn't block trading** by default. |
| **M8** ml4t-data providers | report | 35 modules (Binance, OKX, Databento, Polygon, FRED…). **No Kraken, no Coinbase, no IBKR.** |
| **M9** book's crypto case study | report (read) | Binance perps, 2 bps maker / 4 bps taker. **Best of 2,807 candidates**: validation Sharpe 1.67. **Deflated Sharpe at raw K: −0.13. Holdout: Sharpe −0.83, CAGR −44.8%, max drawdown −82%** (stored notebook outputs). |

## Deviations from the pre-registration

1. **Timestamp.** The header says "~00:15 UTC"; the commit is 00:09:52 UTC (19:09:52 −05:00). It was pushed before any test ran.
2. **G3 harness fix.** The first run passed `y` as a single point. The window then defaults to len(y) = 1, so 2 was ranked against [3] only and gave 0.0. The function's own docstring says the window defaults to the series length. Rerun with `y` on the same 5 dates: 50.0. Both runs are kept in `s35_results.json` (`first_run_harness_errors`).
3. **G5 harness.** The first run only recognised inclusive and [start, end) bounds, so it labelled the fill "other". The code uses (start, end] (`data_sources.py`). The fill value didn't change; the classification was added. The cost part failed in both runs.
4. **G6.** The script ran `discover-tools`. Starting the server (127.0.0.1, no credentials) was done by hand and recorded in the same JSON.
5. **Test-only installs after setup:** `pyarrow` (gs-quant venv, to read our BTC file), gs-quant's `[mcp]` extra, `pytest` (FinRL's install doesn't include it). The ML4T library suites ran in venvs built by `uv sync --frozen` from their own lockfiles (Python 3.13).
6. **ml4t-backtest suite:** the first attempt passed `-o cache_dir=...`, which its strict config rejects ("Unknown config option"). Rerun without it.
7. **F1:** `--continue-on-collection-errors` was added so one bad import doesn't hide the other 76 results. No test was changed.
8. **M2 harness:** the first run built price columns from mixed ints/floats and Polars refused them. Prices were cast to float; no rule changed.
9. **F6 prices:** "zero-drift" was implemented as a martingale: log-returns N(−σ²/2, σ²), so the expected price change is zero.
10. **Time zone.** Everything ran with `TZ=America/Toronto` (this session's setting). It matters for G1 (below).

## Exploratory follow-ups (after the results; not pre-registered)

**G1: the 2 failures are time-zone-dependent.** Rerunning `test_close_market.py` gives:

| `TZ` | Result |
|---|---|
| UTC | 3 pass |
| Europe/London | 3 pass |
| America/New_York | 2 fail |

gs-quant's close-market roll reads the machine's local clock. Lesson for us: run every Chronos process with `TZ=UTC`.

**F4: a prefix test** (`s34_f4_prefix_explore.py`). The slice test can't see a leak *inside* the cut window. FinRL's `preprocess_data` ends with `df.ffill().bfill()` over the whole frame sorted by (date, ticker). Computing features on data up to day *t* and comparing row *t* with the full run, at 16 values of *t*:
- 15 of the 16 match.
- Day 0 doesn't. Six features (Bollinger bands, RSI, CCI, DX, daily return) are back-filled from a later row, and the value is **identical for all three tickers**. Ticker BBB, priced ~50, gets an upper Bollinger band of 101.35: AAA's level.

So the fill leaks across time and across tickers. Here it only touched the warm-up row.

The first version of this comparison ignored NaN-vs-number differences and reported no difference; it was fixed before reading any conclusion from it.

## What this means against "what would change the conclusions"

### ML4T: ml4t-backtest

M2.1–M2.8 all pass. It is a correct bar engine for our cases, including:
- funding;
- the 0.01 multiplier;
- gap-through stops;
- blocking controls;
- a 24/7 year.

That makes it the strongest **third opinion** we've tested for the spike's fill tests (better than zipline-reloaded: it has funding, futures multipliers and 24/7). It also ships cross-framework parity evidence against VectorBT, Backtrader, Zipline and LEAN (not Nautilus).

**It does not replace Nautilus:**
- its live half (ml4t-live) can only build US-stock contracts through IBKR (M7);
- live and backtest are pinned to different versions;
- live's defaults keep trading through a reconciliation mismatch.

### ML4T: ml4t-diagnostic

- **White's Reality Check** passes size.
- **Purged walk-forward** is correct.
- **DSR (2025 form)** passes size and is less conservative than v1 (2.6% vs 0.0% rejections under the null; power wasn't measured). But:
  - it ignores skew/kurtosis against a zero benchmark;
  - its rescaling table stops at K = 100 (our sweeps run to thousands).
  
  So it is **not a drop-in for v1's DSR**; it is a useful second opinion if those two are handled.
- **RAS** is unsafe as documented: 100% false finds on noise. It's fine standardised.

### gs-quant

G4 fails: the clock guard has a date-keyed hole. The guard *pattern* is worth copying, with timestamp-level availability (`available_at`), never date-level. Its maths functions default to 252 days.

### FinRL

F2 and F4b fail as predicted, plus the cross-ticker fill:
- same-bar fills (stock env);
- survivorship (a future gap deletes a ticker's whole past);
- long-only, whole-unit, no-funding crypto env;
- its own reported Sharpe uses √252.

Not a usable research harness for us.

## Files

- `PREREGISTERED.md`: rules, before running.
- gs-quant: `s35_gsquant_checks.py`, `s35_results.json`.
- FinRL:
  - `s34_finrl_checks.py`, `s34_results.json`;
  - `s34_f4_prefix_explore.py`, `s34_f4_prefix_explore.json` (exploratory);
  - `s34_f6_rl_noise.py`, `s34_f6_results.json`.
- ML4T:
  - `s33_ml4tbt_checks.py`, `s33_bt_results.json`;
  - `s33_ml4tdiag_checks.py`, `s33_diag_results.json` (v1's DSR reproduced inside the script);
  - `s33_ml4tlive_checks.py`, `s33_live_data_results.json`.
- `test_suites.json`: suite counts for G1, F1, M1.

No third-party code is copied here. The scripts only import the installed packages.
