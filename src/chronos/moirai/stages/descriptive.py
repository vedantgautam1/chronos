"""descriptive.py — stage 4.10, Descriptive reporting (spec §4.10, NO GATES).

Everything here is computed and stamped into evidence; it influences no verdict. The
outcome always `passed=True` (a reporting-only stage) — this is the deliberate design
(spec §4.10 argues a regime GATE would be theater at this sample size).

Contents:
  - Regime tables: per-calendar-year performance (always), and above/below the
    200-day moving average of the asset price (only when >= 200 days of price history
    before the window are available; otherwise skipped with a note — you cannot form a
    200d MA on a window shorter than 200 days without the prior history).
  - Cross-asset trace (adopted descriptive-only): the identical rule on ETH/USDT H1,
    reported not gated; a SIGN FLIP vs BTC is worth a human look. Runs only when
    ETH/USDT data is cached AND the candidate strategy is symbol-agnostic; otherwise
    skipped with a note (the milestone MACrossover is symbol-bound, and ETH data is not
    ingested — both recorded honestly rather than faked).
  - Annualized translations (R3): Lo (2002) Eq. 22 AR(1)-corrected annualized Sharpe
    ALONGSIDE the naive sqrt(k) version, both labelled reporting-only; every annualized
    figure names its window (V and the bar both depend on it).
  - Turnover, profit factor, CAGR, Sortino, maxDD (Stage 0 Appendix A) — computed here
    because the engine computes no statistics.

This stage reads the asset price via the one Oceanus door (`get_bars`) for the 200d-MA
regime; it never catches `SealedDataError` (a sealed window must ERROR the verdict —
probe G7), only guards on availability with the read-only `available_range`.
"""

from datetime import timedelta

import numpy as np

from chronos.hephaestus.types import BacktestResult
from chronos.moirai import statistics as stats
from chronos.moirai.context import GauntletContext
from chronos.moirai.rerun import net_return, per_bar_sharpe
from chronos.moirai.round_trips import reconstruct_round_trips
from chronos.moirai.types import TestOutcome
from chronos.oceanus.access import available_range, get_bars

MOIRA_ID = "M4.10-descriptive"

_MA_DAYS = 200
_CROSS_ASSET_SYMBOL = "ETH/USDT"


def _returns_array(result: BacktestResult) -> np.ndarray:
    r = result.returns
    return np.asarray(r.to_list() if hasattr(r, "to_list") else list(r), float)


def _max_drawdown(equity) -> float:
    e = np.asarray(equity.to_list() if hasattr(equity, "to_list") else list(equity), float)
    if e.size == 0:
        return 0.0
    running_max = np.maximum.accumulate(e)
    dd = e / running_max - 1.0
    return float(-dd.min())


def _sortino(r: np.ndarray, periods_per_year: float) -> float:
    if r.size == 0:
        return 0.0
    downside = np.minimum(r, 0.0)
    dd_rms = np.sqrt(np.mean(downside ** 2))
    if dd_rms == 0.0:
        return 0.0
    return float(r.mean() / dd_rms * np.sqrt(periods_per_year))


def _profit_factor(trades) -> float | None:
    trips = reconstruct_round_trips(trades)
    gains = sum(rt.fractional_return for rt in trips if rt.fractional_return > 0.0)
    losses = sum(-rt.fractional_return for rt in trips if rt.fractional_return < 0.0)
    if losses == 0.0:
        return None  # no losing trips — profit factor is undefined (not "infinite gain")
    return float(gains / losses)


def _turnover(trades, initial_cash: float) -> float:
    if initial_cash <= 0.0:
        return 0.0
    notional = sum(float(f.qty_filled) * float(f.price) for f in trades)
    return float(notional / initial_cash)


def _per_year(returns_series) -> dict:
    """Per-calendar-year net return and per-bar Sharpe, from the return series' own
    UTC datetime index."""
    out: dict = {}
    if not hasattr(returns_series, "index"):
        return out
    for year, group in returns_series.groupby(returns_series.index.year):
        r = np.asarray(group.to_list(), float)
        out[str(int(year))] = {
            "bars": int(r.size),
            "net_return": float(np.prod(1.0 + r) - 1.0) if r.size else 0.0,
            "per_bar_sharpe": stats.per_bar_sharpe(r),
        }
    return out


def _above_below_200dma(result: BacktestResult, base_config) -> dict:
    """Split the window's per-bar returns by whether the asset close sat above or below
    its trailing 200-day MA. Needs 200 days of price history BEFORE the window; skipped
    (reporting-only) when that history is not on disk."""
    symbol = base_config.symbol
    timeframe = base_config.timeframe
    bar = timeframe.duration
    ma_bars = int(timedelta(days=_MA_DAYS) / bar)
    ext_start = base_config.start - timedelta(days=_MA_DAYS)
    coverage = available_range(symbol, timeframe)
    if coverage is None or coverage[0] > ext_start or coverage[1] < base_config.end:
        return {"available": False, "note": (
            f"need {_MA_DAYS} days of price history before {base_config.start.date()} to "
            "form the 200d MA; not on disk for this window — skipped (reporting-only).")}

    bars = get_bars(symbol, timeframe, ext_start, base_config.end)  # SealedDataError uncaught (G7)
    close = bars.set_index("open_time")["close"].astype(float)
    ma = close.rolling(ma_bars).mean()
    returns_series = result.returns
    above_r, below_r = [], []
    for ts, ret in returns_series.items():
        m = ma.get(ts)
        c = close.get(ts)
        if m is None or c is None or np.isnan(m):
            continue
        (above_r if c > m else below_r).append(float(ret))
    return {
        "available": True, "ma_period_bars": ma_bars,
        "above": _regime_stats(above_r), "below": _regime_stats(below_r),
    }


