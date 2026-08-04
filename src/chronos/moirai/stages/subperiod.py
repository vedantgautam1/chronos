"""subperiod.py — stage 4.8, Sub-period stability ("walk-forward," named honestly)
(spec §4.8, R4).

Split the research window into K contiguous, non-overlapping, year-long
(`subperiod.window_months`) half-open sub-windows — an exact partition, no gap, no
overlap, last window possibly short — and re-run the fixed candidate on each
(`kind=VERIFICATION`, via the shared `rerun_candidate` helper), then aggregate.

Three gates:
  (i)   per-bar Sharpe strictly positive in >= `subperiod.positive_sharpe_frac` of
        the windows;
  (ii)  the pooled mean of the per-window mean returns is > 0 with a one-sided HAC t >
        `subperiod.hac_t_threshold`, Newey-West at lag m per D-R4-m (m = ceil(K^(1/3)),
        consumed from statistics.py — no HAC math here), sensitivity bracket {m/2, 2m}
        in evidence;
  (iii) no single window contributes more than `subperiod.max_single_window_pnl_frac`
        of total net PnL (an edge that is one window is a regime artifact wearing a
        full-period costume).

**Gate (ii) is an OPEN, UNRATIFIED methodology decision — NOT validated (founder,
2026-08-04; for the quant to ratify at v002/Phase 6).** As built it applies Newey-West
to the K per-window MEAN returns (T = K, m = ceil(K^(1/3))) — the literal spec wording
"pooled mean of per-window mean returns." Two forms, both flawed, neither ratified:
  - *per-window means (as built):* at K≈6 the HAC t rests on ~6 points — Newey-West is
    near-empty there and cannot really do its job.
  - *pooled per-bar returns (the more-powered alternative, deliberately NOT adopted):*
    a HAC t on the concatenated per-bar returns has T = full bar count, but each
    sub-window is re-run fresh, so concatenation splices K−1 warmup-reset SEAMS into the
    series — manufacturing autocorrelation artifacts exactly where NW reads them. For a
    project whose whole point is not fooling itself, that contamination is the worse
    failure, so the powered-but-contaminated form is not silently defaulted to.
  The v002 action is to have the quant pick a form AND calibrate the threshold; until
  then gate (ii) is reported but treated as provisional (evidence stamps its status).
  The {m/2, 2m} bracket, gate (i), and gate (iii) stand as built.

Other interpretation notes:
  - Gate (iii) share = window PnL / total net PnL; when total net PnL <= 0 there is no
    positive edge to concentrate, so (iii) passes with a note (the loss is caught by
    the other gates and by 4.3/4.5).
  - K < 2 → sub-period stability is unjudgeable (HAC needs >= 2 windows); the stage
    returns a non-pass `insufficient_subperiods` rather than a meaningless verdict.

v001-vs-spec key drift (v002 reconciliation, recorded): spec §4.8 uses `wf.*`; v001
ships `subperiod.window_months` / `subperiod.positive_sharpe_frac` /
`subperiod.hac_t_threshold` / `subperiod.max_single_window_pnl_frac`. v001 is the frozen
hashed judge; the stage binds to its actual names.

**N-laundering warning (binding on all future sessions):** if any future variant of this
stage introduces per-window parameter selection, every inner evaluation is `SEARCH`
under its own registered hypothesis and DSR charges the inner N. Window boundaries do
not reset trial accounting. This sentence exists because the path from "walk-forward" to
hidden search is exactly one lazy implementation away.

Kind accounting: K × VERIFICATION (never toward N).
"""

from dataclasses import replace

import numpy as np
from dateutil.relativedelta import relativedelta

from chronos.hephaestus.types import BacktestResult
from chronos.moirai import statistics as stats
from chronos.moirai.context import GauntletContext
from chronos.moirai.rerun import net_return, per_bar_sharpe, rerun_candidate
from chronos.moirai.types import TestOutcome

MOIRA_ID = "M4.8-subperiod"

