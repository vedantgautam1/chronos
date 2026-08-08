"""touchstones.py — the regression set T-a…T-e (SPEC §6), built on the Step-2 calibration
generator + isolated harness.

Each touchstone is a `build_t_*()` returning a `TouchstoneSpec` deterministic from pinned
seeds, with an immutable PRE-REGISTERED verdict + written rationale beside it. `judge()` runs
the spec's candidate through the full eleven-stage gauntlet in an ISOLATED calibration store
(never production; probe-G5 quarantine) and returns the verdict. The CI tests
(`tests/moirai/test_touchstones.py`) assert the pinned verdicts; any flip fails CI.

Build constraints (founder 2026-08-04, HANDOFF — the four forks):
  1. T-e builds from a COMMITTED provenance-stamped fixture, not `records/runs.jsonl`.
  2. Touchstone runs use a REDUCED `null_bench.n_nulls` (`TOUCHSTONE_N_NULLS`) via a DEV-CONFIG
     override layered on v001 — v001.json and its hash are UNTOUCHED; the frame is NOT shrunk
     (4.8 needs K≥2 twelve-month sub-windows).
  3. Coverage for 4.7/4.10 comes from a test-time `available_range` monkeypatch (the test_shift
     pattern, applied in `judge()`); synthetic candles are NEVER written to the production bar
     directory — they reach the engine via a synthetic `exchange=` into the isolated data root.
  4. T-a is NOT engineered to pass: its seed/window/params are pinned a priori; if honest S=3
     does not cleanly PASS all eleven gates, that is a gauntlet FINDING to surface, not a tune.

NO verdict-fitting: seeds, windows, and params below are chosen a priori and pinned. A
touchstone that does not return its pre-registered verdict is a finding, never a reseed cue.
"""

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np

from chronos.moirai import stages as _S
from chronos.moirai import statistics as stats
from chronos.moirai.calibration.generator import generate_frame, generate_regime_frame
from chronos.moirai.calibration.harness import CalibrationHarness, _SyntheticExchange
from chronos.moirai.config import load_config
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.nulls import NullStrategy, place_null_entries
from chronos.moirai.pipeline import run_gauntlet
from chronos.oceanus.access import available_range, get_bars
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunKind, register_search
from chronos.strategies.ma_crossover import MACrossover

_FIXTURES = Path(__file__).resolve().parent / "fixtures"

_V001_PATH = Path(__file__).resolve().parents[4] / "configs" / "gauntlet" / "v001.json"

FULL_PIPELINE = (
    "M4.0-eligibility", "M4.1-signal-null", "M4.2-plateau", "M4.3-dsr", "M4.4-shuffle",
    "M4.5-cost-stress", "M4.6-capacity", "M4.7-shift", "M4.8-subperiod", "M4.9-null-bench",
    "M4.10-descriptive",
)

# Fork-2: touchstone runs reduce the null count (v001 ships 200 for calibration/production).
# A dev-config override, NOT a v001 edit; the [0.2,0.8] T-d band stays meaningful at this count
# (band width 0.6 ≫ resolution 1/40 = 0.025).
TOUCHSTONE_N_NULLS = 40

_SYNTH = "SYNTH/USDT"

# The should-PASS canaries (T-a1, T-a2) cannot be pinned yet: the meta-finding below proves no
# honest strategy clears all eleven gates under the PROVISIONAL §14 thresholds (ruin_dd,
# subperiod, min_round_trips are mutually tensioned). A PASS scoped to the gates that happen to
# pass would be a canary rigged to always pass — it could never fail for the reason should-PASS
# touchstones exist. So their verdicts are DEFERRED and NOT asserted in CI; they pin only once
# Phase-6 calibration reconciles §14 and a genuine all-eleven PASS is achievable. Their measured
# eleven-stage tables are recorded as FINDINGS (SESSION_FINDINGS 2026-08-06).
PASS_DEFERRED = "BLOCKED-ON-PHASE-6-CALIBRATION"


def _registry() -> dict:
    return {
        "M4.0-eligibility": _S.Eligibility(), "M4.1-signal-null": _S.SignalNull(),
        "M4.2-plateau": _S.Plateau(), "M4.3-dsr": _S.DeflatedSharpe(),
        "M4.4-shuffle": _S.TradeShuffle(), "M4.5-cost-stress": _S.CostStress(),
        "M4.6-capacity": _S.Capacity(), "M4.7-shift": _S.ShiftedWindow(),
        "M4.8-subperiod": _S.SubPeriod(), "M4.9-null-bench": _S.NullBenchmark(),
        "M4.10-descriptive": _S.Descriptive(),
    }


def _dev_config(pipeline, *, full_eval, n_nulls=TOUCHSTONE_N_NULLS):
    """v001's frozen thresholds + a reduced touchstone null count + the chosen pipeline.
    v001.json is never edited — this is an in-memory dev override (its hash is irrelevant here;
    touchstones measure the INSTRUMENT, and verdict authority is NO_AUTHORITY until Phase 6)."""
    v = load_config(_V001_PATH)
    thresholds = {**v.thresholds, "null_bench.n_nulls": n_nulls}
    return replace(v, thresholds=thresholds, pipeline_order=tuple(pipeline),
                   full_evaluation_mode=full_eval)


