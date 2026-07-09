"""Phase 6 tests: the sole door's guarantees — I3 (every run logged),
I6 (every trial counted), I8 (hypothesis first), plus the coordinates."""

from datetime import timedelta
from decimal import Decimal

import pytest

from chronos.hephaestus.engine import _execute
from chronos.mnemosyne.stub import RecordStore
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunStatus, run_experiment
from tests.oceanus.test_ingest import FakeExchange

from .scaffolding import BuyOnceStrategy, DoNothingStrategy
from .test_view import START

HYPOTHESIS = Hypothesis(
    id="H-test-001",
    statement="loop fixtures execute end to end",
    prediction="flat or slightly negative equity; this is plumbing, not alpha",
)


def config(n_hours=48, seed=0):
    return RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                     start=START, end=START + timedelta(hours=n_hours), seed=seed)


def run(tmp_path, strategy=None, cfg=None, store=None):
    store = store or RecordStore(tmp_path / "records")
    fake = FakeExchange(int(START.timestamp() * 1000), n_bars=200)
    record = run_experiment(strategy or DoNothingStrategy(), cfg or config(),
                            HYPOTHESIS, store=store,
                            data_root=tmp_path / "data", exchange=fake)
    return record, store


class CrashingStrategy:
    def on_bar(self, view, ctx):
        raise RuntimeError("deliberate mid-run crash")


def test_no_hypothesis_no_run(tmp_path):
    with pytest.raises(TypeError, match="Hypothesis"):
        run_experiment(DoNothingStrategy(), config(), hypothesis=None,
                       store=RecordStore(tmp_path))


def test_empty_hypothesis_fields_are_refused():
    with pytest.raises(ValueError, match="non-empty"):
        Hypothesis(id="H-1", statement="   ", prediction="x")


def test_completed_run_is_recorded_with_full_coordinates(tmp_path):
    record, store = run(tmp_path)
    assert record.status is RunStatus.COMPLETED
    assert record.trial_index == 1

    runs = [r for r in store.read_all() if r["type"] == "run"]
    assert len(runs) == 1
    persisted = runs[0]
    assert persisted["status"] == "COMPLETED"
    assert len(persisted["config_hash"]) == 64  # sha256 hex
    assert len(persisted["data_snapshot_hash"]) == 64
    assert persisted["core_version"] not in (None, "")  # git SHA (+ -dirty)
    assert persisted["seed"] == 0
    assert persisted["result"]["bars_processed"] == 48


def test_hypothesis_is_persisted_before_the_run_record(tmp_path):
    _, store = run(tmp_path)
    types = [r["type"] for r in store.read_all()]
    assert types == ["hypothesis", "run"]  # registration precedes outcome (I8)


def test_crashed_run_yields_persisted_errored_record_and_reraises(tmp_path):
    store = RecordStore(tmp_path / "records")
    with pytest.raises(RuntimeError, match="deliberate mid-run crash"):
        run(tmp_path, strategy=CrashingStrategy(), store=store)

    runs = [r for r in store.read_all() if r["type"] == "run"]
    assert len(runs) == 1
    assert runs[0]["status"] == "ERRORED"
    assert "deliberate mid-run crash" in runs[0]["error"]
    assert runs[0]["result"] is None


def test_n_runs_advance_counter_by_exactly_n_including_errors(tmp_path):
    store = RecordStore(tmp_path / "records")
    run(tmp_path, store=store)
    run(tmp_path, store=store)
    with pytest.raises(RuntimeError):
        run(tmp_path, strategy=CrashingStrategy(), store=store)
    assert store.trial_count == 3  # the crash counts (I6)
    trial_indices = [r["trial_index"] for r in store.read_all() if r["type"] == "run"]
    assert trial_indices == [1, 2, 3]


def test_records_resist_mutation(tmp_path):
    _, store = run(tmp_path)
    first_read = store.read_all()
    first_read[0]["type"] = "tampered"
    first_read[0]["trial_index"] = 999
    assert store.read_all()[0]["type"] == "hypothesis"  # store unchanged
    # And the store's whole write surface is append + read:
    assert not any(hasattr(store, m) for m in ("update", "delete", "rewrite"))


def test_private_execute_raises_without_the_door(tmp_path):
    with pytest.raises(PermissionError, match="run_experiment"):
        _execute({}, Timeframe.H1, DoNothingStrategy(), None, None, None)


def test_result_carries_hypothesis_link_and_warnings(tmp_path):
    record, _ = run(tmp_path, strategy=BuyOnceStrategy(qty=Decimal("0.1")))
    assert record.result.hypothesis_id == "H-test-001"
    assert record.result.trial_index == record.trial_index
    assert any("provisional_cost_constants" in w for w in record.result.warnings)
    assert len(record.result.trades) == 1
    assert record.result.returns.iloc[0] == 0.0