_WINDOW_MONTHS_KEY = "subperiod.window_months"          # spec: wf.window_months (v002)
_POSITIVE_FRAC_KEY = "subperiod.positive_sharpe_frac"   # spec: wf.min_positive_frac (v002)
_HAC_T_KEY = "subperiod.hac_t_threshold"                # spec: wf.hac_t_min (v002)
_MAX_PNL_FRAC_KEY = "subperiod.max_single_window_pnl_frac"  # spec: wf.max_window_pnl_frac (v002)


def _partition(start, end, months: int) -> list[tuple]:
    """Contiguous half-open [s, e) sub-windows of `months` each, exactly covering
    [start, end): no overlap, no gap, last window short if the span isn't a multiple."""
    windows = []
    cursor = start
    while cursor < end:
        nxt = min(cursor + relativedelta(months=months), end)
        windows.append((cursor, nxt))
        cursor = nxt
    return windows


def _nw_lag(k: int) -> int:
    """D-R4-m: m = ceil(k^(1/3)), floored at 1. T is the series length (here K)."""
    return max(1, int(np.ceil(k ** (1.0 / 3.0))))


def _hac_t(window_means: np.ndarray, m: int) -> float | None:
    """One-sided HAC t that the mean of `window_means` is > 0: mean·sqrt(T)/sqrt(S),
    S = Newey-West long-run variance (statistics.newey_west; m capped at T−1). None if
    fewer than two points; 0.0 for a degenerate (non-positive) variance."""
    x = np.asarray(window_means, float)
    T = x.size
    if T < 2:
        return None
    m_eff = max(0, min(int(m), T - 1))
    s_hat = stats.newey_west(x, m_eff)
    if s_hat <= 0.0:
        return 0.0
    return float(x.mean() * np.sqrt(T) / np.sqrt(s_hat))


