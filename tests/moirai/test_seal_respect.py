"""test_seal_respect.py — probe G7: the holdout seal is respected (I4). Protected, CI.

A re-run stage whose evaluation window touches a SEALED range without a token must let
`SealedDataError` propagate UNCAUGHT — it is NEVER swallowed or caught-and-continued.
`run_gauntlet` turns that into an `ERRORED` verdict (record persisted per I11, then
re-raised). This is DISTINCT from stage 4.7's forward guard, which gracefully REFUSES a
shifted/auxiliary window that would enter sealed or past-data ranges: G7 is about a
stage running the candidate's OWN evaluation window on sealed data — being asked to
judge on the holdout — which must error, not quietly skip.

Nothing is sealed in production yet (Atropos seals in Phase 8); this constructs a seal
over the candidate's window via an injected registry.
"""

from datetime import datetime, timezone

import pytest

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.pipeline import run_gauntlet
from chronos.moirai.stages import CostStress
from chronos.moirai.types import ERRORED
from chronos.oceanus.access import SealedDataError
from chronos.oceanus.model import Timeframe
from chronos.oceanus.seal import SealRegistry
from chronos.run import Hypothesis, RunConfig
from tests.hephaestus.invariants.test_probes import ToyMomentum
from tests.moirai._noop import build_config, build_result

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)


def test_g7_sealed_window_errors_the_verdict(tmp_path, monkeypatch):
    base_config = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                            start=START, end=END, strategy_params={})
    candidate = Candidate(strategy=ToyMomentum(), base_config=base_config,
                          hypothesis=Hypothesis(id="H-seal", statement="x", prediction="y"))
    store = RecordStore(tmp_path / "records")
    cfg = build_config(("M4.5-cost-stress",), full_evaluation_mode=True)
    ctx = context_for_config(store, cfg, gauntlet_seed=1, candidate=candidate)

    # Seal the candidate's own evaluation window and inject the registry into the door.
    reg = SealRegistry(tmp_path / "seal.json")
    reg.seal("BTC/USDT", Timeframe.H1, START, END, "phase-8 holdout (constructed)")
    monkeypatch.setattr("chronos.oceanus.access.SealRegistry", lambda *a, **k: reg)

    result = build_result(returns_values=[0.0, 0.01, -0.01, 0.02], hypothesis_id="H-seal")

    # 4.5 re-runs the (now sealed) window → SealedDataError must propagate, not be caught.
    with pytest.raises(SealedDataError):
        run_gauntlet(result, {"M4.5-cost-stress": CostStress()}, ctx)

    # I11: an ERRORED verdict record was still persisted on the crash path.
    verdicts = [r for r in store.read_all() if r.get("type") == "gauntlet_verdict"]
    assert len(verdicts) == 1
    assert verdicts[0]["status"] == ERRORED
    assert "SealedDataError" in (verdicts[0]["cause_of_death"] or "")