@dataclass(frozen=True)
class TouchstoneSpec:
    name: str
    frame: object                 # synthetic OHLCV DataFrame (or None for stats-only T-e)
    frame_start: datetime
    frame_end: datetime
    base_config: RunConfig
    strategy: object
    hypothesis: Hypothesis
    gauntlet_seed: int
    prep: object = None           # optional callable(ctx, wrapped_run) to seed SEARCH records


def judge(spec: TouchstoneSpec, *, store_path, full_eval: bool,
          n_nulls: int = TOUCHSTONE_N_NULLS, pipeline=FULL_PIPELINE):
    """Run `spec`'s candidate through the full gauntlet in an ISOLATED store, serving the
    synthetic frame via a synthetic exchange into an isolated data root (never the production
    bar directory).
    Returns (verdict, base_result)."""
    harness = CalibrationHarness(store_path)  # raises if it resolves to the production store
    store = harness.store
    data_root = Path(store_path) / "synthdata"
    tf = spec.base_config.timeframe
    symbol = spec.base_config.symbol
    synth = _SyntheticExchange(spec.frame, tf)

    # Populate the isolated data root with the whole frame (one fetch through the door).
    get_bars(symbol, tf, spec.frame_start, spec.frame_end, root=data_root, exchange=synth)

    dev = _dev_config(pipeline, full_eval=full_eval, n_nulls=n_nulls)
    candidate = Candidate(strategy=spec.strategy, base_config=spec.base_config,
                          hypothesis=spec.hypothesis)
    ctx = context_for_config(store, dev, gauntlet_seed=spec.gauntlet_seed, candidate=candidate)

    original_run = ctx.run

    def wrapped(**kw):
        return original_run(data_root=data_root, exchange=synth, **kw)

    ctx.run = wrapped  # type: ignore[method-assign]

    if spec.prep is not None:
        spec.prep(ctx, wrapped, store, data_root, synth)

    base_rec = wrapped(kind=RunKind.VERIFICATION, config=spec.base_config,
                       strategy=spec.strategy, hypothesis=spec.hypothesis)
    base_result = base_rec.result

    def _cov(sym, timeframe, **k):
        return available_range(sym, timeframe, root=data_root)

    def _gb(*a, **k):
        return get_bars(*a, root=data_root, exchange=synth)

    with mock.patch("chronos.moirai.stages.shift.available_range", _cov), \
         mock.patch("chronos.moirai.stages.descriptive.available_range", _cov), \
         mock.patch("chronos.moirai.stages.descriptive.get_bars", _gb):
        verdict = run_gauntlet(base_result, _registry(), ctx)
    return verdict, base_result


