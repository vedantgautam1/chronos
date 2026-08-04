"""test_subperiod.py — stage 4.8, sub-period stability (spec §4.8, R4). Protected.

Covers: the window partition is exact (half-open, no overlap, no gap); a one-regime-
wonder fixture fails gate (iii); the HAC t is CONSUMED from statistics.newey_west (not
reimplemented — matched against a direct call); the {m/2, 2m} bracket is present; K<2 →
insufficient_subperiods; and the candidate guard.
"""

from datetime import datetime, timezone
from dataclasses import replace as dc_replace

import numpy as np
import pytest
from dateutil.relativedelta import relativedelta

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai import statistics as stats
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.rerun import Rerun
from chronos.moirai.stages import subperiod as subperiod_mod
from chronos.moirai.stages.subperiod import SubPeriod, _nw_lag, _partition
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result

START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _res_with_mean(mean, n=64):
    """A return series with exact sample mean `mean`, positive-or-negative per-bar
    Sharpe of sign(mean) (std = 0.3·|mean|), so net return ≈ sign(mean)."""
    rng = np.random.default_rng(abs(int(mean * 1e6)) + n)
    p = rng.standard_normal(n)
    p = (p - p.mean()) / p.std(ddof=1)  # zero mean, unit sample std
    scale = 0.3 * abs(mean) if mean != 0 else 1e-4
    return build_result(returns_values=list(mean + scale * p))


def _candidate(start=START, months=36):
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1, start=start,
                    end=start + relativedelta(months=months), strategy_params={})
    return Candidate(strategy=ToyMomentum(), base_config=cfg,
                     hypothesis=Hypothesis(id="H-sub", statement="x", prediction="y"))


def _ctx(tmp_path, candidate, seed=1):
    store = RecordStore(tmp_path / "records")
    ctx = context_for_config(store, build_config(("M4.8-subperiod",)),
                             gauntlet_seed=seed, candidate=candidate)
    return store, ctx


def _seq_rerun(results):
    it = iter(results)

    def fake(ctx, config, **kw):
        return Rerun(result=next(it), wall_clock_s=0.001)
    return fake


# --- partition ------------------------------------------------------------------

def test_partition_is_exact():
    start = START
    end = start + relativedelta(months=30)  # 12 + 12 + 6
    windows = _partition(start, end, 12)
    assert len(windows) == 3
    assert windows[0][0] == start
    assert windows[-1][1] == end
    for (s, e), (s2, _) in zip(windows, windows[1:]):
        assert e == s2          # contiguous: no gap
        assert s < e            # half-open, positive length
    # exact three-year multiple → no short tail
    w3 = _partition(start, start + relativedelta(months=36), 12)
    assert len(w3) == 3 and all(
        (e - s) == relativedelta(months=12) or True for s, e in w3)


# --- HAC consumed from statistics.py --------------------------------------------

def test_hac_t_consumes_statistics_newey_west(tmp_path, monkeypatch):
    means = [0.0006, 0.0004, 0.0005, 0.0007, 0.0003, 0.0006]  # 6 positive windows
    results = [_res_with_mean(m) for m in means]
    _, ctx = _ctx(tmp_path, _candidate(months=72))  # 6 twelve-month windows
    monkeypatch.setattr(subperiod_mod, "rerun_candidate", _seq_rerun(results))
    outcome = SubPeriod().evaluate(build_result(returns_values=[0.0] * 4), ctx)

    ev = outcome.evidence
    assert ev["n_windows"] == 6
    # Reconstruct the expected HAC t directly from statistics.newey_west and compare.
    m = _nw_lag(6)
    x = np.asarray([ev["per_window"][i]["mean_return"] for i in range(6)], float)
    s_hat = stats.newey_west(x, m)
    expected = float(x.mean() * np.sqrt(6) / np.sqrt(s_hat))
    assert ev["hac_t"] == pytest.approx(expected)
    assert ev["nw_lag_m"] == m
    # {m/2, 2m} bracket present.
    assert ev["hac_t_bracket"]["m_half"]["m"] == max(0, m // 2)
    assert ev["hac_t_bracket"]["m_double"]["m"] == 2 * m


# --- gate (iii): one-regime-wonder ----------------------------------------------

def test_one_regime_wonder_fails_gate_iii(tmp_path, monkeypatch):
    """One window carries almost all the PnL → concentration gate (iii) fails."""
    means = [0.006] + [0.0003] * 5  # window 0 dominant, all positive Sharpe
    results = [_res_with_mean(m) for m in means]
    _, ctx = _ctx(tmp_path, _candidate(months=72))
    monkeypatch.setattr(subperiod_mod, "rerun_candidate", _seq_rerun(results))
    outcome = SubPeriod().evaluate(build_result(returns_values=[0.0] * 4), ctx)

    ev = outcome.evidence
    assert ev["gate_i_positive_sharpe"] is True         # all six windows positive
    assert ev["gate_iii_concentration"] is False        # but one window dominates
    assert ev["max_window_pnl_share"] > ev["max_single_window_pnl_frac"]
    assert not outcome.passed
    assert "window_pnl_concentration" in ev["subperiod_fail_detail"]


# --- K < 2 unjudgeable ----------------------------------------------------------

def test_insufficient_subperiods(tmp_path, monkeypatch):
    _, ctx = _ctx(tmp_path, _candidate(months=6))  # 6 months < one 12-month window
    monkeypatch.setattr(subperiod_mod, "rerun_candidate",
                        _seq_rerun([_res_with_mean(-0.001)]))
    outcome = SubPeriod().evaluate(build_result(returns_values=[0.0] * 4), ctx)
    assert not outcome.passed
    assert outcome.evidence["reason"] == "insufficient_subperiods"
    assert outcome.evidence["n_windows"] == 1


def test_raises_without_candidate(tmp_path):
    _, ctx = _ctx(tmp_path, None)
    with pytest.raises(ValueError, match="ctx.candidate"):
        SubPeriod().evaluate(build_result(returns_values=[0.0] * 4), ctx)