def _regime_stats(rs: list) -> dict:
    r = np.asarray(rs, float)
    return {"bars": int(r.size),
            "net_return": float(np.prod(1.0 + r) - 1.0) if r.size else 0.0,
            "per_bar_sharpe": stats.per_bar_sharpe(r)}


def _annualized(result: BacktestResult, base_config) -> dict:
    r = _returns_array(result)
    q = stats.HOURS_PER_YEAR  # hourly bars per year (H1)
    sr = per_bar_sharpe(result)
    rho = 0.0
    if r.size > 2 and r.std() > 0:
        rho = float(np.corrcoef(r[:-1], r[1:])[0, 1])
    naive = sr * np.sqrt(q)
    lo = sr * stats.lo_eta(int(q), rho)  # Lo (2002) Eq. 22, AR(1)-corrected
    lo_note = None
    if not np.isfinite(lo):
        # AR(1) aggregation is degenerate as |rho| → 1 (e.g. perfectly alternating
        # returns); fall back to the naive figure rather than report a non-finite one.
        lo, lo_note = naive, "AR(1) aggregation degenerate at |rho|≈1; fell back to naive"
    return {
        "reporting_only": True,
        "window": [base_config.start.isoformat(), base_config.end.isoformat()],
        "bars": int(r.size),
        "per_bar_sharpe": sr,
        "ar1_rho": rho,
        "annualized_sharpe_naive_sqrt_k": float(naive),
        "annualized_sharpe_lo_ar1": float(lo),
        "annualized_sharpe_lo_ar1_note": lo_note,
        "periods_per_year": q,
    }


def _cross_asset(ctx, base_config) -> dict:
    """The identical rule on ETH/USDT H1 (reporting-only). Runs only if ETH data is
    cached AND the candidate strategy is symbol-agnostic; otherwise skipped with a note.
    A sign flip vs BTC is worth a human look."""
    coverage = available_range(_CROSS_ASSET_SYMBOL, base_config.timeframe)
    strategy = ctx.candidate.strategy
    bound_symbol = getattr(strategy, "symbol", None)
    if coverage is None:
        return {"available": False, "note": (
            f"no {_CROSS_ASSET_SYMBOL} {base_config.timeframe.value} data cached; "
            "cross-asset trace skipped (reporting-only).")}
    if bound_symbol is not None and bound_symbol != _CROSS_ASSET_SYMBOL:
        return {"available": False, "note": (
            f"candidate strategy is bound to {bound_symbol!r}; a faithful cross-asset "
            f"trace needs a symbol-agnostic rule (or a rebound instance for "
            f"{_CROSS_ASSET_SYMBOL}). Skipped (reporting-only) — a Candidate-design "
            "question, deferred.")}
    from dataclasses import replace

    from chronos.moirai.rerun import rerun_candidate
    eth_config = replace(base_config, symbol=_CROSS_ASSET_SYMBOL)
    rr = rerun_candidate(ctx, eth_config)
    return {"available": True, "symbol": _CROSS_ASSET_SYMBOL,
            "net_return": net_return(rr.result),
            "per_bar_sharpe": per_bar_sharpe(rr.result),
            "wall_clock_s": rr.wall_clock_s}


class Descriptive:
    """Stage 4.10. moira_id matches configs/gauntlet/v001.json pipeline_order. NEVER
    gates — the outcome is always passed=True (reporting-only)."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        if ctx.candidate is None:
            raise ValueError(
                "stage 4.10 needs ctx.candidate for the cross-asset trace and window "
                "metadata; none was provided."
            )
        base_config = ctx.candidate.base_config
        r = _returns_array(result)
        initial_cash = float(base_config.initial_cash)
        years = (r.size / stats.HOURS_PER_YEAR) if r.size else 0.0
        equity = result.equity_curve
        e0 = float(equity.iloc[0]) if len(equity) else initial_cash
        e1 = float(equity.iloc[-1]) if len(equity) else initial_cash
        cagr = ((e1 / e0) ** (1.0 / years) - 1.0) if years > 0 and e0 > 0 else 0.0

        evidence = {
            "gates": "none — reporting-only stage (spec §4.10)",
            "regime_per_calendar_year": _per_year(result.returns),
            "regime_above_below_200d_ma": _above_below_200dma(result, base_config),
            "cross_asset_trace": _cross_asset(ctx, base_config),
            "annualized": _annualized(result, base_config),
            "metrics": {
                "net_return": net_return(result),
                "cagr": float(cagr),
                "max_drawdown": _max_drawdown(equity),
                "sortino_annualized": _sortino(r, stats.HOURS_PER_YEAR),
                "profit_factor": _profit_factor(result.trades),
                "turnover_x_initial_cash": _turnover(result.trades, initial_cash),
                "n_fills": len(result.trades),
                "n_round_trips": len(reconstruct_round_trips(result.trades)),
            },
        }
        cross = evidence["cross_asset_trace"]
        if cross.get("available"):
            btc_net = evidence["metrics"]["net_return"]
            evidence["cross_asset_sign_flip"] = bool(
                (cross["net_return"] > 0.0) != (btc_net > 0.0))

        return TestOutcome(moira_id=self.moira_id, passed=True, score=0.0,
                           evidence=evidence)