class SubPeriod:
    """Stage 4.8. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        if ctx.candidate is None:
            raise ValueError(
                "stage 4.8 needs ctx.candidate (strategy + base config + hypothesis) "
                "to re-run each sub-window; none was provided."
            )
        base_config = ctx.candidate.base_config
        months = int(ctx.config.thresholds[_WINDOW_MONTHS_KEY])
        min_pos_frac = ctx.config.thresholds[_POSITIVE_FRAC_KEY]
        hac_t_threshold = ctx.config.thresholds[_HAC_T_KEY]
        max_pnl_frac = ctx.config.thresholds[_MAX_PNL_FRAC_KEY]
        initial_cash = float(base_config.initial_cash)

        windows = _partition(base_config.start, base_config.end, months)
        per_window: list[dict] = []
        wall_clocks: list[float] = []
        sharpes: list[float] = []
        window_means: list[float] = []
        window_pnls: list[float] = []
        for (s, e) in windows:
            modified = replace(base_config, start=s, end=e)
            rr = rerun_candidate(ctx, modified)
            wall_clocks.append(rr.wall_clock_s)
            returns = rr.result.returns
            r = np.asarray(returns.to_list() if hasattr(returns, "to_list")
                           else list(returns), float)
            sr = per_bar_sharpe(rr.result)
            nr = net_return(rr.result)
            pnl = initial_cash * nr
            sharpes.append(sr)
            window_means.append(float(r.mean()) if r.size else 0.0)
            window_pnls.append(pnl)
            per_window.append({
                "start": s.isoformat(), "end": e.isoformat(),
                "per_bar_sharpe": sr, "mean_return": window_means[-1],
                "net_return": nr, "net_pnl": pnl,
                "config_hash": rr.result.config_hash,
                "data_snapshot_hash": rr.result.data_snapshot_hash,
                "wall_clock_s": rr.wall_clock_s,
            })

        k = len(windows)
        evidence: dict = {
            "n_windows": k,
            "window_months": months,
            "per_window": per_window,
            "positive_sharpe_frac_threshold": min_pos_frac,
            "hac_t_threshold": hac_t_threshold,
            "max_single_window_pnl_frac": max_pnl_frac,
            "run_wall_clock_s": wall_clocks,
            "kind_accounting": f"{k} × VERIFICATION (never toward N)",
            "n_laundering_note": (
                "fixed-parameter re-run only; no per-window selection. If a future "
                "variant selects parameters per window, every inner eval is SEARCH "
                "under its own hypothesis and DSR charges the inner N — window "
                "boundaries do not reset trial accounting (spec §4.8)."),
        }

        if k < 2:
            evidence["reason"] = "insufficient_subperiods"
            evidence["insufficient_note"] = (
                f"only {k} sub-window(s) fit [{base_config.start.date()}, "
                f"{base_config.end.date()}) at {months}-month windows; sub-period "
                "stability and its HAC t need >= 2 windows. Unjudgeable — does not pass.")
            return TestOutcome(moira_id=self.moira_id, passed=False, score=0.0,
                               evidence=evidence)

        # Gate (i): per-bar Sharpe positive in enough windows.
        arr = np.asarray(sharpes, float)
        pos_count = int(np.sum(arr > 0.0))
        pos_frac = pos_count / k
        gate_i = pos_frac >= min_pos_frac

        # Gate (ii): pooled mean of per-window means > 0 with one-sided HAC t.
        means = np.asarray(window_means, float)
        pooled_mean = float(means.mean())
        m = _nw_lag(k)
        hac_t = _hac_t(means, m)
        hac_t_half = _hac_t(means, max(0, m // 2))
        hac_t_double = _hac_t(means, 2 * m)
        gate_ii = bool(pooled_mean > 0.0 and hac_t is not None
                       and hac_t > hac_t_threshold)

        # Gate (iii): no single window dominates total net PnL (only when total > 0).
        total_pnl = float(np.sum(window_pnls))
        if total_pnl > 0.0:
            shares = [p / total_pnl for p in window_pnls]
            max_share = max(shares)
            gate_iii = max_share <= max_pnl_frac
        else:
            shares = [None for _ in window_pnls]
            max_share = None
            gate_iii = True  # no positive edge to be concentrated

        passed = bool(gate_i and gate_ii and gate_iii)
        evidence.update({
            "positive_sharpe_windows": pos_count,
            "positive_sharpe_frac": pos_frac,
            "gate_i_positive_sharpe": gate_i,
            "pooled_mean_return": pooled_mean,
            "nw_lag_m": m,
            "hac_t": hac_t,
            "hac_t_bracket": {"m_half": {"m": max(0, m // 2), "hac_t": hac_t_half},
                              "m_double": {"m": 2 * m, "hac_t": hac_t_double}},
            "gate_ii_hac_t": gate_ii,
            "gate_ii_methodology_status": (
                "OPEN/UNRATIFIED — per-window-means HAC (T=K); the pooled-per-bar "
                "alternative is more powered but contaminated by K−1 warmup-reset seams. "
                "The quant ratifies the form AND calibrates the threshold at v002/Phase 6; "
                "gate (ii) is provisional until then."),
            "total_net_pnl": total_pnl,
            "window_pnl_shares": shares,
            "max_window_pnl_share": max_share,
            "gate_iii_concentration": gate_iii,
        })
        if total_pnl <= 0.0:
            evidence["concentration_note"] = (
                "total net PnL <= 0: no positive edge to concentrate, so gate (iii) is "
                "vacuously satisfied. The loss is caught by gates (i)/(ii) and 4.3/4.5.")
        if not passed:
            failed = []
            if not gate_i:
                failed.append("positive_sharpe_frac")
            if not gate_ii:
                failed.append("hac_t")
            if not gate_iii:
                failed.append("window_pnl_concentration")
            evidence["reason"] = "subperiod_instability"
            evidence["subperiod_fail_detail"] = failed

        return TestOutcome(moira_id=self.moira_id, passed=passed,
                           score=float(hac_t if hac_t is not None else 0.0),
                           evidence=evidence)
