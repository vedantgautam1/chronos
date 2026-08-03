"""test_cost_stress.py — stage 4.5, cost stress (spec §4.5, D-05). Protected.

Covers: monotone-cost fixture → PASS; non-monotone fixture (cheaper level fails while
the gate level passes) → FAIL non_monotone_cost_response; gate-level failure →
cost_gate_fail; the margin criterion boundary (active vs inactive); and — the anti-
shortcut proof — three REAL ctx.run VERIFICATION executions with distinct config
hashes and an identical data hash (no cost_summary rescale).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pytest

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.rerun import Rerun, net_return, per_bar_sharpe
from chronos.moirai.stages import cost_stress as cost_stress_mod
from chronos.moirai.stages.cost_stress import CostStress
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunKind
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result
from tests.oceanus.test_ingest import FakeExchange

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
PROVISIONAL = ("provisional_cost_constants: configured guesses (R6).",)


def _returns_with_sr(target_sr, n=64):
    """A length-n return series whose per-bar Sharpe ≈ target_sr and whose net return
    has the sign of target_sr (zero-mean unit-std pattern shifted by the target)."""
    rng = np.random.default_rng(abs(int(target_sr * 1e6)) + n)
    x = rng.standard_normal(n)
    x = (x - x.mean()) / x.std(ddof=1)
    scale = 1e-3
    return list(x * scale + target_sr * scale)


def _res(target_sr, *, warnings=PROVISIONAL):
    return build_result(returns_values=_returns_with_sr(target_sr), warnings=warnings)


def _candidate():
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1, start=START,
                    end=START + timedelta(hours=64),
                    strategy_params={}, cost=_default_cost())
    hyp = Hypothesis(id="H-cost", statement="x", prediction="y")
    return Candidate(strategy=ToyMomentum(), base_config=cfg, hypothesis=hyp)


def _default_cost():
    from chronos.hephaestus.costs import CostConfig
    return CostConfig()  # slippage 1 bps, half-spread 1 bps, taker 10 bps, provisional


def _ctx(tmp_path, candidate, seed=1):
    store = RecordStore(tmp_path / "records")
    ctx = context_for_config(store, build_config(("M4.5-cost-stress",)),
                             gauntlet_seed=seed, candidate=candidate)
    return store, ctx


def _fake_rerun(by_level):
    def fake(ctx, config, **kw):
        return Rerun(result=by_level[int(config.cost.slippage_bps)], wall_clock_s=0.001)
    return fake


# --- gate branches (rerun monkeypatched — deterministic, no engine) ------------

def test_monotone_passes(tmp_path, monkeypatch):
    _, ctx = _ctx(tmp_path, _candidate())
    by_level = {5: _res(0.03), 10: _res(0.02), 25: _res(0.01)}
    monkeypatch.setattr(cost_stress_mod, "rerun_candidate", _fake_rerun(by_level))
    base = _res(0.05)
    outcome = CostStress().evaluate(base, ctx)
    assert outcome.passed
    assert outcome.evidence["margin_active"] is True


def test_non_monotone_fails(tmp_path, monkeypatch):
    """Gate (10 bps) passes but the dominated 5 bps run fails → red flag."""
    _, ctx = _ctx(tmp_path, _candidate())
    by_level = {5: _res(-0.5), 10: _res(0.02), 25: _res(0.01)}
    monkeypatch.setattr(cost_stress_mod, "rerun_candidate", _fake_rerun(by_level))
    outcome = CostStress().evaluate(_res(0.05), ctx)
    assert not outcome.passed
    assert outcome.evidence["reason"] == "non_monotone_cost_response"


def test_gate_level_failure(tmp_path, monkeypatch):
    _, ctx = _ctx(tmp_path, _candidate())
    by_level = {5: _res(0.03), 10: _res(-0.5), 25: _res(-0.6)}
    monkeypatch.setattr(cost_stress_mod, "rerun_candidate", _fake_rerun(by_level))
    outcome = CostStress().evaluate(_res(0.05), ctx)
    assert not outcome.passed
    assert outcome.evidence["reason"] == "cost_gate_fail"


def test_margin_boundary(tmp_path, monkeypatch):
    """With the provisional-cost margin active (0.005/bar): a 10-bps run with a
    positive-but-sub-margin Sharpe fails; a supra-margin one passes."""
    # sub-margin at the gate → fail
    _, ctx = _ctx(tmp_path, _candidate())
    by_level = {5: _res(0.03), 10: _res(0.004), 25: _res(0.001)}
    monkeypatch.setattr(cost_stress_mod, "rerun_candidate", _fake_rerun(by_level))
    outcome = CostStress().evaluate(_res(0.05), ctx)
    assert not outcome.passed and outcome.evidence["reason"] == "cost_gate_fail"

    # supra-margin at the gate → pass
    _, ctx2 = _ctx(tmp_path / "b", _candidate())
    by_level2 = {5: _res(0.03), 10: _res(0.006), 25: _res(0.001)}
    monkeypatch.setattr(cost_stress_mod, "rerun_candidate", _fake_rerun(by_level2))
    assert CostStress().evaluate(_res(0.05), ctx2).passed


def test_margin_inactive_uses_zero_floor(tmp_path, monkeypatch):
    """No provisional warning on the judged result → floor is 0, so a positive
    sub-0.005 Sharpe passes the gate."""
    _, ctx = _ctx(tmp_path, _candidate())
    by_level = {5: _res(0.03, warnings=()), 10: _res(0.004, warnings=()),
                25: _res(0.001, warnings=())}
    monkeypatch.setattr(cost_stress_mod, "rerun_candidate", _fake_rerun(by_level))
    outcome = CostStress().evaluate(_res(0.05, warnings=()), ctx)
    assert outcome.evidence["margin_active"] is False
    assert outcome.passed


def test_raises_without_candidate(tmp_path):
    _, ctx = _ctx(tmp_path, None)
    with pytest.raises(ValueError, match="ctx.candidate"):
        CostStress().evaluate(_res(0.05), ctx)


# --- the anti-shortcut proof: three REAL VERIFICATION runs ---------------------

def test_three_real_verification_runs_distinct_hashes(tmp_path):
    n_bars = 120
    cand = _candidate()
    cand = Candidate(strategy=ToyMomentum(),
                     base_config=RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                                           start=START, end=START + timedelta(hours=n_bars),
                                           strategy_params={}, cost=_default_cost()),
                     hypothesis=Hypothesis(id="H-cost", statement="x", prediction="y"))
    store, ctx = _ctx(tmp_path, cand)

    fake = FakeExchange(int(START.timestamp() * 1000), n_bars=n_bars, page_limit=500)
    original = ctx.run
    calls = {"verification": 0}

    def patched(**kw):
        if kw.get("kind") == RunKind.VERIFICATION:
            calls["verification"] += 1
        return original(data_root=tmp_path / "data", exchange=fake, **kw)

    ctx.run = patched  # type: ignore[method-assign]
    outcome = CostStress().evaluate(_res(0.05), ctx)

    # Exactly three engine re-runs happened (5, 10, 25 bps) — not a line-item rescale.
    assert calls["verification"] == 3
    vruns = [r for r in store.read_all()
             if r.get("type") == "run" and r.get("kind") == RunKind.VERIFICATION.value]
    assert len(vruns) == 3
    config_hashes = {r["config_hash"] for r in vruns}
    data_hashes = {r["data_snapshot_hash"] for r in vruns}
    assert len(config_hashes) == 3       # distinct costs → distinct config hashes
    assert len(data_hashes) == 1         # identical window/data → one data hash
    # The stressed slippage levels are the absolute config values, not scaled summaries.
    levels = {str(l) for l in ctx.config.thresholds["cost_stress.levels_bps"]}
    assert set(outcome.evidence["cost_curve"].keys()) == {"base"} | levels