# =====================================================================================
# T-a1 — faint should-PASS canary. Verdict: PASS_DEFERRED (BLOCKED-ON-PHASE-6-CALIBRATION).
# =====================================================================================
# §6 AMENDMENT (founder 2026-08-04/05): the original T-a "should-PASS on a faint edge" split into
# T-a1 (this) and T-a2 — a FRONT-LOADED gauntlet finding (see the meta-finding at PASS_DEFERRED
# above). T-a1 is a genuine, honestly-constructed faint edge (S=3, timeable per the SNR rule); it
# is NOT tuned. Its measured eleven-stage table (SESSION_FINDINGS 2026-08-06): edge-clarity gates
# 4.1/4.3/4.4/4.5/4.9 PASS, and 4.0 (INSUFFICIENT_BREADTH, 10 round trips) + 4.8 (subperiod) FAIL.
#
# Its verdict is NEITHER PASS NOR FAIL — it is PASS_DEFERRED. Reading it as PASS would require
# scoping out 4.0/4.8 (a canary rigged to always pass — it could never fail for the reason
# should-PASS touchstones exist). Reading it as FAIL would slander a good strategy: the edge is
# real and the gauntlet detects it — under the PROVISIONAL §14 thresholds T-a1 trips 4.0
# (min_round_trips=30, a deliberate frequency floor, NOT a hidden high-frequency assumption). Per
# the 2026-08-07 subperiod diagnostic, the 4.8 co-trip is a K=3 gate-(iii) artifact, NOT a
# frequency gate (4.8 fails T-a2 at 47 round trips): it resolves at K≈7 for T-a2 (touchstone fix,
# not gate) and stays unresolved for T-a1. T-a1 pins as a should-PASS regression ONLY once Phase-6
# decides min_round_trips (a policy call) and calibrates ruin_dd — subperiod is not a reconcile
# target (the precondition at PASS_DEFERRED). It certifies detectability at
# the SPECIFIC point (S=3, 45-day regimes, σ=0.60) — NOT "the ~2.3 floor" in general.
#   • T-a2 (below): a higher-frequency edge — the would-be clean all-eleven canary; also DEFERRED.
#
# Rationale (founder-approved redesign 2026-08-04): a pure-drift S=3 path is buy-and-hold —
# profitable but with no exploitable TIMING, so it structurally fails 4.1 (no signal variation)
# and 4.9 (random longs ride the same drift). Instead the fixture SWITCHES between a bull regime
# (within-regime annualized Sharpe +3) and a bear regime (−3), persistence ~21 days, σ=0.60. An
# MA harvests the bulls and sidesteps the bears — genuine timing that random long-only entries
# and an always-long signal cannot replicate, so 4.1/4.9 can distinguish it. A flip to FAIL means
# the gauntlet became too harsh or broke.
#
# NOT tuned to pass (fork 4): every fixture/strategy number below is fixed by an a-priori RULE,
# not searched against pass/fail. Two rules, both stated (founder-approved corrections, 2026-08-04):
#
#   (i) SNR rule for regime persistence — a regime edge is only TIMEABLE if its cumulative drift
#       exceeds the within-regime noise: L_bars ≥ 8760 / S². At S=3 that is ≥ ~41 days, so the
#       half-life is 45 days. (A 21-day regime is noise-dominated — SNR 0.72 < 1 — so no MA can
#       time it; that was the finding that produced this rule.)
#   (ii) MA timescale rule — slow = regime half-life in hours (45 d × 24 = 1080 h); fast = slow/4
#       = 270 h (the canonical 50/200-day 1:4 ratio). The MA speed follows the fixture's TIMESCALE
#       class, independent of the seed — NOT the milestone's arbitrary intraday params.
#
# σ is kept at the realistic 0.60: if 4.4 trips ruin_dd=0.40, that is the ruin_dd-vs-σ Phase-6
# calibration finding — LOGGED and surfaced, NOT resolved by lowering vol or changing D/MA. Frame
# is 3 years (K=3 twelve-month sub-windows for 4.8) plus a 3-week margin each side (4.7 shifts).
#
# SCOPE: T-a certifies detectability at the SPECIFIC point (S=3, 45-day regimes, σ=0.60) — not
# "the ~2.3 floor" in general.
TA1_FRAME_SEED = 314
TA1_GAUNTLET_SEED = 20260804
TA1_BULL_SHARPE = 3.0
TA1_BEAR_SHARPE = -3.0
TA1_HALF_LIFE_DAYS = 45  # SNR rule: ≥ 8760/S² ≈ 41 days at S=3 (regime move ≥ within-regime noise)
# Verdict is DEFERRED — not asserted in CI — until Phase-6 calibration (see PASS_DEFERRED above).
TA1_VERDICT = PASS_DEFERRED
# Gates observed PASSING at the recorded 2026-08-06 run — a FINDING, not a scoped assertion.
TA1_OBSERVED_EDGE_GATES_PASSED = ("M4.1-signal-null", "M4.3-dsr", "M4.4-shuffle",
                                  "M4.5-cost-stress", "M4.9-null-bench")
TA1_OBSERVED_FAILS = ("M4.0-eligibility", "M4.8-subperiod")  # provisional-threshold tension

# Strategy from the regime timescale, a priori (see rationale above).
_TA1_SLOW = TA1_HALF_LIFE_DAYS * 24         # 1080 h ≈ regime half-life
_TA1_FAST = _TA1_SLOW // 4                  # 270 h (1:4 canonical ratio)
_TA1_MA_PARAMS = {"fast": _TA1_FAST, "slow": _TA1_SLOW, "fraction": "0.95"}


def build_t_a1() -> TouchstoneSpec:
    base_start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    base_end = datetime(2023, 1, 1, tzinfo=timezone.utc)          # 3 years → K=3 for 4.8
    margin = timedelta(weeks=3)                                    # room for ±2-week shifts (4.7)
    frame_start = base_start - margin
    frame_end = base_end + margin
    n_bars = int((frame_end - frame_start) / Timeframe.H1.duration)
    frame = generate_regime_frame(
        bull_sharpe=TA1_BULL_SHARPE, bear_sharpe=TA1_BEAR_SHARPE,
        half_life_days=TA1_HALF_LIFE_DAYS, n_bars=n_bars, seed=TA1_FRAME_SEED, start=frame_start)
    base_config = RunConfig(symbol=_SYNTH, timeframe=Timeframe.H1, start=base_start,
                            end=base_end, strategy_params=dict(_TA1_MA_PARAMS))
    hypothesis = Hypothesis(
        id="T-a1-should-pass-regime",
        statement=f"A regime-timescale MA({_TA1_FAST}/{_TA1_SLOW}h) times a faint bull/bear regime "
                  "edge (within-regime annualized Sharpe ±3, 45-day persistence) — a genuine, "
                  "honestly-constructed edge the gauntlet should ultimately PASS.",
        prediction="Edge detected (4.1/4.3/4.4/4.5/4.9 pass); all-eleven PASS is DEFERRED "
                   "(BLOCKED-ON-PHASE-6-CALIBRATION) — provisional §14 (4.0/4.8) cannot yet judge "
                   "a faint low-frequency edge.")
    return TouchstoneSpec(name="T-a1", frame=frame, frame_start=frame_start, frame_end=frame_end,
                          base_config=base_config, strategy=MACrossover(symbol=_SYNTH),
                          hypothesis=hypothesis, gauntlet_seed=TA1_GAUNTLET_SEED)


