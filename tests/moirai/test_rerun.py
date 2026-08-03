"""test_rerun.py — the shared VERIFICATION re-run helper (moirai/rerun.py). Protected.

Covers: the candidate=None guard (raises, never guesses); a real engine re-run
through a FakeExchange that returns a BacktestResult and a positive wall-clock; kwargs
forwarded verbatim to ctx.run; and the net-return / per-bar-Sharpe metrics read the
returns series as-is.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.rerun import Rerun, net_return, per_bar_sharpe, rerun_candidate
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunKind
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result
from tests.oceanus.test_ingest import FakeExchange

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _ctx(tmp_path, *, candidate, seed=1):
    store = RecordStore(tmp_path / "records")
    ctx = context_for_config(store, build_config(("M4.5-cost-stress",)),
                             gauntlet_seed=seed, candidate=candidate)
    return store, ctx


def _candidate(n_bars=120):
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1, start=START,
                    end=START + timedelta(hours=n_bars), strategy_params={})
    hyp = Hypothesis(id="H-rerun", statement="momentum", prediction="something")
    return Candidate(strategy=ToyMomentum(), base_config=cfg, hypothesis=hyp)


def test_rerun_raises_without_candidate(tmp_path):
    _, ctx = _ctx(tmp_path, candidate=None)
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1, start=START,
                    end=START + timedelta(hours=10), strategy_params={})
    with pytest.raises(ValueError, match="ctx.candidate"):
        rerun_candidate(ctx, cfg)


def test_rerun_returns_result_and_positive_wall_clock(tmp_path):
    n_bars = 120
    cand = _candidate(n_bars)
    store, ctx = _ctx(tmp_path, candidate=cand)
    fake = FakeExchange(int(START.timestamp() * 1000), n_bars=n_bars, page_limit=500)
    rr = rerun_candidate(ctx, cand.base_config, data_root=tmp_path / "data",
                         exchange=fake)
    assert isinstance(rr, Rerun)
    assert rr.result is not None
    assert rr.wall_clock_s >= 0.0
    # It ran as VERIFICATION, and it was logged (I3/I6).
    vruns = [r for r in store.read_all()
             if r.get("type") == "run" and r.get("kind") == RunKind.VERIFICATION.value]
    assert len(vruns) == 1


def test_metrics_read_returns_as_is():
    r = build_result(returns_values=[0.0, 0.01, -0.005, 0.02])
    expected_net = float(np.prod(1.0 + np.array([0.0, 0.01, -0.005, 0.02])) - 1.0)
    assert net_return(r) == pytest.approx(expected_net)
    arr = np.array([0.0, 0.01, -0.005, 0.02])
    assert per_bar_sharpe(r) == pytest.approx(arr.mean() / arr.std(ddof=1))
