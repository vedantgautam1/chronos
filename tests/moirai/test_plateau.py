"""test_plateau.py — stage 4.2 parameter plateau + N finalization, and probe G6.

Protected path (tests/moirai/). Covers 4.2's branches (flat-plateau PASS, overfit
spike FAIL, grid_unparseable, no-grid no_neighborhood_defined PASS, no-grid
undeclared_search_breadth FAIL), the freeze-on-every-exit guarantee, and probe G6:
  G6a fragmentation fixture → union-N warning (via stage 4.0);
  G6b ctx.run(kind=SEARCH) after 4.2 → SearchFrozenError;
  G6c a plateau neighbor run ⇒ compute_search_n +1 ⇒ 4.3 reads the FROZEN N ⇒ SR*
      strictly above what the stale N would give (broken wiring fails this test).
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai import statistics as stats
from chronos.moirai.context import Candidate, SearchFrozenError, context_for_config
from chronos.moirai.stages import DeflatedSharpe, Eligibility, Plateau
from chronos.moirai.pipeline import run_gauntlet
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunKind, compute_search_n
from chronos.strategies.ma_crossover import MACrossover
from tests.moirai._noop import build_config, build_result
from tests.oceanus.test_ingest import FakeExchange

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
GRID = "fast in range(10,35,5)"          # [10, 15, 20, 25, 30]; candidate fast=20


# --- fixtures ------------------------------------------------------------------

def _returns_with_sharpe(sr, *, T=200, scale=1e-2):
    """A deterministic return series with per-bar Sharpe ≈ `sr` (mean sr·scale,
    std ≈ scale) via a fixed two-value alternation — no RNG, exactly reproducible."""
    mu = sr * scale
    return list(np.tile([mu + scale, mu - scale], T // 2))


def _seed_search(store, hyp_id, fast, returns_values, *, slow=50):
    """Append a COMPLETED SEARCH run record for one neighbor grid point — the shape
    `compute_search_n`, 4.2's `_stored_search_sharpes`, and 4.3's V reader consume."""
    n = len(returns_values)
    idx = [(START + timedelta(hours=i)).isoformat() for i in range(n)]
    store.append({
        "type": "run", "run_id": f"seed-f{fast}", "trial_index": 1000 + fast,
        "status": "COMPLETED", "kind": "SEARCH", "error": None,
        "hypothesis_id": hyp_id,
        "config": {"strategy_params": {"fast": fast, "slow": slow}},
        "result": {
            "returns": [[idx[i], returns_values[i]] for i in range(n)],
            "date_range": [idx[0], idx[-1]],
        },
    })


def _candidate(hyp_id, grid, *, strategy=None, fast=20, slow=50):
    hyp = Hypothesis(id=hyp_id, statement="plateau", prediction="broad",
                     param_grid_description=grid)
    cfg = RunConfig(symbol="BTC/USDT", timeframe=Timeframe.H1,
                    start=START, end=START + timedelta(hours=120),
                    strategy_params={"fast": fast, "slow": slow})
    return Candidate(strategy=strategy or object(), base_config=cfg, hypothesis=hyp)


def _ctx(tmp_path, order, candidate, *, seed=1234, full=False):
    store = RecordStore(tmp_path / "records")
    cfg = build_config(order, full_evaluation_mode=full)
    ctx = context_for_config(store, cfg, gauntlet_seed=seed, candidate=candidate)
    return store, ctx


# --- 4.2 branches --------------------------------------------------------------

def test_flat_plateau_passes(tmp_path):
    """Neighbors all near the candidate's Sharpe → median ≥ 0.5×candidate, no cliff."""
    store, ctx = _ctx(tmp_path, ("M4.2-plateau",), _candidate("H-flat", GRID))
    for fast in (10, 15, 25, 30):
        _seed_search(store, "H-flat", fast, _returns_with_sharpe(0.10))
    result = build_result(returns_values=_returns_with_sharpe(0.10),
                          hypothesis_id="H-flat")
    outcome = Plateau().evaluate(result, ctx)
    assert outcome.passed
    assert outcome.evidence["median_ok"] and outcome.evidence["cliff_ok"]
    assert len(outcome.evidence["neighbors_read_free"]) == 4
    assert outcome.evidence["neighbors_run_as_search"] == []
    assert ctx.search_frozen  # N finalized regardless of verdict


