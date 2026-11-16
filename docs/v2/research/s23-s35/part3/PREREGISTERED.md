# S23–S35, Part 3 — pre-registered tests: gs-quant (S35), FinRL (S34), Machine Learning for Trading (S33)

Written 2026-11-16 ~00:15 UTC, committed and pushed **before any test below runs**. The commit time is the record.

## What was done before this file (setup only, no tests)

- Clones (shallow) and installs. Each repo has its own `uv` venv on Python 3.12.
- Reading code to decide what to test. Several predictions below come from that reading and are marked **(read)**. A test whose result I predict from reading still has to run; a correct prediction isn't a pass.
- Two facts were seen during setup and are recorded here as **observed before pre-registration**, not as test results:
  1. **ML4T's libraries:** the latest versions of the five libraries can't be installed together. `ml4t-live` 0.1.3 needs `ml4t-specs` < 0.2; `ml4t-diagnostic` 0.2.1 needs ≥ 0.2.1. Also, `ml4t-live` 0.1.3 pins `ml4t-backtest` 0.1.12 while the latest is 0.2.0. So I use two venvs: one for backtest/diagnostic/engineer/data, one for live.
  2. **FinRL:** its documented install (`pip install -e .`, which pulls ray, wrds, selenium, torch 2.15 and others) completed in a fresh 3.12 venv.

## Pinned versions

| Item | Source | Commit / version |
|---|---|---|
| S35 | goldmansachs/gs-quant | `8725ddf2ce4b` (6 Nov 2026, release 2.2.5), Apache-2.0 |
| S34 | AI4Finance-Foundation/FinRL | `7e98df461cbc` (25 Oct 2026), MIT; PyPI `finrl` 0.3.7 is from Apr 2024 |
| S33 | stefan-jansen/machine-learning-for-trading | `457a6f95bba7` (12 Nov 2026), MIT, 3rd edition |
| S33 libs | ml4t/backtest | tag v0.2.0 = `45becfb0985e` (PyPI 0.2.0) |
| | ml4t/diagnostic | tag v0.2.1 = `166b2a8c9be3` (PyPI 0.2.1) |
| | PyPI only | ml4t-engineer 0.2.1, ml4t-data 0.3.1, ml4t-live 0.1.3 (+ its pinned ml4t-backtest 0.1.12) |

**Data:**
- Bitstamp BTC/USD 5-minute bars 2023–2024 (pre-seal; V2-D38), resampled where stated.
- Synthetic series with seeds fixed in the scripts.

**Not tested:**
- Anything needing Goldman Sachs credentials, Binance downloads, Yahoo, WRDS or a live IB Gateway (none reachable or available here).
- FinRL-X (a separate repo the FinRL README now points to). It isn't in the founder's list.

Same rules as before:
- No seed shopping: every seed listed is run and reported.
- A test that can't run is reported as not run, with the reason.

---

## S35 — gs-quant

| Id | Test | Pass rule |
|---|---|---|
| **G1** | Repo test suite `pytest gs_quant/test` from the repo root, venv `[test]` extras | PASS if every failure or error needs GS credentials, the network or a missing optional dependency (each listed). Otherwise FAIL, listing the rest. |
| **G2** | `gs_quant.timeseries.volatility` on 2023 BTC daily closes (365 calendar days) and on hourly closes | PASS if it equals the hand formula from its own docstring to 1e-9. Record the annualisation factor it applies. **Prediction (read):** 252 on calendar-daily data (understates annual vol by √(252/365) ≈ 0.83); hourly data raises an error. |
| **G3** | `percentiles` with ties: x = [1, 2, 2, 2, 3], score 2 | PASS if 50.0 (mid-rank: (1 + 0.5 × 3) / 5 × 100), as V2-D21 requires. |
| **G4** | Look-ahead guard in the offline `PredefinedAssetEngine`. A trigger at 10:00 on day *t* asks the data handler for (a) a price at 11:00 the same day, (b) day *t*'s date-keyed (end-of-day) price | PASS if both are refused. FAIL if either is returned. **Prediction (read):** (a) refused, (b) returned (FAIL): the guard compares dates for date-keyed data. |
| **G5** | TWAP fill and cost on 1-minute synthetic data: TWAP 10:00–10:30, fixed per-unit cost | PASS if the fill equals the mean of the fixings over the bounds the code uses (recorded: inclusive or half-open) and the cost is exactly qty × unit cost. |
| **G6** | Its MCP server started offline (local auth, no credentials) | Report only: does it start, how many tools, and does any tool place or modify orders? |