# =====================================================================================
# T-a2 — higher-frequency should-PASS canary. Verdict: PASS_DEFERRED (BLOCKED-ON-PHASE-6-CALIB).
# =====================================================================================
# The complement to T-a1 (§6 amendment): a HIGHER-FREQUENCY regime edge intended to trade enough
# to clear 4.0 (≥30 round trips) AND pass every gate — the would-be clean all-eleven canary.
# A priori construction (NOT tuned to pass):
#   • regime half-life 12 days → over the 3-year base window ~90 regimes → the MA books enough
#     round trips for breadth (4.0 ≥30);
#   • S = ±6 from the SNR rule L ≥ 8760/S² (12 d = 288 bars ≥ 8760/36 = 243 → timeable, margin);
#   • MA by the timescale rule: slow = 12 d × 24 = 288 h, fast = slow/4 = 72 h; σ=0.60.
# Measured eleven-stage table (SESSION_FINDINGS 2026-08-06): 4.0 breadth CLEARS (47 round trips)
# and 4.1/4.3/4.5/4.6/4.7/4.9 PASS, but 4.4 (p95 maxDD 0.535 > ruin_dd 0.40, the ruin_dd-vs-σ
# finding) and 4.8 (subperiod) FAIL. So a clean all-eleven PASS does NOT exist even here — which
# is the meta-finding — but that claim (under provisional §14, no honest strategy clears all
# eleven) is UNTESTED at K≈7: it rests only on 4.0+4.4, and the 4.8 FAIL here is a K=3 gate-(iii)
# artifact, not a frequency gate (2026-08-07 diagnostic). Verdict is
# therefore PASS_DEFERRED (neither PASS — nothing scoped out — nor FAIL — the edge is real),
# pinned only once Phase-6 calibrates ruin_dd (4.4), decides min_round_trips (4.0, policy), and
# runs the all-eleven-K≈7 test — subperiod is not a reconcile target.
TA2_FRAME_SEED = 271
TA2_GAUNTLET_SEED = 20260805
TA2_BULL_SHARPE = 6.0
TA2_BEAR_SHARPE = -6.0
TA2_HALF_LIFE_DAYS = 12  # SNR: 8760/S² = 243 bars ≈ 10.1 d ≤ 12 d → timeable; ~90 regimes/3yr
TA2_VERDICT = PASS_DEFERRED
TA2_OBSERVED_GATES_PASSED = ("M4.0-eligibility", "M4.1-signal-null", "M4.3-dsr",
                             "M4.5-cost-stress", "M4.6-capacity", "M4.7-shift", "M4.9-null-bench")
TA2_OBSERVED_FAILS = ("M4.4-shuffle", "M4.8-subperiod")  # ruin_dd-vs-σ + subperiod tension

_TA2_SLOW = TA2_HALF_LIFE_DAYS * 24         # 288 h ≈ regime half-life
_TA2_FAST = _TA2_SLOW // 4                  # 72 h
_TA2_MA_PARAMS = {"fast": _TA2_FAST, "slow": _TA2_SLOW, "fraction": "0.95"}


def build_t_a2() -> TouchstoneSpec:
    base_start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    base_end = datetime(2023, 1, 1, tzinfo=timezone.utc)          # 3 years → K=3 for 4.8
    margin = timedelta(weeks=3)
    frame_start = base_start - margin
    frame_end = base_end + margin
    n_bars = int((frame_end - frame_start) / Timeframe.H1.duration)
    frame = generate_regime_frame(
        bull_sharpe=TA2_BULL_SHARPE, bear_sharpe=TA2_BEAR_SHARPE,
        half_life_days=TA2_HALF_LIFE_DAYS, n_bars=n_bars, seed=TA2_FRAME_SEED, start=frame_start)
    base_config = RunConfig(symbol=_SYNTH, timeframe=Timeframe.H1, start=base_start,
                            end=base_end, strategy_params=dict(_TA2_MA_PARAMS))
    hypothesis = Hypothesis(
        id="T-a2-clean-pass-regime",
        statement=f"A higher-frequency regime-timescale MA({_TA2_FAST}/{_TA2_SLOW}h) times a "
                  "bull/bear edge (within-regime annualized Sharpe ±6, 12-day persistence), "
                  "trading enough to clear breadth — a genuine edge the gauntlet should PASS.",
        prediction="Breadth + edge gates pass; all-eleven PASS is DEFERRED "
                   "(BLOCKED-ON-PHASE-6-CALIBRATION) — 4.4 (ruin_dd-vs-σ) and 4.8 remain.")
    return TouchstoneSpec(name="T-a2", frame=frame, frame_start=frame_start, frame_end=frame_end,
                          base_config=base_config, strategy=MACrossover(symbol=_SYNTH),
                          hypothesis=hypothesis, gauntlet_seed=TA2_GAUNTLET_SEED)


