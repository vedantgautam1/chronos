"""test_descriptive.py — stage 4.10, descriptive reporting (spec §4.10). Protected.

Covers: the outcome NEVER gates (passed always True); regime / cross-asset / annualized
figures are present; every annualized figure names its window; the 200d-MA regime skips
with a note when history is short and computes when a long price series is available;
the cross-asset trace notes a symbol-bound candidate; and the candidate guard.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from chronos.hephaestus.types import BacktestResult, CostSummary
from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.stages import descriptive as descriptive_mod
from chronos.moirai.stages.descriptive import Descriptive
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig
from chronos.strategies.ma_crossover import MACrossover
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result
from decimal import Decimal

START = datetime(2026, 3, 1, tzinfo=timezone.utc)


def _candidate(*, symbol="BTC/USDT", timeframe=Timeframe.H1, strategy=None, start=START,
               end=None):
    end = end or (start + timedelta(hours=200))
    cfg = RunConfig(symbol=symbol, timeframe=timeframe, start=start, end=end,
                    strategy_params={})
    return Candidate(strategy=strategy or ToyMomentum(), base_config=cfg,
                     hypothesis=Hypothesis(id="H-desc", statement="x", prediction="y"))


def _ctx(tmp_path, candidate, seed=1):
    store = RecordStore(tmp_path / "records")
    ctx = context_for_config(store, build_config(("M4.10-descriptive",)),
                             gauntlet_seed=seed, candidate=candidate)
    return store, ctx


def test_never_gates_and_has_all_sections(tmp_path, monkeypatch):
    # Hermetic: force the skip paths regardless of what BTC history is on disk, so the
    # test asserts the same sections whether or not the canonical data has been ingested.
    monkeypatch.setattr(descriptive_mod, "available_range", lambda *a, **k: None)
    _, ctx = _ctx(tmp_path, _candidate())
    result = build_result(returns_values=[0.0, 0.01, -0.005, 0.02, -0.01, 0.015])
    outcome = Descriptive().evaluate(result, ctx)
    assert outcome.passed is True                       # reporting-only, never gates
    ev = outcome.evidence
    for key in ("regime_per_calendar_year", "regime_above_below_200d_ma",
                "cross_asset_trace", "annualized", "metrics"):
        assert key in ev
    # metrics present
    for key in ("cagr", "max_drawdown", "sortino_annualized", "profit_factor",
                "turnover_x_initial_cash", "net_return"):
        assert key in ev["metrics"]
    # ETH not cached → cross-asset skipped with a note (reporting-only)
    assert ev["cross_asset_trace"]["available"] is False
    # 200d MA needs 200 days of prior history → skipped on this short 2026 window
    assert ev["regime_above_below_200d_ma"]["available"] is False


def test_annualized_names_its_window(tmp_path):
    _, ctx = _ctx(tmp_path, _candidate())
    result = build_result(returns_values=[0.001, -0.002, 0.003, 0.0])
    ev = Descriptive().evaluate(result, ctx).evidence
    ann = ev["annualized"]
    assert ann["reporting_only"] is True
    assert "window" in ann and len(ann["window"]) == 2       # names its window
    assert "annualized_sharpe_naive_sqrt_k" in ann
    assert "annualized_sharpe_lo_ar1" in ann                 # Lo Eq.22 alongside naive


def test_cross_asset_symbol_bound_note(tmp_path, monkeypatch):
    """A symbol-bound candidate (MACrossover on BTC) with ETH data present → the trace
    is skipped with a note about the binding, not silently faked or degenerate-run."""
    monkeypatch.setattr(descriptive_mod, "available_range",
                        lambda *a, **k: (START - timedelta(days=400), START + timedelta(days=1)))
    _, ctx = _ctx(tmp_path, _candidate(strategy=MACrossover()))
    ev = Descriptive().evaluate(build_result(returns_values=[0.0, 0.01]), ctx).evidence
    cross = ev["cross_asset_trace"]
    assert cross["available"] is False
    assert "bound" in cross["note"].lower()


def test_200dma_compute_path(tmp_path, monkeypatch):
    """With a long daily price series available, the 200d-MA regime computes and splits
    the window's returns into above/below buckets."""
    day = timedelta(days=1)
    ext_start = START - timedelta(days=200)
    end = START + timedelta(days=60)
    # 260 daily bars: rise for 230 days, then fall — so the in-window tail straddles MA.
    n = 261
    times = [ext_start + i * day for i in range(n)]
    closes = [100.0 + i for i in range(230)] + [330.0 - 3.0 * j for j in range(n - 230)]
    bars = pd.DataFrame({"open_time": times, "close": closes[:n]})
    monkeypatch.setattr(descriptive_mod, "get_bars", lambda *a, **k: bars)
    monkeypatch.setattr(descriptive_mod, "available_range",
                        lambda *a, **k: (ext_start, end + day))

    # result.returns indexed on the in-window daily timestamps (day 200..259)
    in_window = [START + i * day for i in range(60)]
    rng = np.random.default_rng(0)
    returns = pd.Series(list(rng.normal(0.0002, 0.01, 60)),
                        index=pd.DatetimeIndex(in_window))
    equity = pd.Series([10000.0 * (1 + 0.001 * i) for i in range(60)],
                       index=pd.DatetimeIndex(in_window))
    result = BacktestResult(
        run_id="r", core_version="c", config_hash="h", data_snapshot_hash="d", seed=0,
        bars_processed=60, date_range=(START, end), symbols=("BTC/USDT",),
        timeframe="1d", trades=(), order_events=(), equity_curve=equity, returns=returns,
        cost_summary=CostSummary(Decimal("0"), Decimal("0"), Decimal("0")),
        warnings=(), hypothesis_id="H-desc", trial_index=1)

    # symbol-bound candidate → cross-asset trace skips (its own note), isolating the
    # 200d-MA path under test from the wide available_range monkeypatch above.
    _, ctx = _ctx(tmp_path, _candidate(timeframe=Timeframe.D1, start=START, end=end,
                                       strategy=MACrossover()))
    ev = Descriptive().evaluate(result, ctx).evidence
    regime = ev["regime_above_below_200d_ma"]
    assert regime["available"] is True
    assert regime["ma_period_bars"] == 200
    assert regime["above"]["bars"] + regime["below"]["bars"] > 0


def test_raises_without_candidate(tmp_path):
    _, ctx = _ctx(tmp_path, None)
    with pytest.raises(ValueError, match="ctx.candidate"):
        Descriptive().evaluate(build_result(returns_values=[0.0, 0.01]), ctx)
