"""test_shift.py — stage 4.7, shifted-window stability (spec §4.7). Protected.

Covers: four offsets → four real VERIFICATION runs (deterministic across a fresh
context); the sealed-range forward guard (constructed seal → refusal, no run); the
past-available-data forward guard (narrow coverage → refusal, no run); the
pass-fraction boundary; and the candidate=None guard.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.rerun import Rerun
from chronos.moirai.stages import shift as shift_mod
from chronos.moirai.stages.shift import ShiftedWindow
from chronos.oceanus.model import Timeframe
from chronos.oceanus.seal import SealRegistry
from chronos.run import Hypothesis, RunConfig, RunKind
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result
from tests.oceanus.test_ingest import FakeExchange

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WIDE = (START - timedelta(days=40), START + timedelta(days=40))


def _returns_with_sr(target_sr, n=64):
    rng = np.random.default_rng(abs(int(target_sr * 1e6)) + n)
    x = rng.standard_normal(n)
    x = (x - x.mean()) / x.std(ddof=1)
    return list(x * 1e-3 + target_sr * 1e-3)


def _res(target_sr):
    return build_result(returns_values=_returns_with_sr(target_sr))


def _candidate(hours=48):
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1, start=START,
                    end=START + timedelta(hours=hours), strategy_params={})
    return Candidate(strategy=ToyMomentum(), base_config=cfg,
                     hypothesis=Hypothesis(id="H-shift", statement="x", prediction="y"))


def _ctx(tmp_path, candidate, seed=1):
    store = RecordStore(tmp_path / "records")
    ctx = context_for_config(store, build_config(("M4.7-shift",)),
                             gauntlet_seed=seed, candidate=candidate)
    return store, ctx


def _seq_rerun(results):
    it = iter(results)

    def fake(ctx, config, **kw):
        return Rerun(result=next(it), wall_clock_s=0.001)
    return fake


# --- four offsets → four real VERIFICATION runs, deterministic -----------------

def _run_real(tmp_path, seed, monkeypatch):
    cand = _candidate(hours=48)
    store, ctx = _ctx(tmp_path, cand, seed=seed)
    monkeypatch.setattr(shift_mod, "available_range", lambda *a, **k: WIDE)
    fake = FakeExchange(int((START - timedelta(days=21)).timestamp() * 1000),
                        n_bars=24 * 44, page_limit=2000)
    original = ctx.run
    calls = {"v": 0}

    def patched(**kw):
        if kw.get("kind") == RunKind.VERIFICATION:
            calls["v"] += 1
        return original(data_root=tmp_path / "data", exchange=fake, **kw)

    ctx.run = patched  # type: ignore[method-assign]
    outcome = ShiftedWindow().evaluate(_res(0.05), ctx)
    return store, ctx, outcome, calls


def test_four_offsets_four_runs(tmp_path, monkeypatch):
    _, _, outcome, calls = _run_real(tmp_path, 1, monkeypatch)
    assert calls["v"] == 4
    assert outcome.evidence["n_evaluated"] == 4
    assert outcome.evidence["n_refused"] == 0
    assert len(outcome.evidence["per_offset"]) == 4


def test_deterministic_across_fresh_context(tmp_path, monkeypatch):
    _, _, o1, _ = _run_real(tmp_path / "a", 7, monkeypatch)
    _, _, o2, _ = _run_real(tmp_path / "b", 7, monkeypatch)
    s1 = [o["per_bar_sharpe"] for o in o1.evidence["per_offset"]]
    s2 = [o["per_bar_sharpe"] for o in o2.evidence["per_offset"]]
    assert s1 == s2


# --- forward guards ------------------------------------------------------------

def test_sealed_range_refusal(tmp_path, monkeypatch):
    """A seal overlapping the −2w window → that offset is refused, never run."""
    cand = _candidate(hours=48)
    _, ctx = _ctx(tmp_path, cand)
    monkeypatch.setattr(shift_mod, "available_range", lambda *a, **k: WIDE)

    reg = SealRegistry(tmp_path / "seal.json")
    # −2w window is [START−14d, START−14d+48h). Seal a range inside it.
    reg.seal("BTC/USDT", Timeframe.H1, START - timedelta(days=14),
             START - timedelta(days=13), "test seal")
    monkeypatch.setattr(shift_mod, "SealRegistry", lambda: reg)

    ran = {"n": 0}

    def fake(ctx_, config, **kw):
        ran["n"] += 1
        return Rerun(result=_res(0.05), wall_clock_s=0.0)
    monkeypatch.setattr(shift_mod, "rerun_candidate", fake)

    outcome = ShiftedWindow().evaluate(_res(0.05), ctx)
    by_offset = {o["offset_weeks"]: o for o in outcome.evidence["per_offset"]}
    assert by_offset[-2]["refused"] is True
    assert by_offset[-2]["reason"] == "sealed_range"
    assert ran["n"] == 3           # only the three non-sealed offsets ran
    assert outcome.evidence["n_refused"] == 1


def test_past_available_data_refusal(tmp_path, monkeypatch):
    """Coverage narrowed to exactly the base window → every shift runs past it."""
    cand = _candidate(hours=48)
    _, ctx = _ctx(tmp_path, cand)
    base_cov = (cand.base_config.start, cand.base_config.end)
    monkeypatch.setattr(shift_mod, "available_range", lambda *a, **k: base_cov)

    ran = {"n": 0}

    def fake(ctx_, config, **kw):
        ran["n"] += 1
        return Rerun(result=_res(0.05), wall_clock_s=0.0)
    monkeypatch.setattr(shift_mod, "rerun_candidate", fake)

    outcome = ShiftedWindow().evaluate(_res(0.05), ctx)
    assert ran["n"] == 0                                   # nothing ran
    assert outcome.evidence["n_refused"] == 4
    assert not outcome.passed
    reasons = {o["reason"] for o in outcome.evidence["per_offset"]}
    assert reasons == {"past_available_data"}


# --- pass-fraction boundary ----------------------------------------------------

def test_pass_fraction_boundary(tmp_path, monkeypatch):
    """base Sharpe 0.10, band ±50% → within iff sr ∈ [0.05, 0.15]. 4/4 within → pass
    (1.0 ≥ 0.8); 3/4 within → fail (0.75 < 0.8)."""
    monkeypatch.setattr(shift_mod, "available_range", lambda *a, **k: WIDE)
    base = _res(0.10)

    # all four within band → pass
    _, ctx = _ctx(tmp_path, _candidate())
    monkeypatch.setattr(shift_mod, "rerun_candidate",
                        _seq_rerun([_res(0.12), _res(0.12), _res(0.12), _res(0.12)]))
    ok = ShiftedWindow().evaluate(base, ctx)
    assert ok.passed and ok.evidence["n_within_band"] == 4

    # three within, one far out → fail
    _, ctx2 = _ctx(tmp_path / "b", _candidate())
    monkeypatch.setattr(shift_mod, "rerun_candidate",
                        _seq_rerun([_res(0.12), _res(0.12), _res(0.12), _res(0.30)]))
    bad = ShiftedWindow().evaluate(base, ctx2)
    assert not bad.passed and bad.evidence["n_within_band"] == 3


def test_raises_without_candidate(tmp_path):
    _, ctx = _ctx(tmp_path, None)
    with pytest.raises(ValueError, match="ctx.candidate"):
        ShiftedWindow().evaluate(_res(0.05), ctx)


# --- dropped spec gate: sign-agreement sub-gate is dormant under v001 ----------

def test_sign_agreement_subgate_dormant_under_v001(tmp_path, monkeypatch):
    """v001 has no shift.min_sign_agree key → the sub-gate is built but inactive and
    never touches the verdict; the pass-fraction gate alone decides."""
    monkeypatch.setattr(shift_mod, "available_range", lambda *a, **k: WIDE)
    _, ctx = _ctx(tmp_path, _candidate())
    monkeypatch.setattr(shift_mod, "rerun_candidate",
                        _seq_rerun([_res(0.12)] * 4))
    outcome = ShiftedWindow().evaluate(_res(0.10), ctx)
    sub = outcome.evidence["sign_agreement_subgate"]
    assert sub["active"] is False
    assert "min_sign_agree" not in sub
    assert outcome.passed  # decided by pass-fraction only


def _ctx_with_v002_key(tmp_path, candidate, min_sign_agree):
    from dataclasses import replace as dc_replace
    store = RecordStore(tmp_path / "records")
    cfg = build_config(("M4.7-shift",))
    thresholds = dict(cfg.thresholds)
    thresholds["shift.min_sign_agree"] = min_sign_agree  # the v002 key
    cfg = dc_replace(cfg, thresholds=thresholds)
    return context_for_config(store, cfg, gauntlet_seed=1, candidate=candidate)


def test_sign_agreement_subgate_active_and_agreeing_passes(tmp_path, monkeypatch):
    """With the v002 key present and all runs (base + 4 shifts) net-positive → 5/5
    sign agreement satisfies min_sign_agree=5; the sub-gate is active and passes."""
    monkeypatch.setattr(shift_mod, "available_range", lambda *a, **k: WIDE)
    ctx = _ctx_with_v002_key(tmp_path, _candidate(), min_sign_agree=5)
    monkeypatch.setattr(shift_mod, "rerun_candidate", _seq_rerun([_res(0.12)] * 4))
    outcome = ShiftedWindow().evaluate(_res(0.10), ctx)
    sub = outcome.evidence["sign_agreement_subgate"]
    assert sub["active"] is True
    assert sub["min_sign_agree"] == 5
    assert sub["sign_agree_count"] == 5      # base + 4 shifts all net-positive
    assert sub["subgate_pass"] is True
    assert outcome.passed


def test_sign_agreement_subgate_active_can_fail_the_verdict(tmp_path, monkeypatch):
    """Base net negative, all four shifts net-positive → only the base agrees with
    itself (count 1). With min_sign_agree=5 the sub-gate fails and the verdict is
    FAIL — proving the activated sub-gate is folded into `passed`."""
    monkeypatch.setattr(shift_mod, "available_range", lambda *a, **k: WIDE)
    ctx = _ctx_with_v002_key(tmp_path, _candidate(), min_sign_agree=5)
    base = build_result(returns_values=_returns_with_sr(-0.10))  # negative net base
    monkeypatch.setattr(shift_mod, "rerun_candidate", _seq_rerun([_res(0.12)] * 4))
    outcome = ShiftedWindow().evaluate(base, ctx)
    sub = outcome.evidence["sign_agreement_subgate"]
    assert sub["active"] is True
    assert sub["sign_agree_count"] == 1      # only the base agrees with itself
    assert sub["subgate_pass"] is False
    assert not outcome.passed
