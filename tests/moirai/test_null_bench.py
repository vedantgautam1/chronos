"""test_null_bench.py — stage 4.9, full-engine null benchmark (spec §4.9). Protected.

Covers: null placement is price-blind BY CONSTRUCTION (no price parameter) and
deterministic under a fixed seed (I10); the percentile gate reads v001's 95 as a
PERCENTILE (not a 0.95 fraction); a candidate clearly above / below the null band gates
correctly; nulls run as real VERIFICATION executions tagged `:null:`; a candidate with
no round trips is unjudgeable; and the candidate guard.
"""

import inspect
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.nulls import NullStrategy, place_null_entries
from chronos.moirai.rerun import Rerun
from chronos.moirai.stages import null_bench as null_bench_mod
from chronos.moirai.stages.null_bench import NullBenchmark
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunKind
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result, build_round_trip_fills
from tests.oceanus.test_ingest import FakeExchange

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _cfg_n_nulls(n):
    from dataclasses import replace as dc_replace
    cfg = build_config(("M4.9-null-bench",))
    thr = dict(cfg.thresholds)
    thr["null_bench.n_nulls"] = n
    return dc_replace(cfg, thresholds=thr)


def _candidate(hours=120):
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1, start=START,
                    end=START + timedelta(hours=hours), strategy_params={})
    return Candidate(strategy=ToyMomentum(), base_config=cfg,
                     hypothesis=Hypothesis(id="H-null", statement="x", prediction="y"))


def _ctx(tmp_path, candidate, n_nulls=5, seed=1):
    store = RecordStore(tmp_path / "records")
    ctx = context_for_config(store, _cfg_n_nulls(n_nulls), gauntlet_seed=seed,
                             candidate=candidate)
    return store, ctx


def _candidate_result(net_target, *, n_bars=120):
    """A candidate BacktestResult with three 1-bar round trips (so n_entries=3) and a
    controlled net return (via a flat return series scaled to hit net_target)."""
    fills = build_round_trip_fills([1.0, 1.0, 1.0], start=START)  # 3 trips, durations 1
    per_bar = (1.0 + net_target) ** (1.0 / n_bars) - 1.0
    return build_result(returns_values=[per_bar] * n_bars, trades=fills,
                        bars_processed=n_bars)


# --- price-blindness (structural) + determinism --------------------------------

def test_placement_has_no_price_parameter():
    params = list(inspect.signature(place_null_entries).parameters)
    assert params == ["n_bars", "durations", "n_entries", "rng"]  # no price series


def test_placement_deterministic_under_fixed_seed():
    a = place_null_entries(1000, [5, 10, 20], 6, np.random.default_rng(42))
    b = place_null_entries(1000, [5, 10, 20], 6, np.random.default_rng(42))
    assert a == b
    # non-overlapping and inside [0, n_bars)
    for (e, x) in a:
        assert 0 <= e < x < 1000
    for (_, x0), (e1, _) in zip(a, a[1:]):
        assert e1 > x0  # strictly after the previous exit (reserved gap)


# --- percentile gate reads 95 as a percentile ----------------------------------

def _fixed_nulls_rerun(nets):
    it = iter(nets)

    def fake(ctx, config, *, strategy=None, hypothesis=None, **kw):
        return Rerun(result=build_result(returns_values=[next(it)]), wall_clock_s=0.0)
    return fake


def test_percentile_gate_reads_95_not_fraction(tmp_path, monkeypatch):
    nets = list(np.linspace(-0.10, 0.10, 20))  # symmetric null distribution
    _, ctx = _ctx(tmp_path, _candidate(), n_nulls=len(nets))
    monkeypatch.setattr(null_bench_mod, "rerun_candidate", _fixed_nulls_rerun(nets))
    # candidate net sits between p95 and the max → passes only under a 95-percentile read
    cand_net = float(np.percentile(nets, 95)) + 0.001
    outcome = NullBenchmark().evaluate(_candidate_result(cand_net), ctx)
    assert outcome.evidence["gate_threshold_net_return"] == pytest.approx(
        float(np.percentile(nets, 95)))
    assert outcome.passed  # above the 95th percentile


def test_candidate_below_band_fails(tmp_path, monkeypatch):
    nets = list(np.linspace(-0.10, 0.10, 20))
    _, ctx = _ctx(tmp_path, _candidate(), n_nulls=len(nets))
    monkeypatch.setattr(null_bench_mod, "rerun_candidate", _fixed_nulls_rerun(nets))
    outcome = NullBenchmark().evaluate(_candidate_result(-0.05), ctx)  # mid/low
    assert not outcome.passed
    assert outcome.evidence["reason"] == "does_not_beat_null_benchmark"
    assert 0.0 <= outcome.evidence["candidate_percentile_in_null_dist"] <= 100.0


def test_no_round_trips_is_unjudgeable(tmp_path, monkeypatch):
    _, ctx = _ctx(tmp_path, _candidate())
    monkeypatch.setattr(null_bench_mod, "rerun_candidate",
                        _fixed_nulls_rerun([0.0]))
    outcome = NullBenchmark().evaluate(build_result(returns_values=[0.0] * 50), ctx)
    assert not outcome.passed
    assert outcome.evidence["reason"] == "no_candidate_round_trips"


def test_raises_without_candidate(tmp_path):
    _, ctx = _ctx(tmp_path, None)
    with pytest.raises(ValueError, match="ctx.candidate"):
        NullBenchmark().evaluate(_candidate_result(0.0), ctx)


# --- real engine: nulls run as VERIFICATION, tagged :null:, deterministic ------

def _run_real(tmp_path, seed):
    n_bars = 120
    cand = _candidate(hours=n_bars)
    store, ctx = _ctx(tmp_path, cand, n_nulls=5, seed=seed)
    fake = FakeExchange(int(START.timestamp() * 1000), n_bars=n_bars, page_limit=500)
    original = ctx.run

    def patched(**kw):
        return original(data_root=tmp_path / "data", exchange=fake, **kw)

    ctx.run = patched  # type: ignore[method-assign]
    outcome = NullBenchmark().evaluate(_candidate_result(0.0, n_bars=n_bars), ctx)
    return store, outcome


def test_nulls_run_as_verification_tagged_null(tmp_path):
    store, outcome = _run_real(tmp_path, seed=3)
    vruns = [r for r in store.read_all()
             if r.get("type") == "run" and r.get("kind") == RunKind.VERIFICATION.value]
    null_runs = [r for r in vruns if ":null:" in r.get("hypothesis_id", "")]
    assert len(null_runs) == 5                      # five nulls, all real engine runs
    assert "null_distribution" in outcome.evidence
    assert len(outcome.evidence["run_wall_clock_s"]) == 5


def test_stage_deterministic_under_fixed_seed(tmp_path):
    _, o1 = _run_real(tmp_path / "a", seed=9)
    _, o2 = _run_real(tmp_path / "b", seed=9)
    assert o1.evidence["null_distribution"] == o2.evidence["null_distribution"]
    assert o1.evidence["candidate_percentile_in_null_dist"] == \
        o2.evidence["candidate_percentile_in_null_dist"]
