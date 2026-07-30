"""Phase 3 — the pipeline skeleton's trust suite (spec §9). Protected path.

Covers probes G1 (verdict determinism, I10) and G4 (no unlogged judgment, I11),
plus DAG ordering, short-circuit, full-evaluation mode, the ctx.run wrapper
(kind-forcing + I9 stamp + SEARCH freeze), and authority propagation.

The two throwaway no-op Moirai and the deterministic fixtures live in
`tests/moirai/_noop.py` (deleted in Phase 4a).
"""

import subprocess
import sys
import textwrap
from datetime import timedelta
from pathlib import Path

import pytest

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import (
    SearchFrozenError,
    context_for_config,
)
from chronos.moirai.pipeline import MoiraRegistryError, run_gauntlet
from chronos.moirai.types import (
    AUTHORITATIVE,
    ERRORED,
    FAIL,
    INSUFFICIENT_BREADTH,
    NON_PROMOTABLE,
    NO_AUTHORITY,
    PASS,
    verdict_determinism_view,
)
from chronos.run import Hypothesis, RunConfig, RunKind
from chronos.oceanus.model import Timeframe
from tests.moirai._noop import (
    AlwaysFail,
    AlwaysPass,
    CrashMoira,
    InsufficientBreadthMoira,
    NonPromotableMoira,
    build_config,
    build_fixture_result,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ctx(tmp_path, pipeline_order, *, full_evaluation_mode=False, is_calibrated=False,
         seed=1234):
    store = RecordStore(tmp_path / "records")
    config = build_config(pipeline_order, full_evaluation_mode=full_evaluation_mode)
    return store, context_for_config(store, config, seed, is_calibrated=is_calibrated)


# --- Probe G1 — verdict determinism (I10) --------------------------------------

def test_g1_verdict_determinism(tmp_path):
    """Identical inputs + seed, run twice, the second run in a FRESH PROCESS →
    byte-identical verdict_determinism_view(). The fresh process catches machine-
    state dependence (dict ordering, hash randomization) an in-process re-run
    would miss (pattern from tests/moirai/test_config.py::cross_process)."""
    order = ("noop-always-pass", "noop-always-fail")
    store, ctx = _ctx(tmp_path / "a", order, seed=777)
    result = build_fixture_result()
    moirai = {"noop-always-pass": AlwaysPass(), "noop-always-fail": AlwaysFail()}

    verdict = run_gauntlet(result, moirai, ctx, search_n=280, effective_n=None)
    in_process_view = verdict_determinism_view(verdict)

    # Second judgment, fresh interpreter, its own temp store.
    sub_store = tmp_path / "b" / "records"
    code = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(REPO_ROOT)!r})
        from chronos.mnemosyne.stub import RecordStore
        from chronos.moirai.context import context_for_config
        from chronos.moirai.pipeline import run_gauntlet
        from chronos.moirai.types import verdict_determinism_view
        from tests.moirai._noop import (
            AlwaysPass, AlwaysFail, build_config, build_fixture_result,
        )
        store = RecordStore({str(sub_store)!r})
        config = build_config(("noop-always-pass", "noop-always-fail"))
        ctx = context_for_config(store, config, 777)
        result = build_fixture_result()
        moirai = {{"noop-always-pass": AlwaysPass(), "noop-always-fail": AlwaysFail()}}
        verdict = run_gauntlet(result, moirai, ctx, search_n=280, effective_n=None)
        sys.stdout.write(verdict_determinism_view(verdict))
    """)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=REPO_ROOT)
    assert out.returncode == 0, out.stderr
    assert out.stdout == in_process_view  # byte-identical across processes


def test_g1_strip_set_is_exactly_three_fields(tmp_path):
    """The determinism view strips verdict_id, judged_at and per-outcome runtime_s
    — and nothing else. Two verdicts differing ONLY in those three must compare
    equal; a verdict differing in any compared field must not."""
    order = ("noop-always-pass",)
    store, ctx = _ctx(tmp_path, order)
    result = build_fixture_result()
    moirai = {"noop-always-pass": AlwaysPass()}

    v1 = run_gauntlet(result, moirai, ctx, search_n=5)
    v2 = run_gauntlet(result, moirai, ctx, search_n=5)
    # v2 has a later verdict_id, a later judged_at, and different runtimes — yet:
    assert v1.verdict_id != v2.verdict_id
    assert verdict_determinism_view(v1) == verdict_determinism_view(v2)

    # A different search_n IS compared (it is a coordinate, not bookkeeping):
    v3 = run_gauntlet(result, moirai, ctx, search_n=6)
    assert verdict_determinism_view(v3) != verdict_determinism_view(v1)


# --- Probe G4 — no unlogged judgment (I11) -------------------------------------

def test_g4_no_unlogged_judgment(tmp_path):
    """A crash mid-pipeline persists the per-stage outcomes gathered so far plus
    an ERRORED verdict with the error text, then re-raises. No PASS verdict is
    ever written for a crashed run."""
    order = ("noop-always-pass", "noop-crash", "noop-always-fail")
    store, ctx = _ctx(tmp_path, order)
    result = build_fixture_result()
    moirai = {
        "noop-always-pass": AlwaysPass(),
        "noop-crash": CrashMoira(),
        "noop-always-fail": AlwaysFail(),
    }

    with pytest.raises(RuntimeError, match="gauntlet probe crash"):
        run_gauntlet(result, moirai, ctx, search_n=1)

    records = store.read_all()
    outcome_recs = [r for r in records if r["type"] == "gauntlet_outcome"]
    verdict_recs = [r for r in records if r["type"] == "gauntlet_verdict"]

    # The AlwaysPass stage completed before the crash → its outcome record persists.
    assert [r["moira_id"] for r in outcome_recs] == ["noop-always-pass"]
    assert outcome_recs[0]["passed"] is True

    # Exactly one verdict, ERRORED, carrying the error text; never a PASS.
    assert len(verdict_recs) == 1
    assert verdict_recs[0]["status"] == ERRORED
    assert "gauntlet probe crash" in verdict_recs[0]["cause_of_death"]
    assert not any(r["status"] == PASS for r in verdict_recs)
    # The partial outcome survives inside the verdict too.
    assert verdict_recs[0]["outcomes"][0]["moira_id"] == "noop-always-pass"


# --- DAG ordering --------------------------------------------------------------

def test_outcomes_follow_pipeline_order_not_dict_order(tmp_path):
    """Outcomes appear in pipeline_order even when the moirai dict is built in a
    different order (spec §3.2 — the order is part of the hashed config)."""
    order = ("s3", "s1", "s2")
    store, ctx = _ctx(tmp_path, order)
    result = build_fixture_result()
    # dict insertion order deliberately scrambled relative to pipeline_order.
    moirai = {
        "s1": AlwaysPass("s1"),
        "s2": AlwaysPass("s2"),
        "s3": AlwaysPass("s3"),
    }
    verdict = run_gauntlet(result, moirai, ctx, search_n=1)
    assert [o.moira_id for o in verdict.outcomes] == ["s3", "s1", "s2"]
    assert verdict.status == PASS


def test_missing_moira_raises(tmp_path):
    """A moira_id in the order with no registered Moira → clear error, no silent skip."""
    order = ("present", "absent")
    store, ctx = _ctx(tmp_path, order)
    result = build_fixture_result()
    with pytest.raises(MoiraRegistryError, match="absent"):
        run_gauntlet(result, {"present": AlwaysPass("present")}, ctx, search_n=1)


# --- Short-circuit -------------------------------------------------------------

def test_short_circuit_marks_downstream_not_executed(tmp_path):
    """AlwaysFail at position 2 → positions 3+ recorded executed=False; none of
    the un-run stages is recorded as passed (spec §3.2 ordering-artifact)."""
    order = ("s1", "s2-fail", "s3", "s4")
    store, ctx = _ctx(tmp_path, order)
    result = build_fixture_result()
    moirai = {
        "s1": AlwaysPass("s1"),
        "s2-fail": AlwaysFail("s2-fail"),
        "s3": AlwaysPass("s3"),
        "s4": AlwaysPass("s4"),
    }
    verdict = run_gauntlet(result, moirai, ctx, search_n=1)

    by_id = {o.moira_id: o for o in verdict.outcomes}
    assert by_id["s1"].executed and by_id["s1"].passed
    assert by_id["s2-fail"].executed and not by_id["s2-fail"].passed
    assert not by_id["s3"].executed and not by_id["s3"].passed
    assert not by_id["s4"].executed and not by_id["s4"].passed
    assert verdict.status == FAIL
    assert verdict.cause_of_death == "s2-fail"

    # Only executed stages get outcome records in the store.
    outcome_recs = [r for r in store.read_all() if r["type"] == "gauntlet_outcome"]
    assert [r["moira_id"] for r in outcome_recs] == ["s1", "s2-fail"]


# --- Full-evaluation mode ------------------------------------------------------

def test_full_eval_runs_everything_and_lists_all_failures(tmp_path):
    """full_evaluation_mode → all stages execute regardless of failures;
    cause_of_death is the ordered, joined list of every failing moira_id."""
    order = ("s1-fail", "s2", "s3-fail")
    store, ctx = _ctx(tmp_path, order, full_evaluation_mode=True)
    result = build_fixture_result()
    moirai = {
        "s1-fail": AlwaysFail("s1-fail"),
        "s2": AlwaysPass("s2"),
        "s3-fail": AlwaysFail("s3-fail"),
    }
    verdict = run_gauntlet(result, moirai, ctx, search_n=1)
    assert all(o.executed for o in verdict.outcomes)
    assert verdict.status == FAIL
    assert verdict.cause_of_death == "s1-fail,s3-fail"


# --- Terminal statuses ---------------------------------------------------------

def test_non_promotable_terminal_zero_downstream(tmp_path):
    """A NON_PROMOTABLE signal is terminal even in full-evaluation mode: zero
    downstream stages execute, regardless of every other score (spec §3.2)."""
    order = ("s1", "s2-nonpromotable", "s3")
    store, ctx = _ctx(tmp_path, order, full_evaluation_mode=True)
    result = build_fixture_result()
    moirai = {
        "s1": AlwaysPass("s1"),
        "s2-nonpromotable": NonPromotableMoira("s2-nonpromotable"),
        "s3": AlwaysPass("s3"),
    }
    verdict = run_gauntlet(result, moirai, ctx, search_n=1)
    assert verdict.status == NON_PROMOTABLE
    assert verdict.cause_of_death == "s2-nonpromotable"
    by_id = {o.moira_id: o for o in verdict.outcomes}
    assert not by_id["s3"].executed  # terminal even under full-eval


def test_insufficient_breadth_status(tmp_path):
    """An INSUFFICIENT_BREADTH signal yields that distinct status, not FAIL."""
    order = ("s1-breadth", "s2")
    store, ctx = _ctx(tmp_path, order)
    result = build_fixture_result()
    moirai = {
        "s1-breadth": InsufficientBreadthMoira("s1-breadth"),
        "s2": AlwaysPass("s2"),
    }
    verdict = run_gauntlet(result, moirai, ctx, search_n=1)
    assert verdict.status == INSUFFICIENT_BREADTH
    assert verdict.cause_of_death == "s1-breadth"


def test_all_pass_is_pass(tmp_path):
    order = ("s1", "s2")
    store, ctx = _ctx(tmp_path, order)
    result = build_fixture_result()
    verdict = run_gauntlet(
        result, {"s1": AlwaysPass("s1"), "s2": AlwaysPass("s2")}, ctx, search_n=1
    )
    assert verdict.status == PASS
    assert verdict.cause_of_death is None


# --- ctx.run wrapper -----------------------------------------------------------

def _toy_strategy():
    from tests.hephaestus.invariants.test_probes import ToyMomentum
    return ToyMomentum()


def _run_config():
    START = build_fixture_result().date_range[0]
    return RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                     start=START, end=START + timedelta(hours=50))


def test_ctx_run_stamps_gauntlet_config_hash(tmp_path):
    """A run triggered through ctx.run produces an engine record whose
    gauntlet_config_hash equals the active config's hash (I9 anchor closed)."""
    from tests.oceanus.test_ingest import FakeExchange

    store, ctx = _ctx(tmp_path, ("s1",))
    fake = FakeExchange(int(_run_config().start.timestamp() * 1000), n_bars=50)
    ctx.run(kind=RunKind.VERIFICATION, config=_run_config(), strategy=_toy_strategy(),
            hypothesis=Hypothesis(id="H-ctx", statement="s", prediction="p"),
            data_root=tmp_path / "data", exchange=fake)
    runs = [r for r in store.read_all() if r["type"] == "run"]
    assert runs and runs[0]["gauntlet_config_hash"] == ctx.gauntlet_config_hash


