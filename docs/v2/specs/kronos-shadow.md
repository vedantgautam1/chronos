> **Staleness note (3 Nov 2026) — read before using this spec.** Written 27 Oct, before V2-D27/D28.
> - Wherever it says **Kraken fees / Kraken costs**, use **IBKR crypto futures costs**: commission + exchange fees + spread + slippage + funding + futures–spot basis. Signals still come from Kraken spot data.
> - Its **1h/4h bars and horizons** must be re-checked against the intraday track (CHRONOS_V2 §12 O-8). The baseline strategy for role B is now S-INTRADAY / S-TREND.
> - Proposed (P-2): add a HAR realised-variance baseline for role C on intraday bars.
> - **5 Nov:** "2× costs" means frictions doubled, funding and basis at modelled values (V2-D35). The sealed holdout's single look is recorded in Mnemosyne by instrument + date range + lineage and an overlapping second look is refused (V2-D34). **The sealed holdout starts 1 Apr 2026 00:00 UTC (V2-D38)**, not "the last ~25%": dev and validation split the window from the cutoff to 31 Mar 2026.
> - "Matrix refs" below point to `claude/comparison-matrix.md` in the claude.ai Project.
> - Where this spec and `docs/v2/CHRONOS_V2.md` disagree, CHRONOS_V2 wins.

# Spec — Kronos shadow signal (v0.1, 27 Oct 2026)

**Status:** founder decided to implement Kronos (27 Oct 2026; Locked V2-D05). This spec is for a Claude Code session on the founder's Mac. It is engine-agnostic so it survives the NautilusTrader spike either way. Matrix refs: §19 (LLM/model in trading decision, level L1), §2 (trial accounting), §4 (sizing).

## Goal
Find out, with honest trial counting and after costs, whether Kronos forecasts add value to BTC trading in any of three roles:
- **A. Standalone direction signal** — trade when predicted return over horizon h exceeds a threshold.
- **B. Filter** — on a fixed baseline trend strategy (e.g. MA crossover), skip entries Kronos disagrees with.
- **C. Volatility forecast for sizing** — feed predicted volatility into the drawdown-budget sizing (§4). The paper's volatility claim (≈9% lower MAE) is its most defensible one [Likely], and this role needs no directional edge.

Kronos has **no order authority** in v0.1. It writes forecasts to a table; strategies read the table.

## Facts to confirm first (do not trust this spec on these — read the repo)
1. Read `github.com/shiyu-coder/Kronos` README and the `KronosPredictor` API. Expected: tokenizer + model + `max_context`, and `predict(df, x_timestamp, y_timestamp, pred_len, T, top_p, sample_count)` [Likely, unverified].
2. **Training cutoff of the exact checkpoint.** An independent review says pretraining ended June 2024 [Likely]. If the Hugging Face weights were re-released or updated later, the cutoff moves and the clean window shrinks. Record the checkpoint commit hash and its stated data end date. **Clean data = strictly after the cutoff.**
3. Licence: MIT per the model card [Likely]. Kronos-large is not public; use `Kronos-small` (24.7M) and `Kronos-base` (102.3M), context 512.
4. Device: check MPS (Apple GPU) support; fall back to CPU. Measure seconds per forecast at `sample_count` 1 and 10.

## Data
- **Instrument:** BTC/USD (Kraken). ETH/USD optional as a second test, counted as extra trials.
- **Bars:** 1h and 4h OHLCV (+ volume). Kronos also takes "amount" (quote volume) — compute it if the source lacks it.
- **Source:** Kraken's REST OHLC endpoint only returns a limited recent window [Likely]; use Kraken's downloadable historical trade/OHLCVT files for history and build bars locally. Store raw files immutable; bars as Parquet with `instrument_id`, `timestamp_utc`, `source`, `asset_class`.
- **Window:** cutoff+1 day → today. Split chronologically:
  - **Dev:** first ~45% (configuration choices only here)
  - **Validation:** next ~30%
  - **Sealed holdout:** last ~25% — touched once, at the end, for the final verdict.

## Forecast generation
- Rolling, strictly causal: at each bar close t, feed the last ≤512 bars ending at t; predict `pred_len` = h bars.
- Fixed seed per (timestamp, config); pin checkpoint hash, `T`, `top_p`, `sample_count`.
- Store one row per forecast: `run_id, config_id, checkpoint, ts_decision, horizon, pred_close_path_summary (mean/median/quantiles), pred_return, pred_vol, sample_dispersion, wall_time`.
- Cache everything — re-runs must not re-sample.

## Pre-registered configuration grid (every cell is a counted trial)
| Knob | Values |
|---|---|
| Model | small, base |
| Timeframe | 1h, 4h |
| Horizon h | 1 bar, 24 bars (1h) / 6 bars (4h) |
| sample_count | 10 (fixed; also log the N=1 forecast from the same draws) |
| Role | A, B, C |

That is 2 × 2 × 2 × 3 = **24 trials** before thresholds. Thresholds for A/B are chosen on Dev only and each threshold tried is a trial. Log all of them to the experiment store (SEARCH kind). No knob outside this table without a new pre-registration.

## Baselines (must be beaten, not zero)
- Random walk / zero-drift forecast (directional Brier, return RankIC = 0)
- Naive momentum forecast (sign of last h-bar return)
- For C: realised-vol (EWMA) and GARCH(1,1) volatility forecasts (both available in `arch`, see COMPONENTS)
- For B: the unfiltered baseline strategy

## Metrics
- Forecast: directional Brier vs random walk; RankIC of pred_return vs realised; vol forecast MAE/QLIKE vs EWMA and GARCH.
- Economic (A, B): net expectancy per trade after full costs (see staleness note), at 1× and 2× costs; trades count; max drawdown; DSR with the honest trial count.
- Sizing (C): realised portfolio vol vs target, drawdown vs budget, compared with EWMA sizing.
- Report the **N=1 vs N=10** difference (the review's main critique of the paper).

## Promote / drop rules (decided now, not after seeing results)
- **Promote to paper (shadow-live on the VPS):** validation net expectancy > 0 at 2× costs, beats its baseline, DSR ≥ 0.95 at the honest N, and the effect has the same sign in at least 2 of 3 validation sub-windows.
- **Drop:** fails the above → the role is removed; no further tuning on the same data.
- **Final verdict:** sealed holdout, once.
- Role C can be promoted independently of A/B.

## Deliverables
1. `kronos_adapter` module (load, forecast, cache, store rows).
2. Forecast backfill job over the clean window.
3. Evaluation notebook/script producing one report: trials table, baselines, metrics above, verdict per role.
4. Shadow-live job (later, on the VPS): forecast at each bar close, write to the table, no orders.

## Out of scope for v0.1
Fine-tuning (would need its own pre-registration and a later clean window), other assets, any order path.