def test_overfit_spike_fails_with_plateau_cause(tmp_path):
    """A lonely spike: candidate Sharpe high, every neighbor negative → cliff + median
    both fail. Cause is M4.2-plateau."""
    store, ctx = _ctx(tmp_path, ("M4.2-plateau",), _candidate("H-spike", GRID))
    for fast in (10, 15, 25, 30):
        _seed_search(store, "H-spike", fast, _returns_with_sharpe(-0.05))
    result = build_result(returns_values=_returns_with_sharpe(0.30),
                          hypothesis_id="H-spike")
    outcome = Plateau().evaluate(result, ctx)
    assert not outcome.passed
    assert not outcome.evidence["median_ok"]
    assert not outcome.evidence["cliff_ok"]
    assert outcome.evidence["neighbor_negative_fraction"] > 0.25
    assert ctx.search_frozen


def test_grid_unparseable_fails_without_guessing(tmp_path):
    store, ctx = _ctx(tmp_path, ("M4.2-plateau",),
                      _candidate("H-bad", "fast in wibblewobble"))
    result = build_result(returns_values=_returns_with_sharpe(0.10),
                          hypothesis_id="H-bad")
    outcome = Plateau().evaluate(result, ctx)
    assert not outcome.passed
    assert outcome.evidence["reason"] == "grid_unparseable"
    assert ctx.search_frozen


def test_candidate_off_grid_is_grid_unparseable(tmp_path):
    """Candidate params not located on the parsed grid → ambiguity → grid_unparseable
    (never guessed)."""
    store, ctx = _ctx(tmp_path, ("M4.2-plateau",),
                      _candidate("H-off", GRID, fast=22))  # 22 not in [10,15,20,25,30]
    result = build_result(returns_values=_returns_with_sharpe(0.10),
                          hypothesis_id="H-off")
    outcome = Plateau().evaluate(result, ctx)
    assert not outcome.passed
    assert outcome.evidence["reason"] == "grid_unparseable"
    assert "not on parsed grid" in outcome.evidence["grid_unparseable_detail"]


def test_no_grid_no_breadth_passes_no_neighborhood_defined(tmp_path):
    """A genuinely pre-registered single point (no grid, no SEARCH breadth) → PASS
    with the founder-mandated no_neighborhood_defined note (never implies exemption)."""
    store, ctx = _ctx(tmp_path, ("M4.2-plateau",), _candidate("H-solo", None))
    result = build_result(returns_values=_returns_with_sharpe(0.05),
                          hypothesis_id="H-solo")
    outcome = Plateau().evaluate(result, ctx)
    assert outcome.passed
    assert outcome.evidence["reason"] == "no_neighborhood_defined"
    note = outcome.evidence["no_neighborhood_note"]
    assert "No countable SEARCH breadth" in note
    assert "NOT a blessing or exemption" in note
    assert ctx.search_frozen


def test_no_grid_with_search_breadth_flags_undeclared(tmp_path):
    """No grid, YET kind=SEARCH records exist under this hypothesis → a searched point
    wearing a pre-registered label → undeclared_search_breadth FAIL (fires on
    kind=SEARCH, never on legacy kind=None)."""
    store, ctx = _ctx(tmp_path, ("M4.2-plateau",), _candidate("H-sneaky", None))
    _seed_search(store, "H-sneaky", 20, _returns_with_sharpe(0.10))
    _seed_search(store, "H-sneaky", 25, _returns_with_sharpe(0.12))
    result = build_result(returns_values=_returns_with_sharpe(0.10),
                          hypothesis_id="H-sneaky")
    outcome = Plateau().evaluate(result, ctx)
    assert not outcome.passed
    assert outcome.evidence["reason"] == "undeclared_search_breadth"
    assert outcome.evidence["search_n_at_4.2"] == 2


def test_legacy_kind_none_does_not_trigger_undeclared(tmp_path):
    """A legacy sweep record (NO kind key) must NOT trip undeclared_search_breadth —
    compute_search_n excludes it by construction (founder condition b)."""
    store, ctx = _ctx(tmp_path, ("M4.2-plateau",), _candidate("H-legacy", None))
    store.append({  # legacy run: no 'kind' key at all
        "type": "run", "run_id": "legacy-1", "trial_index": 100,
        "status": "COMPLETED", "hypothesis_id": "H-legacy",
        "config": {"strategy_params": {"fast": 20, "slow": 50}},
        "result": {"returns": [], "date_range": None},
    })
    result = build_result(returns_values=_returns_with_sharpe(0.05),
                          hypothesis_id="H-legacy")
    outcome = Plateau().evaluate(result, ctx)
    assert outcome.passed
    assert outcome.evidence["reason"] == "no_neighborhood_defined"


# --- Probe G6b — SEARCH refused after 4.2 --------------------------------------

def test_g6b_search_refused_after_plateau(tmp_path):
    store, ctx = _ctx(tmp_path, ("M4.2-plateau",), _candidate("H-freeze", None))
    result = build_result(returns_values=_returns_with_sharpe(0.05),
                          hypothesis_id="H-freeze")
    Plateau().evaluate(result, ctx)          # runs 4.2 → freezes
    assert ctx.search_frozen
    with pytest.raises(SearchFrozenError):
        ctx.run(kind=RunKind.SEARCH, config=ctx.candidate.base_config,
                strategy=ctx.candidate.strategy, hypothesis=ctx.candidate.hypothesis)