def test_ctx_run_forces_explicit_kind(tmp_path):
    """Calling ctx.run without kind= raises TypeError — discipline, not a default."""
    store, ctx = _ctx(tmp_path, ("s1",))
    with pytest.raises(TypeError):
        ctx.run(config=_run_config(), strategy=_toy_strategy(),
                hypothesis=Hypothesis(id="H", statement="s", prediction="p"))


def test_ctx_run_refuses_search_after_freeze(tmp_path):
    """With N frozen, ctx.run(kind=SEARCH) raises; VERIFICATION still works (G6b)."""
    from tests.oceanus.test_ingest import FakeExchange

    store, ctx = _ctx(tmp_path, ("s1",))
    ctx.freeze_search()
    with pytest.raises(SearchFrozenError):
        ctx.run(kind=RunKind.SEARCH, config=_run_config(), strategy=_toy_strategy(),
                hypothesis=Hypothesis(id="H", statement="s", prediction="p"))
    # VERIFICATION is unaffected.
    fake = FakeExchange(int(_run_config().start.timestamp() * 1000), n_bars=50)
    ctx.run(kind=RunKind.VERIFICATION, config=_run_config(), strategy=_toy_strategy(),
            hypothesis=Hypothesis(id="H2", statement="s", prediction="p"),
            data_root=tmp_path / "data", exchange=fake)
    assert any(r.get("kind") == "VERIFICATION"
               for r in store.read_all() if r["type"] == "run")