## S34 — FinRL

| Id | Test | Pass rule |
|---|---|---|
| **F1** | `pytest unit_tests` from the repo root | PASS if every failure or error needs the network, credentials or an optional dependency (listed). |
| **F2** | Fill timing in `StockTradingEnv`. One synthetic ticker; buy at step *t* | PASS if the fill uses a price the agent hadn't seen (bar *t+1*). FAIL if it fills at the close in the observation it acted on. **Prediction (read):** FAIL (same-bar fill). |
| **F3** | Costs: buy then sell with `buy_cost_pct = sell_cost_pct = 0.001` | PASS if cash, shares and `env.cost` equal hand values to 1e-9. |
| **F4** | Slice test (BUILD_NOTES §1) on `FeatureEngineer`: default indicators + `daily_return` + turbulence, synthetic 3-ticker daily data, 800 days. Features computed on data cut at day 600 vs on the full data, compared on days ≤ 600 | PASS if every column agrees to 1e-9. Any larger difference = look-ahead. |
| **F4b** | Survivorship: ticker C is missing only on the last 10 days | PASS if C stays in the history where it has data. FAIL if `clean_data` drops C from every date (future data decides the past universe). **Prediction (read):** FAIL. |
| **F5** | Crypto env (`env_multiple_crypto`) on synthetic 2-asset data | Report only: can it short; are fees charged (hand-checked); is funding modelled? |
| **F6** | Reinforcement learning on pure noise. Seeds 0, 1, 2, 3, 4 (all reported). Each seed: 3 tickers, zero-drift geometric random walk, daily vol 3%, 1,500 days. PPO with FinRL's `DRLAgent` defaults, 20,000 timesteps, trained on days 0–999, costs 0.1% a side. Deterministic policy evaluated on days 0–999 (in-sample) and 1,000–1,499 (out-of-sample), plus equal-weight buy-and-hold on both | No pass/fail for FinRL; a demonstration. **Hypothesis:** mean in-sample Sharpe > mean out-of-sample Sharpe, and out-of-sample mean within ±2 standard errors of 0. Annualised with √365. If torch fails at run time, F6 is reported not run. |

## S33 — Machine Learning for Trading (book code + its libraries)

