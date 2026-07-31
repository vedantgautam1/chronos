"""Phase 4a — the three free stages and probe G8 (spec §4.0, §4.3, §4.4, §9).

Protected path (tests/moirai/). Covers: 4.0 breadth (INSUFFICIENT_BREADTH) and the
fragmentation screen (union N); 4.3 evidence (raw-N and effective-N, D-08 guard,
the un-frozen-N note); 4.4 the hand-enumerable 4-trade shuffle fixture (24 paths,
terminal-equity invariance); and G8 (unsafe → NON_PROMOTABLE, zero downstream even
under full_evaluation_mode).
"""

import itertools
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from chronos.hephaestus.engine import UNSAFE_SAME_BAR_WARNING
from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.context import context_for_config
from chronos.moirai.pipeline import run_gauntlet
from chronos.moirai.round_trips import reconstruct_round_trips
from chronos.moirai.stages import DeflatedSharpe, Eligibility, TradeShuffle
from chronos.moirai.stages.trade_shuffle import equity_path, max_drawdown
from chronos.moirai.types import (
    INSUFFICIENT_BREADTH,
    NON_PROMOTABLE,
    TERMINAL_STATUS_KEY,
)
from tests.moirai._noop import (
    build_config,
    build_result,
    build_round_trip_fills,
)

PROVISIONAL_WARNING = (
    "provisional_cost_constants: spread/slippage values are configured guesses"
)


def _ctx(tmp_path, order, *, full_evaluation_mode=False, seed=1234):
    store = RecordStore(tmp_path / "records")
    config = build_config(order, full_evaluation_mode=full_evaluation_mode)
    return store, context_for_config(store, config, seed)


# --- 4.0 Eligibility -----------------------------------------------------------

def test_eligibility_breadth_29_trips_is_insufficient(tmp_path):
    """A 29-round-trip result (below min_round_trips=30) → INSUFFICIENT_BREADTH."""
    store, ctx = _ctx(tmp_path, ("M4.0-eligibility",))
    fills = build_round_trip_fills([1.01] * 29)  # 29 clean round trips
    result = build_result(trades=fills)
    outcome = Eligibility().evaluate(result, ctx)
    assert outcome.executed
    assert not outcome.passed
    assert outcome.evidence[TERMINAL_STATUS_KEY] == INSUFFICIENT_BREADTH
    assert outcome.evidence["round_trips"] == 29


def test_eligibility_30_trips_passes(tmp_path):
    """Exactly min_round_trips (30) → passes the breadth gate."""
    store, ctx = _ctx(tmp_path, ("M4.0-eligibility",))
    result = build_result(trades=build_round_trip_fills([1.01] * 30))
    outcome = Eligibility().evaluate(result, ctx)
    assert outcome.passed
    assert outcome.evidence["round_trips"] == 30
    assert TERMINAL_STATUS_KEY not in outcome.evidence


def test_eligibility_provisional_flag_recorded(tmp_path):
    """A provisional_cost_constants warning is recorded (for stage 4.5 later)."""
    store, ctx = _ctx(tmp_path, ("M4.0-eligibility",))
    result = build_result(trades=build_round_trip_fills([1.01] * 30),
                          warnings=(PROVISIONAL_WARNING,))
    outcome = Eligibility().evaluate(result, ctx)
    assert outcome.evidence["provisional_cost_constants"] is True


def test_eligibility_incompleteness_fails(tmp_path):
    """A returns/bars_processed mismatch → plain FAIL with a clear reason (not a
    terminal status)."""
    store, ctx = _ctx(tmp_path, ("M4.0-eligibility",))
    result = build_result(trades=build_round_trip_fills([1.01] * 30),
                          returns_values=[0.0, 0.0, 0.0], bars_processed=999)
    outcome = Eligibility().evaluate(result, ctx)
    assert not outcome.passed
    assert TERMINAL_STATUS_KEY not in outcome.evidence
    assert any("bars_processed" in f for f in outcome.evidence["completeness_failures"])