# --- Authority propagation -----------------------------------------------------

def test_authority_no_authority_when_uncalibrated(tmp_path):
    """A verdict written under an uncalibrated config carries NO_AUTHORITY."""
    store, ctx = _ctx(tmp_path, ("s1",), is_calibrated=False)
    verdict = run_gauntlet(build_fixture_result(), {"s1": AlwaysPass("s1")}, ctx,
                           search_n=1)
    assert verdict.authority == NO_AUTHORITY


def test_authority_authoritative_when_calibrated(tmp_path):
    """When the activation guard reports calibrated, the stamp is AUTHORITATIVE."""
    store, ctx = _ctx(tmp_path, ("s1",), is_calibrated=True)
    verdict = run_gauntlet(build_fixture_result(), {"s1": AlwaysPass("s1")}, ctx,
                           search_n=1)
    assert verdict.authority == AUTHORITATIVE


# --- Coordinates present -------------------------------------------------------

def test_verdict_carries_every_reproducibility_coordinate(tmp_path):
    """The stored verdict record contains every I10 coordinate, populated."""
    store, ctx = _ctx(tmp_path, ("s1",))
    result = build_fixture_result()
    run_gauntlet(result, {"s1": AlwaysPass("s1")}, ctx, search_n=280,
                 effective_n=41.2)
    rec = [r for r in store.read_all() if r["type"] == "gauntlet_verdict"][0]
    for key in ("gauntlet_config_hash", "moirai_code_version", "engine_core_version",
                "data_snapshot_hash", "gauntlet_seed", "search_n", "effective_n",
                "evaluation_window", "judged_at", "authority", "verdict_id",
                "judged_run_id", "hypothesis_id", "status"):
        assert key in rec, f"missing coordinate: {key}"
    assert rec["engine_core_version"] == result.core_version
    assert rec["data_snapshot_hash"] == result.data_snapshot_hash
    assert rec["search_n"] == 280
    assert rec["effective_n"] == 41.2
    assert rec["evaluation_window"] == [result.date_range[0].isoformat(),
                                        result.date_range[1].isoformat()]
