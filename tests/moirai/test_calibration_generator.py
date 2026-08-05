"""test_calibration_generator.py — the synthetic-candle generator (spec §7.2). Protected.

Covers: frames are Oceanus-VALID (no hard integrity issues); deterministic under a fixed
seed; the known-answer self-test — over 1,000 seeded draws at each ladder rung the realized
annualized log-return Sharpe centers on the target S within ±0.05; S=0 is a true zero-edge
path; and the provenance stamp.
"""

import numpy as np
import pandas as pd
import pytest

from chronos.moirai.calibration.generator import (
    GENERATOR_VERSION,
    generate_frame,
    provenance,
    realized_annualized_sharpe,
)
from chronos.oceanus.access import HARD_FAILURES
from chronos.oceanus.model import Timeframe
from chronos.oceanus.validate import validate

LADDER = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0]  # calib.effect_ladder


def test_frame_is_oceanus_valid():
    frame = generate_frame(target_sharpe=1.0, n_bars=2000, seed=7)
    # structural: low <= open/close <= high, positive prices, tz-aware, contiguous
    assert (frame["low"] <= frame[["open", "close"]].min(axis=1)).all()
    assert (frame["high"] >= frame[["open", "close"]].max(axis=1)).all()
    assert (frame[["open", "high", "low", "close"]] > 0).all().all()
    assert (frame["volume"] > 0).all()
    assert frame["open_time"].dt.tz is not None
    report = validate(frame, Timeframe.H1)
    hard = [i for i in report.issues if i.kind in HARD_FAILURES]
    assert not hard, f"generator produced Oceanus-invalid data: {[i.message for i in hard]}"


def test_deterministic_under_fixed_seed():
    a = generate_frame(target_sharpe=1.5, n_bars=500, seed=42)
    b = generate_frame(target_sharpe=1.5, n_bars=500, seed=42)
    pd.testing.assert_frame_equal(a, b)
    c = generate_frame(target_sharpe=1.5, n_bars=500, seed=43)
    assert not a["close"].equals(c["close"])  # a different seed differs


def test_realized_sharpe_centers_on_target():
    """KNOWN-ANSWER (spec §7.2): 1,000 seeded draws per ladder rung; the mean realized
    annualized Sharpe sits within ±0.05 of the target. n_bars chosen so the standard error
    of the mean (≈ √(bpy/n)/√M) leaves ~3σ of headroom against 0.05 — no seed-shopping."""
    M, n_bars = 1000, 35040  # 4 years of H1 → SE ≈ 0.016 → ~3σ under 0.05
    master = np.random.SeedSequence(2026).spawn(len(LADDER) * M)
    k = 0
    for s in LADDER:
        realized = []
        for _ in range(M):
            seed = int(master[k].generate_state(1)[0])
            k += 1
            frame = generate_frame(target_sharpe=s, n_bars=n_bars, seed=seed)
            realized.append(realized_annualized_sharpe(frame))
        mean = float(np.mean(realized))
        assert abs(mean - s) <= 0.05, (
            f"rung S={s}: mean realized annualized Sharpe {mean:.4f} outside ±0.05 "
            f"(SE≈{np.std(realized)/np.sqrt(M):.4f}) — investigate, do NOT reseed")


def test_s0_is_zero_edge():
    frame = generate_frame(target_sharpe=0.0, n_bars=8760, seed=99)
    # a single S=0 draw is noisy, but its magnitude should be modest (well within a
    # few annualized units) — a gross departure would mean the drift wiring is wrong.
    assert abs(realized_annualized_sharpe(frame)) < 2.0


def test_provenance_stamp():
    # version AND the volume-snapshot id, so synthetic runs trace to their data source
    assert provenance() == f"synthetic:{GENERATOR_VERSION}@7c0b19aa"
    assert provenance().startswith("synthetic:")
    assert "@" in provenance()