def test_eligibility_fragmentation_screen_union_n(tmp_path):
    """Two hypotheses, same grid axes, adjacent grids, registered close together,
    each with SEARCH runs → fragmentation warning with the CORRECT union N."""
    from chronos.run import (
        Hypothesis,
        RunConfig,
        RunKind,
        register_search,
        run_experiment,
    )
    from chronos.oceanus.model import Timeframe
    from tests.oceanus.test_ingest import FakeExchange
    from tests.hephaestus.invariants.test_probes import ToyMomentum

    store, ctx = _ctx(tmp_path, ("M4.0-eligibility",))
    START = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def sweep(hyp_id, grid, n):
        hyp = register_search(
            Hypothesis(id=hyp_id, statement="s", prediction="p"),
            param_grid_description=grid)
        for _ in range(n):
            fake = FakeExchange(int(START.timestamp() * 1000), n_bars=40)
            cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                            start=START, end=START + timedelta(hours=40))
            run_experiment(ToyMomentum(), cfg, hyp, kind=RunKind.SEARCH,
                           store=store, data_root=tmp_path / "data", exchange=fake)

    # Family A (the candidate) with 2 SEARCH runs; sibling family B with 3.
    sweep("H-A-ma", "fast in range(5,55,5) x slow in range(60,200,5)", 2)
    sweep("H-B-ma", "fast in range(10,60,5) x slow in range(65,205,5)", 3)

    result = build_result(trades=build_round_trip_fills([1.01] * 30),
                          hypothesis_id="H-A-ma")
    outcome = Eligibility().evaluate(result, ctx)
    frag = outcome.evidence["possible_search_fragmentation"]
    assert frag["sibling_ids"] == ["H-B-ma"]
    assert frag["union_n"] == 5  # 2 (A) + 3 (B)
    assert frag["shared_axes"] == ["fast", "slow"]


# --- 4.3 Deflated Sharpe -------------------------------------------------------

def test_dsr_evidence_raw_and_effective_n_no_siblings(tmp_path):
    """With no SEARCH siblings (compute_search_n == 0): raw N recorded as 0, the
    deflation N floored to 1, effective_n not_estimable, and the un-frozen note."""
    store, ctx = _ctx(tmp_path, ("M4.3-dsr",))
    # A losing series (like the milestone) → DSR small, gate fails.
    rng = np.random.default_rng(0)
    returns = list(rng.normal(-1e-5, 3e-3, 500))
    result = build_result(returns_values=returns, hypothesis_id="H-standalone")
    outcome = DeflatedSharpe().evaluate(result, ctx)

    ev = outcome.evidence
    assert ev["search_n_raw"] == 0
    assert ev["n_used_for_deflation"] == 1
    assert ev["n_frozen"] is False
    assert ev["effective_n"] == "not_estimable"
    assert ev["V"] == "not_estimable"
    assert "dsr_at_raw_n" in ev
    assert outcome.score == ev["dsr_at_raw_n"]
    assert not outcome.passed  # a losing strategy fails the confidence gate
    # The note must state, IN WORDS, the flooring, the explicit guard, and Phase 7.
    note = ev["deflation_note"]
    assert "floored to 1" in note
    assert "N<2" in note and "nan" in note  # names the explicit guard + its reason
    assert "Phase 7" in note


def test_dsr_effective_n_estimated_with_siblings(tmp_path):
    """With >= 2 aligned SEARCH siblings and M < T/2, effective_n is a number and
    DSR@N-hat is stamped; the gate still reads raw N."""
    from chronos.run import (
        Hypothesis,
        RunConfig,
        RunKind,
        register_search,
        run_experiment,
    )
    from chronos.oceanus.model import Timeframe
    from tests.oceanus.test_ingest import FakeExchange
    from tests.hephaestus.invariants.test_probes import ToyMomentum

    store, ctx = _ctx(tmp_path, ("M4.3-dsr",))
    START = datetime(2026, 1, 1, tzinfo=timezone.utc)
    hyp = register_search(Hypothesis(id="H-swept", statement="s", prediction="p"),
                          param_grid_description="fast in range(5,10,1)")
    for _ in range(4):
        fake = FakeExchange(int(START.timestamp() * 1000), n_bars=60)
        cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                        start=START, end=START + timedelta(hours=60))
        run_experiment(ToyMomentum(), cfg, hyp, kind=RunKind.SEARCH,
                       store=store, data_root=tmp_path / "data", exchange=fake)

    # The candidate's return series must ALIGN with the siblings' (same window,
    # same length) for the JPM Appendix-C pairwise correlation — take the sibling
    # length from the store rather than guessing it.
    sibling_len = len(next(
        r["result"]["returns"] for r in store.read_all()
        if r.get("type") == "run" and r.get("kind") == "SEARCH"))
    returns = list(np.random.default_rng(1).normal(1e-4, 2e-3, sibling_len))
    result = build_result(returns_values=returns, hypothesis_id="H-swept")
    outcome = DeflatedSharpe().evaluate(result, ctx)
    ev = outcome.evidence
    assert ev["search_n_raw"] == 4
    assert ev["n_used_for_deflation"] == 4
    assert ev["V_estimable"] is True
    assert isinstance(ev["effective_n"], float)
    assert "dsr_at_effective_n" in ev
    assert ev["effective_n"] <= 4  # N-hat <= M, always
    # Real-deflation branch: the note states real deflation and NEVER mentions Phase 7
    # or N-flooring ("SR* floored at 0" is legitimate and refers to sr_star, not N).
    note = ev["deflation_note"]
    assert "Real multiple-testing deflation applied" in note
    assert "Phase 7" not in note
    assert "N floored" not in note


