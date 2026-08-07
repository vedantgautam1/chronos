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

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from chronos.moirai import stages as _S
from chronos.moirai.calibration.generator import generate_frame, generate_regime_frame
from chronos.moirai.calibration.harness import CalibrationHarness, _SyntheticExchange
from chronos.moirai.config import load_config
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.pipeline import run_gauntlet
from chronos.oceanus.access import available_range, get_bars
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunKind
from chronos.strategies.ma_crossover import MACrossover

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
# real and the gauntlet detects it — the PROVISIONAL §14 thresholds (breadth min_round_trips=30,
# the subperiod gate) simply cannot yet judge a faint low-frequency edge, encoding a hidden
# high-frequency assumption. T-a1 pins as a should-PASS regression ONLY once Phase-6 calibration
# reconciles those thresholds (the precondition at PASS_DEFERRED). It certifies detectability at
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
# is the meta-finding: under provisional §14, no honest strategy clears all eleven. Verdict is
# therefore PASS_DEFERRED (neither PASS — nothing scoped out — nor FAIL — the edge is real),
# pinned only once Phase-6 calibration reconciles ruin_dd/subperiod/min_round_trips.
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