# --- Probe G6a — fragmentation → union-N (stage 4.0) ---------------------------

def test_g6a_fragmentation_union_n_via_eligibility(tmp_path):
    """A candidate whose grid axes match a sibling hypothesis registered in-window →
    4.0 stamps possible_search_fragmentation with the UNION N. Confirms the 4a
    mechanism still holds under 4b."""
    store, ctx = _ctx(tmp_path, ("M4.0-eligibility",),
                      _candidate("H-cand", GRID))
    now = START.isoformat()
    for hid in ("H-cand", "H-sibling"):
        store.append({"type": "hypothesis", "run_id": f"h-{hid}", "trial_index": 1,
                      "registered_at": now,
                      "hypothesis": {"id": hid, "statement": "s", "prediction": "p",
                                     "param_grid_description": GRID}})
    _seed_search(store, "H-cand", 20, _returns_with_sharpe(0.1))
    _seed_search(store, "H-sibling", 15, _returns_with_sharpe(0.1))
    result = build_result(trades=(), returns_values=_returns_with_sharpe(0.1),
                          hypothesis_id="H-cand", bars_processed=200)
    # give it enough round trips to clear breadth is unnecessary; we only read the
    # fragmentation evidence, which is stamped regardless.
    outcome = Eligibility().evaluate(result, ctx)
    frag = outcome.evidence.get("possible_search_fragmentation")
    assert frag is not None
    assert "H-sibling" in frag["sibling_ids"]
    assert frag["union_n"] == 2  # one SEARCH under each of the two hypotheses


# --- Probe G6c — neighbor run ⇒ N+1 ⇒ 4.3 reads the FROZEN N --------------------

def _with_fake(ctx, tmp_path, n_bars=120):
    fake = FakeExchange(int(START.timestamp() * 1000), n_bars=n_bars, page_limit=500)
    original = ctx.run

    def patched(**kw):
        return original(data_root=tmp_path / "data", exchange=fake, **kw)

    ctx.run = patched  # type: ignore[method-assign]


def test_g6c_neighbor_run_increments_n_and_4_3_reads_frozen_n(tmp_path):
    """THE critical probe. Pre-seed 3 of 4 neighbors (N=3); 4.2 runs the missing one
    (N→4) and freezes; 4.3 reads the frozen N=4. SR* at the frozen N=4 is strictly
    above SR* at the stale N=3, so a broken freeze→4.3 wiring (which would leave
    search_n_raw=3) fails this test — as does the run_gauntlet divergence invariant."""
    candidate = _candidate("H-g6c", GRID, strategy=MACrossover())
    store, ctx = _ctx(tmp_path, ("M4.2-plateau", "M4.3-dsr"), candidate, full=True)
    # Seed 3 neighbors with DISTINCT Sharpes → V estimable and stable (N=3).
    _seed_search(store, "H-g6c", 10, _returns_with_sharpe(0.05))
    _seed_search(store, "H-g6c", 15, _returns_with_sharpe(0.10))
    _seed_search(store, "H-g6c", 25, _returns_with_sharpe(0.15))
    assert compute_search_n("H-g6c", store) == 3       # pre-4.2 N

    result = build_result(returns_values=_returns_with_sharpe(0.12),
                          hypothesis_id="H-g6c")
    _with_fake(ctx, tmp_path)
    verdict = run_gauntlet(result, {"M4.2-plateau": Plateau(),
                                    "M4.3-dsr": DeflatedSharpe()}, ctx)

    # 4.2 ran exactly the one un-seeded neighbor (fast=30) → N incremented by 1.
    plateau_ev = next(o for o in verdict.outcomes if o.moira_id == "M4.2-plateau").evidence
    assert len(plateau_ev["neighbors_run_as_search"]) == 1
    assert len(plateau_ev["neighbors_read_free"]) == 3
    assert compute_search_n("H-g6c", store) == 4       # post-4.2 N (frozen)

    dsr_ev = next(o for o in verdict.outcomes if o.moira_id == "M4.3-dsr").evidence
    assert dsr_ev["search_n_raw"] == 4                 # 4.3 read the FROZEN N, not 3
    assert dsr_ev["n_used_for_deflation"] == 4
    assert dsr_ev["n_frozen"] is True
    assert verdict.search_n == 4                        # divergence invariant held

    # SR* strictly rises with the frozen N: stale N=3 would give a strictly lower bar.
    V = dsr_ev["V"]
    assert stats.sr_star(V, 4) > stats.sr_star(V, 3)