# --- 4.4 Trade-shuffle: the hand-enumerable 4-trade fixture --------------------

# Four per-trip return factors chosen so the distribution is enumerable by hand.
# 4! = 24 orderings. Terminal factor = 1.10*0.90*1.05*0.80 = 0.8316 for ALL of them
# (product commutes) — that invariance is the implementation check.
_FOUR_FACTORS = [1.10, 0.90, 1.05, 0.80]


def test_shuffle_terminal_equity_invariant_across_all_24(tmp_path):
    """Order-invariance: terminal equity is identical across all 4! = 24 shuffles
    (the spec's own doubles-as-implementation-check assertion)."""
    terminals = {
        round(float(equity_path(np.array(list(perm)))[-1]), 12)
        for perm in itertools.permutations(_FOUR_FACTORS)
    }
    assert len(terminals) == 1
    assert terminals == {round(1.10 * 0.90 * 1.05 * 0.80, 12)}


def test_shuffle_maxdd_matches_hand_enumeration(tmp_path):
    """The stage's shuffled maxDD distribution must be drawn from EXACTLY the 24
    hand-enumerable path drawdowns. Every shuffle's maxDD is one of those 24."""
    store, ctx = _ctx(tmp_path, ("M4.4-shuffle",))
    fills = build_round_trip_fills(_FOUR_FACTORS)
    result = build_result(trades=fills)

    # Confirm reconstruction recovers the four factors exactly (fee-free build).
    rts = reconstruct_round_trips(fills)
    assert [round(rt.factor, 10) for rt in rts] == [round(f, 10) for f in _FOUR_FACTORS]

    # The 24 exact hand-enumerable maxDDs (independent oracle).
    oracle = {
        round(max_drawdown(equity_path(np.array(list(perm)))), 12)
        for perm in itertools.permutations(_FOUR_FACTORS)
    }
    outcome = TradeShuffle().evaluate(result, ctx)
    # ruin_dd default 0.40; worst-case maxDD here is 1-0.90*0.80=0.28 < 0.40 → pass.
    assert outcome.passed
    assert outcome.evidence["terminal_equity"] == pytest.approx(0.8316, abs=1e-9)
    # p95 band is one of the enumerable values (the whole distribution is those 24).
    assert round(outcome.evidence["risk_band_drawdown"], 12) in oracle
    # honest limitations present, verbatim in substance.
    assert "order-invariant" in outcome.evidence["limitations"]["terminal_equity_order_invariant"]
    assert "proportional sizing" in outcome.evidence["limitations"]["proportional_sizing_assumption"]


def test_shuffle_deterministic_under_seed(tmp_path):
    """Fixed ctx.rng seed → identical shuffled distribution (I10)."""
    fills = build_round_trip_fills(_FOUR_FACTORS)
    result = build_result(trades=fills)
    store1, ctx1 = _ctx(tmp_path / "a", ("M4.4-shuffle",), seed=42)
    store2, ctx2 = _ctx(tmp_path / "b", ("M4.4-shuffle",), seed=42)
    o1 = TradeShuffle().evaluate(result, ctx1)
    o2 = TradeShuffle().evaluate(result, ctx2)
    assert o1.evidence["percentile_table"] == o2.evidence["percentile_table"]
    assert o1.evidence["risk_band_drawdown"] == o2.evidence["risk_band_drawdown"]


# --- Probe G8 — unsafe non-promotability ---------------------------------------

def test_g8_unsafe_non_promotable_zero_downstream_even_full_eval(tmp_path):
    """An unsafe-flagged result → NON_PROMOTABLE, with 4.3 and 4.4 recorded
    executed=False EVEN under full_evaluation_mode (terminal at 4.0, §3.2)."""
    order = ("M4.0-eligibility", "M4.3-dsr", "M4.4-shuffle")
    store, ctx = _ctx(tmp_path, order, full_evaluation_mode=True)
    result = build_result(
        trades=build_round_trip_fills([1.01] * 30),
        warnings=(UNSAFE_SAME_BAR_WARNING,),
    )
    moirai = {
        "M4.0-eligibility": Eligibility(),
        "M4.3-dsr": DeflatedSharpe(),
        "M4.4-shuffle": TradeShuffle(),
    }
    verdict = run_gauntlet(result, moirai, ctx, search_n=0)
    assert verdict.status == NON_PROMOTABLE
    assert verdict.cause_of_death == "M4.0-eligibility"
    by_id = {o.moira_id: o for o in verdict.outcomes}
    assert by_id["M4.0-eligibility"].executed
    assert not by_id["M4.3-dsr"].executed
    assert not by_id["M4.4-shuffle"].executed
    # No outcome record for the downstream stages was written to the store.
    outcome_recs = [r for r in store.read_all() if r["type"] == "gauntlet_outcome"]
    assert [r["moira_id"] for r in outcome_recs] == ["M4.0-eligibility"]