# =====================================================================================
# T-b — should-DIE: a rule curve-fit to noise. Verdict: FAIL, cause ∈ {4.2, 4.3}.
# =====================================================================================
# GATE A (founder 2026-08-04, HANDOFF): T-b proves the OVERFITTING gates — 4.2 (plateau)
# and 4.3 (deflated Sharpe at HONEST search-N) — kill a winner cherry-picked from a search
# over pure noise. The construction (founder decision 2026-08-07, Option 1): reuse the real
# MA crossover and SEARCH a fast×slow grid over a ZERO-EDGE synthetic frame, then judge the
# single best cell. This exercises the exact machinery the gate tests — honest search-N
# charging (NOT N=1) and plateau collapse — and mirrors the real laundering demo (T-e), whose
# winner was likewise a barely-positive searched MA cell. The spec's "8-parameter rule" wording
# was illustrative of overfitting CAPACITY, not a mechanism requirement; an 8-cell grid over 2
# knobs charges the same selection bias the gate exists to catch.
#
# HONEST N (fork condition 1): the whole grid is registered as `kind=SEARCH` records under ONE
# hypothesis (the candidate's), so `compute_search_n()` returns the grid size, NOT 1, and 4.3
# charges the winner at that N. `_tb_prep` re-runs the grid into the isolated store before the
# candidate is judged; the plateau (4.2) neighbors are all grid cells, so it reads them free and
# adds no new SEARCH — N stays exactly the grid size. The verdict, 4.3's `search_n_raw`, and the
# post-loop `compute_search_n` all coincide (the pipeline's divergence invariant).
#
# GATE A assertion (fork condition 2): run FULL-EVAL, PRINT the per-stage table, and pin
# `cause_of_death` on the OVERFIT gates {4.2, 4.3}. A noise winner fails several downstream gates
# too (4.1/4.9/4.8) in full-eval — that is expected — but the touchstone asserts ONLY that 4.2
# and/or 4.3 are among the failures, and NOT on 4.8 (its gate (ii) form is unratified per
# 2026-08-04). If 4.2 AND 4.3 both PASS and death is via 4.8/downstream only, that is a FINDING
# about the overfit gates — STOP and surface it, do not force the verdict.
#
# A-PRIORI (fork condition 3): the grid, the frame seed, and the zero-edge (target_sharpe=0.0)
# noise frame are all pinned below BEFORE any run. The winner is a deterministic function of
# them; `_tb_prep` asserts the search's argmax equals the pinned winner, so a code change that
# moves the winner fails loudly (a finding) rather than silently re-fitting. No seed-shopping.
_TB_FRAME_SEED = 20260202
_TB_GAUNTLET_SEED = 20260807
_TB_TARGET_SHARPE = 0.0  # PURE NOISE — zero injected edge; any IS profit is selection artifact.
# 8-cell fast×slow grid (all fast < slow). Registered as SEARCH → honest N = 8.
_TB_GRID_FAST = (10, 20, 30, 40)
_TB_GRID_SLOW = (80, 120)
_TB_GRID_DESC = (f"fast in [{', '.join(map(str, _TB_GRID_FAST))}] "
                 f"x slow in [{', '.join(map(str, _TB_GRID_SLOW))}]")
_TB_GRID_CELLS = tuple((f, s) for s in _TB_GRID_SLOW for f in _TB_GRID_FAST)
_TB_FRACTION = "0.95"

# Base evaluation window: 2 years → K=2 twelve-month sub-windows so 4.8 evaluates properly
# (its verdict is reported but NOT asserted — GATE A). ±3-week margins for 4.7 shifts.
_TB_BASE_START = datetime(2020, 1, 1, tzinfo=timezone.utc)
_TB_BASE_END = datetime(2022, 1, 1, tzinfo=timezone.utc)
_TB_MARGIN = timedelta(weeks=3)

# PINNED a priori (the deterministic search winner over the pinned grid/seed/frame; measured
# once, guarded by `_tb_prep`). Filled from the first honest run — NOT shopped.
TB_WINNER = (40, 120)  # (fast, slow) — the deterministic argmax of the pinned grid/seed/noise frame
TB_EXPECTED_N = len(_TB_GRID_CELLS)  # honest search-N charged at 4.3 (= grid size, 8)
TB_VERDICT = "FAIL"
# The overfit gates observed to fire (subset of {M4.2-plateau, M4.3-dsr}); filled from the run.
TB_OVERFIT_CAUSE_GATES = ("M4.2-plateau", "M4.3-dsr")
# 4.8 form is unratified per 2026-08-04; touchstones must not assert on 4.8 until v002 calibration.


