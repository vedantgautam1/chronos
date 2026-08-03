"""test_signal_null.py — stage 4.1, signal-only null gate (spec §4.1). Protected.

Covers: the SignalCapture wrapper's intent mapping and order suppression; the
bootstrap statistic (injected-drift → p<α; pure-noise → empirical rejection ≈ α
over 200 seeded reps within ±2σ; p invariant to the detrending constant;
deterministic under a fixed seed); and the stage end-to-end through a real engine
capture run (no orders emitted, evidence stamped, deterministic).
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from chronos.hephaestus.types import Order, OrderType, Side
from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.stages.signal_null import (
    SignalCapture,
    SignalNull,
    signal_null_pvalue,
)
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result
from tests.oceanus.test_ingest import FakeExchange

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


# --- SignalCapture wrapper -----------------------------------------------------

class _FakeView:
    def __init__(self, now, close):
        self.now = now
        self._close = close

    def bars(self, symbol, lookback):
        import pandas as pd
        return pd.DataFrame({"close": [self._close]})


class _Emits:
    """Inner strategy stub that returns a fixed order list each bar."""

    def __init__(self, orders):
        self._orders = orders

    def on_bar(self, view, ctx):
        return list(self._orders)


def _order(side, qty):
    return Order(id=0, symbol="BTC/USDT", side=side, type=OrderType.MARKET,
                 qty=qty, created_at=START)


def test_signal_capture_maps_net_buy_to_long_and_emits_nothing():
    from decimal import Decimal
    cases = [
        ([_order(Side.BUY, Decimal("0.2"))], 1),       # net buy → long
        ([], 0),                                        # no order → flat
        ([_order(Side.SELL, Decimal("0.2"))], 0),       # net sell → flat
        ([_order(Side.BUY, Decimal("0.3")),
          _order(Side.SELL, Decimal("0.1"))], 1),       # net positive → long
        ([_order(Side.BUY, Decimal("0.1")),
          _order(Side.SELL, Decimal("0.4"))], 0),       # net negative → flat
    ]
    for orders, expected_s in cases:
        cap = SignalCapture(_Emits(orders), "BTC/USDT")
        emitted = cap.on_bar(_FakeView(START, 100.0), ctx=None)
        assert emitted == []                            # NEVER emits orders
        assert cap.signals[-1][1] == expected_s
        assert cap.closes[-1] == (START, 100.0)


# --- The bootstrap statistic ---------------------------------------------------

def _rng(seed):
    return np.random.default_rng(seed)


def test_injected_drift_rejects_the_null():
    """Signals aligned with a real forward drift → θ̂ ≫ 0 → p below α."""
    T = 400
    rng = _rng(0)
    signals = np.array([1 if i % 2 == 0 else 0 for i in range(T)], float)
    forward_returns = rng.normal(0.0, 3e-3, T)
    # Inject drift: signal i pairs directly with the forward return over bar i→i+1.
    forward_returns[signals == 1] += 6e-3
    p, theta = signal_null_pvalue(signals, forward_returns, p_block=1.0, B=500,
                                  rng=_rng(1))
    assert theta > 0.0
    assert p < 0.05


def test_pure_noise_empirical_rejection_near_alpha():
    """200 SEEDED reps of independent signals × independent noise returns: the
    empirical rejection rate at α=0.05 sits within ±2σ of α. FIXED master seed; no
    seed-shopping — this asserts the test is correctly sized, not that a lucky seed
    passes."""
    alpha, reps, T, B = 0.05, 200, 128, 199
    two_sigma = 2.0 * np.sqrt(alpha * (1 - alpha) / reps)  # ≈ 0.0308
    seeds = np.random.SeedSequence(2026).spawn(reps)
    rejections = 0
    for ss in seeds:
        g = np.random.default_rng(ss)
        signals = (g.random(T) < 0.5).astype(float)
        log_returns = g.normal(0.0, 2e-3, T)
        p, _ = signal_null_pvalue(signals, log_returns, p_block=1.0, B=B,
                                  rng=np.random.default_rng(ss))
        if p <= alpha:
            rejections += 1
    rate = rejections / reps
    assert abs(rate - alpha) <= two_sigma, (
        f"empirical rejection {rate:.4f} outside α±2σ "
        f"[{alpha - two_sigma:.4f}, {alpha + two_sigma:.4f}] — investigate, do NOT reseed")


def test_pvalue_invariant_to_detrending_constant():
    """Shifting every log return by a constant leaves the p-value unchanged (the
    statistic detrends by the sample mean; the shift cancels in θ̂ and every
    bootstrap θ because the signals are held fixed)."""
    T = 300
    g = _rng(4)
    signals = (g.random(T) < 0.5).astype(float)
    log_returns = g.normal(1e-4, 2e-3, T)
    p0, _ = signal_null_pvalue(signals, log_returns, p_block=0.5, B=300, rng=_rng(5))
    p1, _ = signal_null_pvalue(signals, log_returns + 7.0, p_block=0.5, B=300, rng=_rng(5))
    assert p0 == p1


def test_deterministic_under_fixed_seed():
    T = 200
    g = _rng(6)
    signals = (g.random(T) < 0.5).astype(float)
    log_returns = g.normal(0.0, 2e-3, T)
    p_a, t_a = signal_null_pvalue(signals, log_returns, p_block=0.5, B=250, rng=_rng(11))
    p_b, t_b = signal_null_pvalue(signals, log_returns, p_block=0.5, B=250, rng=_rng(11))
    assert (p_a, t_a) == (p_b, t_b)


# --- The stage end-to-end through a real capture run ---------------------------

def _candidate_ctx(tmp_path, *, seed=1234, n_bars=120):
    store = RecordStore(tmp_path / "records")
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                    start=START, end=START + timedelta(hours=n_bars),
                    strategy_params={})
    hyp = Hypothesis(id="H-signal", statement="momentum beats noise",
                     prediction="p<=alpha")
    candidate = Candidate(strategy=ToyMomentum(), base_config=cfg, hypothesis=hyp)
    ctx = context_for_config(store, build_config(("M4.1-signal-null",)),
                             gauntlet_seed=seed, candidate=candidate)
    # data_root/exchange are threaded through ctx.run via kwargs.
    return store, ctx, hyp


def _evaluate_with_fake(ctx, result, tmp_path, n_bars=120):
    fake = FakeExchange(int(START.timestamp() * 1000), n_bars=n_bars, page_limit=500)
    # ctx.run forwards **kwargs (data_root, exchange) to run_experiment.
    original_run = ctx.run

    def patched(**kw):
        return original_run(data_root=tmp_path / "data", exchange=fake, **kw)

    ctx.run = patched  # type: ignore[method-assign]
    return SignalNull().evaluate(result, ctx)


def test_stage_captures_signal_emits_no_orders_and_stamps_evidence(tmp_path):
    store, ctx, hyp = _candidate_ctx(tmp_path)
    result = build_result(returns_values=list(np.zeros(120)), hypothesis_id="H-signal")
    outcome = _evaluate_with_fake(ctx, result, tmp_path)

    ev = outcome.evidence
    assert ev["flat_portfolio_assumption"] is True
    assert "p_value" in ev and "theta_hat" in ev
    assert "p_value_bracket" in ev and "fragile_to_block_length" in ev
    assert ev["n_long_bars"] > 0  # ToyMomentum on a rising ramp wants to be long
    # The capture run emitted NO orders → the portfolio stayed flat → its stored
    # VERIFICATION result has zero trades and a flat (all-zero) return series.
    vruns = [r for r in store.read_all()
             if r.get("type") == "run" and r.get("kind") == "VERIFICATION"]
    assert vruns, "the capture run must be logged (VERIFICATION)"
    cap = vruns[-1]["result"]
    assert cap["trades"] == []
    assert all(v == 0.0 for _, v in cap["returns"])


def test_stage_deterministic_under_fixed_gauntlet_seed(tmp_path):
    s1, c1, _ = _candidate_ctx(tmp_path / "a", seed=77)
    s2, c2, _ = _candidate_ctx(tmp_path / "b", seed=77)
    r1 = build_result(returns_values=list(np.zeros(120)), hypothesis_id="H-signal")
    r2 = build_result(returns_values=list(np.zeros(120)), hypothesis_id="H-signal")
    o1 = _evaluate_with_fake(c1, r1, tmp_path / "a")
    o2 = _evaluate_with_fake(c2, r2, tmp_path / "b")
    assert o1.evidence["p_value"] == o2.evidence["p_value"]
    assert o1.evidence["theta_hat"] == o2.evidence["theta_hat"]
    assert o1.evidence["p_block"] == o2.evidence["p_block"]
