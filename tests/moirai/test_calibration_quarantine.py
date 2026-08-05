"""test_calibration_quarantine.py — probe G5 (calibration quarantine, spec §7.2). Protected.

Two halves:
  1. the harness constructor REFUSES the production records directory (or an ancestor);
  2. a full synthetic ladder run through the harness leaves a separate (production-like)
     store's `trial_counter.txt` byte-identical and every `compute_search_n()` output
     unchanged — synthetic runs are structurally isolated (distinct RecordStore root, and
     synthetic candles land in the harness's own data root, never `data/bars/`).
"""

from pathlib import Path

import pytest

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.calibration import CalibrationHarness, ProductionStoreError
from chronos.moirai.calibration.generator import generate_frame
from chronos.run import DEFAULT_RECORDS_DIR, Hypothesis, RunKind, compute_search_n
from chronos.strategies.ma_crossover import MACrossover

SYNTH = "SYNTH/USDT"


def test_g5_refuses_production_store():
    with pytest.raises(ProductionStoreError):
        CalibrationHarness(DEFAULT_RECORDS_DIR)                 # the production store itself
    with pytest.raises(ProductionStoreError):
        CalibrationHarness(DEFAULT_RECORDS_DIR.resolve().parent)  # an ancestor (repo root)


def test_g5_allows_distinct_store(tmp_path):
    h = CalibrationHarness(tmp_path / "calib")
    assert h.store_path == (tmp_path / "calib").resolve()
    assert h.data_root == (tmp_path / "calib").resolve() / "data"


def test_g5_ladder_leaves_production_untouched(tmp_path):
    # A production-like store with one SEARCH record and an advanced counter.
    prod = RecordStore(tmp_path / "prod")
    prod.append({"type": "run", "run_id": "000001-H-prod", "kind": "SEARCH",
                 "hypothesis_id": "H-prod", "status": "COMPLETED"})
    prod.next_trial_index()  # counter -> 1
    counter_before = (tmp_path / "prod" / "trial_counter.txt").read_bytes()
    n_before = compute_search_n("H-prod", prod)
    assert n_before == 1

    # A full mini synthetic ladder into a DISTINCT calibration store.
    harness = CalibrationHarness(tmp_path / "calib")
    hyp = Hypothesis(id="H-synth", statement="synthetic calibration draw",
                     prediction="reporting-only")
    ran = 0
    for s in (0.0, 1.0, 3.0):
        frame = generate_frame(target_sharpe=s, n_bars=200, seed=100 + int(s * 10))
        cr = harness.run_synthetic(MACrossover(symbol=SYNTH), frame, hyp,
                                   RunKind.VERIFICATION, symbol=SYNTH,
                                   strategy_params={"fast": 5, "slow": 20, "fraction": "0.95"})
        assert cr.data_provenance == "synthetic:v1@7c0b19aa"
        ran += 1
    assert ran == 3

    # Production store is byte-identical and its N is unchanged.
    assert (tmp_path / "prod" / "trial_counter.txt").read_bytes() == counter_before
    assert compute_search_n("H-prod", prod) == n_before

    # The synthetic runs DID land in the calibration store, and its data is quarantined.
    calib_runs = [r for r in harness.store.read_all() if r.get("type") == "run"]
    assert len(calib_runs) == 3
    assert any(harness.data_root.rglob("*.parquet"))  # synthetic parquet isolated here