def _tb_frame_window():
    frame_start = _TB_BASE_START - _TB_MARGIN
    frame_end = _TB_BASE_END + _TB_MARGIN
    return frame_start, frame_end


def _tb_build_frame():
    frame_start, frame_end = _tb_frame_window()
    n_bars = int((frame_end - frame_start) / Timeframe.H1.duration)
    return generate_frame(target_sharpe=_TB_TARGET_SHARPE, n_bars=n_bars,
                          seed=_TB_FRAME_SEED, start=frame_start), frame_start, frame_end


def _tb_cell_config(base_config, fast, slow):
    return replace(base_config, strategy_params={"fast": fast, "slow": slow,
                                                 "fraction": _TB_FRACTION})


def tb_grid_sharpes(base_config, strategy, hypothesis, wrapped) -> dict:
    """Run every grid cell as a `kind=SEARCH` record (one hypothesis family) over the isolated
    store, returning {(fast, slow): per-bar Sharpe}. The candidate the gauntlet later judges
    shares this hypothesis id, so `compute_search_n` counts exactly these SEARCH runs → honest N."""
    out: dict = {}
    for fast, slow in _TB_GRID_CELLS:
        rec = wrapped(kind=RunKind.SEARCH, config=_tb_cell_config(base_config, fast, slow),
                      strategy=strategy, hypothesis=hypothesis)
        r = rec.result.returns
        series = r.to_list() if hasattr(r, "to_list") else list(r)
        out[(fast, slow)] = stats.per_bar_sharpe([v for _, v in series] if series
                                                 and isinstance(series[0], (list, tuple))
                                                 else series)
    return out


def _tb_prep(ctx, wrapped, store, data_root, synth):
    """Register the fast×slow grid as SEARCH over the isolated store, then assert the honest
    search winner is the pinned cell (drift guard — a code change that moves it fails loudly)."""
    cand = ctx.candidate
    sharpes = tb_grid_sharpes(cand.base_config, cand.strategy, cand.hypothesis, wrapped)
    winner = max(sharpes, key=sharpes.__getitem__)
    if winner != TB_WINNER:
        raise AssertionError(
            f"T-b honest search winner {winner} (Sharpe {sharpes[winner]:.6g}) != pinned "
            f"TB_WINNER {TB_WINNER}. The grid/seed/frame are pinned a priori; a moved winner is "
            f"a FINDING to surface, not a reseed cue. Full grid: "
            f"{ {k: round(v, 6) for k, v in sharpes.items()} }")


def build_t_b() -> TouchstoneSpec:
    frame, frame_start, frame_end = _tb_build_frame()
    # The candidate IS the pinned winner cell; its hypothesis carries the grid description so
    # 4.2 parses the neighborhood and 4.3 deflates against the searched N.
    base_config = RunConfig(symbol=_SYNTH, timeframe=Timeframe.H1,
                            start=_TB_BASE_START, end=_TB_BASE_END,
                            strategy_params={"fast": TB_WINNER[0], "slow": TB_WINNER[1],
                                             "fraction": _TB_FRACTION})
    hypothesis = Hypothesis(
        id="T-b-overfit-noise",
        statement=(f"An MA crossover selected as the best of an {len(_TB_GRID_CELLS)}-cell "
                   f"fast×slow grid searched over a ZERO-EDGE noise frame — a winner that is "
                   f"pure selection artifact, beautiful in-sample, garbage out-of-sample."),
        prediction=("Dies at the overfitting gates: 4.2 (plateau — a lonely spike, not a broad "
                    "plateau) and/or 4.3 (deflated Sharpe crushed once the honest search-N is "
                    "charged). Verdict FAIL, cause ∈ {4.2, 4.3}. (Downstream gates also fail in "
                    "full-eval; 4.8 is NOT asserted — its form is unratified until v002.)"),
        param_grid_description=_TB_GRID_DESC)
    return TouchstoneSpec(name="T-b", frame=frame, frame_start=frame_start, frame_end=frame_end,
                          base_config=base_config, strategy=MACrossover(symbol=_SYNTH),
                          hypothesis=hypothesis, gauntlet_seed=_TB_GAUNTLET_SEED, prep=_tb_prep)


# =====================================================================================
# T-c — should-DIE via safety. Verdict: NON_PROMOTABLE, terminal at 4.0.
# =====================================================================================
# A deliberate future leak, constructed the SANCTIONED way (spec §6): the flag-gated
# `unsafe_same_bar_fill` path — orders filled at the very close the strategy just decided on.
# This never touches I1 (no-future-leakage stays intact in the trusted path); the engine stamps
# the `unsafe_same_bar_fill` honesty warning, and stage 4.0 turns that warning into a terminal
# NON_PROMOTABLE (probe G8's mechanism). If 4.0 ever stops reading the warning, this flips.
# Cheap: short-circuits at 4.0, so a short frame and no nulls (judged in short-circuit mode).
_TC_FRAME_SEED = 20260303
_TC_GAUNTLET_SEED = 20260807
_TC_START = datetime(2020, 1, 1, tzinfo=timezone.utc)
_TC_END = datetime(2020, 2, 1, tzinfo=timezone.utc)  # 31 days ≈ 744 H1 bars (short — dies at 4.0)
_TC_FRACTION = "0.95"
TC_VERDICT = "NON_PROMOTABLE"
TC_CAUSE = "M4.0-eligibility"