| Id | Test | Pass rule |
|---|---|---|
| **M1** | Test suites of ml4t-backtest v0.2.0 and ml4t-diagnostic v0.2.1, from each repo root | PASS if failures are only network or optional-dependency. Record the counts. |
| **M2.1** | ml4t-backtest 0.2.0, defaults (NEXT_BAR, OPEN), synthetic bars: signal on bar *t* | PASS if it fills at the open of bar *t+1*. |
| **M2.2** | Fees both sides (percentage commission) | PASS if cash matches the hand value to 1e-9. |
| **M2.3** | Gap through stop: long, stop 95, next bar opens 90, high 99 | PASS if it fills at 90 (the open), not 95. |
| **M2.4** | One bar hits both stop and target | Report which fills. PASS if deterministic and stop-first, or the rule is documented. |
| **M2.5** | Funding: long 1 unit, mark 100, rate +0.0001 at a funding timestamp | PASS if cash changes by exactly −0.01 (longs pay a positive rate). Record whether funding at the entry bar's own timestamp is charged. Also settles a doc contradiction: LIMITATIONS.md says funding isn't modelled, but the engine takes `funding_df`. |
| **M2.6** | Control: `max_order_quantity = 1`, order of 3 | PASS if the order is blocked and the position stays 0 (block, not clip, V2-D40). |
| **M2.7** | Multiplier 0.01 (one nano BTC contract): 1 contract, 30,000 → 31,000 | PASS if P&L = 10.00 exactly. |
| **M2.8** | 24/7: BTC hourly, Sat 7 Jan 2023 00:00 to Sat 30 Dec 2023 23:00, sessions not enforced | PASS if it completes and values every input bar. Record the runtime. |
| **M3a** | DSR, N = 1: ml4t-diagnostic's `deflated_sharpe_ratio_from_statistics` vs the 2014 formula by hand (and v1 `statistics.dsr`) on a grid of SR, T, skew, kurtosis | PASS if ml4t equals the hand formula to 1e-12, with any T vs T−1 convention identified and stated. |
| **M3b** | DSR, N > 1 | Report the ratio to v1's DSR. Identify the source of the difference: **(read)** a √V[max of N normals] rescaling of the SR variance. |
| **M3c** | ml4t's tabulated rescaling factors vs Monte Carlo √Var(max of K iid N(0,1)), 10⁶ draws, K ∈ {2, 5, 10, 100, 1000} | PASS if each is within 0.5%. |
| **M3d** | Size under the exact null. 2,000 worlds; each 20 zero-mean strategies, T = 500 normal daily returns. Pick the best SR; DSR with V = that world's cross-trial SR variance; "reject" if DSR > 0.95. Rejection rate for v1 (2014) and ml4t (2025) | PASS for a method if the rate is ≤ 0.0597 (5% + 2 SE). |
| **M4** | RAS false positives. 500 null worlds, N = 100 strategies, T = 252, returns N(0, 0.01²). (a) Usage as in its docstring: complexity on raw returns, annualised Sharpe. (b) Standardised: returns / column σ, per-period Sharpe. δ = 0.05 | PASS for a usage if the share of worlds with ≥ 1 "significant" strategy is ≤ 0.0695 (δ + 2 SE). **Prediction (read):** (a) FAIL, (b) PASS. |
| **M5** | White's Reality Check size. 500 null worlds, 20 strategies N(0, 0.01²), zero benchmark, T = 500, 500 bootstrap draws | PASS if the rejection rate at p < 0.05 is ≤ 0.0695. Record its tie rule against V2-D21 (mid-rank). |
| **M6** | Purged walk-forward: `WalkForwardCV(label_horizon=5)`, 1,000 sequential rows | PASS if, across all folds, no training row *i* has [i, i+5) overlapping its fold's test rows. |
| **M7** | ml4t-live 0.1.3: what contract its `IBBroker` builds for "MBT" (offline, no connection) | Report. **(read)** Only US stocks (`Stock(asset, "SMART", "USD")`). Also record the default risk limits and what a startup reconciliation mismatch does by default. |
| **M8** | ml4t-data 0.3.1 providers | Report whether any covers Kraken, Coinbase Derivatives or IBKR (step 4's sources). |
| **M9** | The book's crypto-perps case study | Report only (its data is Binance, unreachable here): venue, costs and funding treatment, holdout design, and its stated holdout result. |

## What would change the conclusions

- **ML4T:** if M2.1–M2.8 all pass, ml4t-backtest is a correct bar engine with funding and multipliers. It would then be a candidate third opinion for the spike's fill tests, or a fallback if Nautilus fails. It would **not** replace Nautilus while ml4t-live can't trade futures through IBKR (M7).
  - If M3–M5 pass, ml4t-diagnostic can be a second opinion in our known-answer tests (V2-D25), as quantstats is.
  - A method that fails its size test is **not** adopted.
- **gs-quant:** if G4 passes, its clock guard is a design to copy for Hephaestus/Nautilus data access. If it fails, record the date-keyed hole as a trap.
- **FinRL:** if F2, F4 and F4b pass, its environments are a usable research harness. If not, it stays out and the traps go to BUILD_NOTES.