def build_t_c() -> TouchstoneSpec:
    n_bars = int((_TC_END - _TC_START) / Timeframe.H1.duration)
    frame = generate_frame(target_sharpe=_TB_TARGET_SHARPE, n_bars=n_bars,
                           seed=_TC_FRAME_SEED, start=_TC_START)
    base_config = RunConfig(symbol=_SYNTH, timeframe=Timeframe.H1, start=_TC_START, end=_TC_END,
                            strategy_params={"fast": 20, "slow": 50, "fraction": _TC_FRACTION},
                            unsafe_same_bar_fill=True)  # the sanctioned future-leak construction
    hypothesis = Hypothesis(
        id="T-c-unsafe-fill-leak",
        statement=("An MA crossover run with unsafe_same_bar_fill=True — a deliberate future "
                   "leak via the flag-gated path (I1 untouched), the sanctioned way to build one."),
        prediction=("Stage 4.0 reads the engine's unsafe warning and returns NON_PROMOTABLE, "
                    "terminal — the candidate never reaches a statistical gate."))
    return TouchstoneSpec(name="T-c", frame=frame, frame_start=_TC_START, frame_end=_TC_END,
                          base_config=base_config, strategy=MACrossover(symbol=_SYNTH),
                          hypothesis=hypothesis, gauntlet_seed=_TC_GAUNTLET_SEED)


# =====================================================================================
# T-d — null baseline: a seeded random strategy. Verdict: FAIL, 4.9 self-percentile ∈ [0.2, 0.8].
# =====================================================================================
# The null machinery's own smoke test: a genuinely random trader (the shipped price-blind
# `NullStrategy`, entries placed by chance at a pinned seed) should FAIL the gauntlet AND sit in
# the MIDDLE of the 4.9 null distribution — because it IS a null. Its 4.9 self-percentile (share
# of cadence-matched nulls it beats) must land in [0.2, 0.8]: an extreme percentile would mean the
# null benchmark is mis-calibrated (the candidate that is itself a null looks special). Run
# FULL-EVAL to reach 4.9; PRINT the actual percentile before pinning — if outside the band, surface
# it, do NOT reseed to fit (fork condition: whatever the honest seed produces is the result).
_TD_FRAME_SEED = 20260404
_TD_GAUNTLET_SEED = 20260807
_TD_STRATEGY_SEED = 4040  # seeds the random entry schedule (the strategy's own randomness)
_TD_BASE_START = datetime(2020, 1, 1, tzinfo=timezone.utc)
_TD_BASE_END = datetime(2022, 1, 1, tzinfo=timezone.utc)  # 2 years → K=2 for 4.8; enough for breadth
_TD_MARGIN = timedelta(weeks=3)
_TD_N_ENTRIES = 45                 # > min_round_trips (30) so it clears breadth and reaches 4.9
_TD_DURATIONS = (24, 48, 72)       # 1–3 day holds, resampled for the schedule
_TD_FRACTION = "0.95"
TD_VERDICT = "FAIL"
TD_SELF_PERCENTILE_BAND = (0.2, 0.8)  # 4.9 candidate_percentile_in_null_dist / 100 must land here


def _td_intervals(n_run_bars: int):
    rng = np.random.default_rng(_TD_STRATEGY_SEED)
    return place_null_entries(n_run_bars, _TD_DURATIONS, _TD_N_ENTRIES, rng)


def build_t_d() -> TouchstoneSpec:
    frame_start = _TD_BASE_START - _TD_MARGIN
    frame_end = _TD_BASE_END + _TD_MARGIN
    n_bars = int((frame_end - frame_start) / Timeframe.H1.duration)
    frame = generate_frame(target_sharpe=_TB_TARGET_SHARPE, n_bars=n_bars,
                           seed=_TD_FRAME_SEED, start=frame_start)
    n_run_bars = int((_TD_BASE_END - _TD_BASE_START) / Timeframe.H1.duration)
    intervals = _td_intervals(n_run_bars)
    base_config = RunConfig(symbol=_SYNTH, timeframe=Timeframe.H1,
                            start=_TD_BASE_START, end=_TD_BASE_END, strategy_params={})
    hypothesis = Hypothesis(
        id="T-d-null-baseline",
        statement=(f"A seeded random strategy (price-blind NullStrategy, {_TD_N_ENTRIES} entries "
                   f"placed by chance) traded over a zero-edge frame — a genuine null."),
        prediction=("FAILs the gauntlet, and its 4.9 self-percentile lands in [0.2, 0.8] — a null "
                    "sits in the middle of the null distribution; an extreme percentile would mean "
                    "the 4.9 benchmark is mis-calibrated."))
    return TouchstoneSpec(name="T-d", frame=frame, frame_start=frame_start, frame_end=frame_end,
                          base_config=base_config,
                          strategy=NullStrategy(symbol=_SYNTH, intervals=intervals,
                                                fraction=_TD_FRACTION),
                          hypothesis=hypothesis, gauntlet_seed=_TD_GAUNTLET_SEED)


# =====================================================================================
# T-e — the laundering demo as regression. Verdict: DSR@N=1 > DSR@N=280, and DSR@N=280 < 0.95.
# =====================================================================================
# THE project-defining counterfactual, pinned into CI forever: the 280-sweep winner's REAL
# returns (0.5630 vs 0.0542 on real BTC data) — the identical Sharpe reads as "56% chance of
# skill" at N=1 and "5% chance" at the honest N=280. If any change makes the cherry-picked winner
# pass at honest N, or fail at N=1, the trial-ontology machinery is damaged and the build stops.
#
# FORM — the HONEST two-part inequality, NOT the §6 chained form. Spec §6 writes
# `DSR@N=1 > dsr.confidence > DSR@N=280`, i.e. `0.5630 > 0.95 > 0.0542` — but 0.5630 !> 0.95, a
# CONFIRMED v002 defect (2026-08-04 HANDOFF): the winner's N=1 DSR need not clear the 0.95 gate,
# it only needs to be MUCH HIGHER than the honest-N reading while the honest reading sits below
# the gate. So T-e asserts the two independent facts the demo actually shows:
#     (1) DSR@N=1 (0.5630)  >  DSR@N=280 (0.0542)    — laundering inflates the score ~10×;
#     (2) DSR@N=280 (0.0542)  <  dsr.confidence (0.95) — the honest reading correctly rejects.
#
# FIXTURE (fork condition 1): built from a COMMITTED, provenance-stamped fixture
# (`fixtures/te_laundering_winner.json`) — the winner's per-bar returns extracted ONCE from
# records/runs.jsonl (gitignored, 119 MB), NOT read live. Stats-only: no engine, no gauntlet run
# (<1 s). The shipped `statistics.dsr` is asserted (the point is to pin the SHIPPED code).
#
# PHASE-7 DEPENDENCY: the fixture is LEGACY (kind=None sweep records, pre-284). Phase 7 re-runs
# the 280 sweep live under kind=SEARCH so `compute_search_n` re-establishes N=280 end-to-end, then
# T-e re-pins against live records and this fixture retires (see MOIRAI_BUILD_BRIEF Phase 7).
_TE_FIXTURE = _FIXTURES / "te_laundering_winner.json"
TE_V = 8.659587301602424e-05       # cross-trial variance of the 280 sweep's per-bar Sharpes
TE_N_HONEST = 280                  # the search that produced the winner (spec §6, SESSION_FINDINGS)
TE_N_NAIVE = 1.0001                # "as if a single pre-registered hypothesis" (N=1 proxy; SR*→0)
TE_DSR_CONFIDENCE = 0.95           # v001 dsr.confidence gate
# Pinned reproduced values (the canonical laundering numbers, SESSION_FINDINGS 2026-07-16).
TE_DSR_N1 = 0.5630
TE_DSR_N280 = 0.0542


def evaluate_t_e() -> dict:
    """Compute the laundering demo from the committed fixture using the SHIPPED statistics.dsr.
    Returns the two DSR readings plus cross-checks. Pure math — no engine, no store."""
    fx = json.loads(_TE_FIXTURE.read_text())
    returns = np.asarray(fx["returns"], float)
    sr_hat = stats.per_bar_sharpe(returns)
    T = returns.size
    # Cross-check: the fixture's pinned sr_hat/T match a fresh recompute from its raw returns
    # (guards against fixture corruption or a per_bar_sharpe change).
    assert T == fx["T_bars"], f"fixture T {fx['T_bars']} != recomputed {T}"
    assert abs(sr_hat - fx["sr_hat_per_bar"]) < 1e-12, "fixture sr_hat drifted from returns"
    # At N≈1 the expected-max SR* floors to 0, so V is immaterial there; use the measured V for
    # both so a single honest V drives the whole demo.
    dsr_n1 = float(stats.dsr(sr_hat, T=T, V=TE_V, N=TE_N_NAIVE))
    dsr_n280 = float(stats.dsr(sr_hat, T=T, V=TE_V, N=TE_N_HONEST))
    return {
        "sr_hat_per_bar": sr_hat, "T": T, "V": TE_V,
        "dsr_at_n1": dsr_n1, "dsr_at_n280": dsr_n280,
        "dsr_confidence": TE_DSR_CONFIDENCE,
        "cell": fx["cell"], "trial_index": fx["trial_index"],
        "laundering_holds": bool(dsr_n1 > dsr_n280 and dsr_n280 < TE_DSR_CONFIDENCE),
    }
