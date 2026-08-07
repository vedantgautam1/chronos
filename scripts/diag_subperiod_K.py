"""diag_subperiod_K.py — POINT-IN-TIME DIAGNOSTIC (Phase 5 side-diagnostic, 2026-08-07).

DIAGNOSTIC, NOT gauntlet code: asserts nothing in CI, is NOT imported by moirai/, touches no
frozen artifact (touchstones.py / subperiod.py / v001.json / configs/gauntlet / CI tests all
untouched). It reads the frozen judge and measures it. Kept for reproducibility/provenance of a
scope-changing finding; re-run it after the quant's gate-(ii) recalibration or when the
all-eleven K=7 test is built. Do not mistake it for instrument code.

QUESTION: is 4.8's (subperiod) touchstone failure on the DEFERRED should-PASS canaries a
K=3-window artifact? The canaries run on a 3-year window (K=3 twelve-month sub-windows), but
SPEC §4.8 says the real operating point is "K ≈ 6–7 given ~7.4 research years at the proposed
seal." This script measures whether 4.8's failure survives at the real K.

PINNED RESULTS (2026-08-07; seeds T-a1 {314,315,316,317,318}, T-a2 {271,272,273,274,275}):
  - 4.8 score == gate-(ii) HAC t. At K=3 BOTH canaries PASS gate (ii); the failure is gate (iii)
    window-PnL concentration (+ gate (i) for T-a1) — a low-K resolution artifact, NOT frequency.
  - 4.8 pass-rate  T-a1: K=3 1/5 → K=7 2/5   |   T-a2: K=3 1/5 → K=7 5/5.
  - T-a2 = clean window artifact (resolves at the real K). T-a1 = UNRESOLVED at K=7 (residual is
    a mix of gates (i)/(ii)/(iii)). SCOPE CAVEAT: this isolates 4.8 ONLY — 4.0 and 4.4 at K=7 are
    UNTESTED, so the meta-finding still rests on those. See SESSION_FINDINGS/HANDOFF 2026-08-07.

MEASUREMENT ONLY — changes nothing about the instrument:
  - Does NOT edit touchstones.py / subperiod.py / v001.json / configs/gauntlet / any CI test.
  - Does NOT change any threshold. Seeds are pre-registered below; EVERY seed is reported.
  - Isolated store only (a fresh tmp dir per run; CalibrationHarness refuses the prod path).
  - This file is scratch: not committed unless the founder approves at the checkpoint.

Reads (not writes) the frozen judge. The window-extended canaries in Step 2 use the SAME
a-priori rules already pinned (same within-regime Sharpe, same half-life, same MA timescale
rule, same σ=0.60); the ONLY change is window length (3yr → 7yr). No new seed hunt.

STRUCTURAL NOTE (verified by reading subperiod.py): SubPeriod.evaluate() never references its
`result` argument — it re-runs each sub-window from ctx.candidate.base_config. So 4.8 can be run
in isolation with a stub result. Step 1 validates this isolated runner against the full judge()
harness (score must match the recorded 1.915 / 4.391) before Step 2 trusts it.
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from dateutil.relativedelta import relativedelta

from chronos.moirai.calibration.generator import generate_regime_frame
from chronos.moirai.calibration.harness import CalibrationHarness, _SyntheticExchange
from chronos.moirai.calibration.touchstones import (
    _TA1_MA_PARAMS, _TA2_MA_PARAMS, _SYNTH, _dev_config, FULL_PIPELINE,
    TA1_BULL_SHARPE, TA1_BEAR_SHARPE, TA1_HALF_LIFE_DAYS, TA1_FRAME_SEED, TA1_GAUNTLET_SEED,
    TA2_BULL_SHARPE, TA2_BEAR_SHARPE, TA2_HALF_LIFE_DAYS, TA2_FRAME_SEED, TA2_GAUNTLET_SEED,
    build_t_a1, build_t_a2, judge, TouchstoneSpec,
)
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.stages import SubPeriod
from chronos.oceanus.access import get_bars
from chronos.oceanus.model import Timeframe
from chronos.run import Hypothesis, RunConfig, RunKind
from chronos.strategies.ma_crossover import MACrossover

UTC = timezone.utc
_BASE_START = datetime(2020, 1, 1, tzinfo=UTC)  # same anchor build_t_a1/a2 use
_MARGIN = timedelta(weeks=3)                     # same ±3wk margin the pinned builds keep (4.7)

# Pre-registered seed sets (fixed a priori; report ALL). First of each is the pinned canary seed.
TA1_SEEDS = [314, 315, 316, 317, 318]
TA2_SEEDS = [271, 272, 273, 274, 275]

_CANARY = {
    "T-a1": dict(bull=TA1_BULL_SHARPE, bear=TA1_BEAR_SHARPE, half_life=TA1_HALF_LIFE_DAYS,
                 ma=_TA1_MA_PARAMS, gseed=TA1_GAUNTLET_SEED, seeds=TA1_SEEDS),
    "T-a2": dict(bull=TA2_BULL_SHARPE, bear=TA2_BEAR_SHARPE, half_life=TA2_HALF_LIFE_DAYS,
                 ma=_TA2_MA_PARAMS, gseed=TA2_GAUNTLET_SEED, seeds=TA2_SEEDS),
}


def _tmp_store() -> Path:
    return Path(tempfile.mkdtemp(prefix="diag_subperiod_"))


def build_spec(canary: str, *, frame_seed: int, base_years: int) -> TouchstoneSpec:
    """A window-parametrized canary built from the SAME pinned a-priori rules — only the base
    window length varies. base_years=3 with the canonical seed reproduces the pinned build."""
    c = _CANARY[canary]
    base_start = _BASE_START
    base_end = base_start + relativedelta(years=base_years)
    frame_start = base_start - _MARGIN
    frame_end = base_end + _MARGIN
    n_bars = int((frame_end - frame_start) / Timeframe.H1.duration)
    frame = generate_regime_frame(
        bull_sharpe=c["bull"], bear_sharpe=c["bear"], half_life_days=c["half_life"],
        n_bars=n_bars, seed=frame_seed, start=frame_start)
    base_config = RunConfig(symbol=_SYNTH, timeframe=Timeframe.H1, start=base_start,
                            end=base_end, strategy_params=dict(c["ma"]))
    hyp = Hypothesis(id=f"{canary}-diag-K-seed{frame_seed}-y{base_years}",
                     statement=f"{canary} diagnostic ({base_years}yr window, seed {frame_seed}).",
                     prediction="subperiod-stability diagnostic; not a verdict.")
    return TouchstoneSpec(name=f"{canary}/s{frame_seed}/y{base_years}", frame=frame,
                          frame_start=frame_start, frame_end=frame_end, base_config=base_config,
                          strategy=MACrossover(symbol=_SYNTH), hypothesis=hyp,
                          gauntlet_seed=c["gseed"])


def run_48_isolated(spec: TouchstoneSpec):
    """Run stage 4.8 ONLY, mirroring judge()'s plumbing (synthetic exchange → isolated data
    root → wrapped ctx.run for the VERIFICATION re-runs). No other stages, no 4.9 nulls. Passes
    a stub `result=None` — SubPeriod.evaluate ignores it (verified in subperiod.py)."""
    store_path = _tmp_store()
    harness = CalibrationHarness(store_path)      # refuses the production root
    store = harness.store
    data_root = store_path / "synthdata"
    tf = spec.base_config.timeframe
    synth = _SyntheticExchange(spec.frame, tf)
    get_bars(spec.base_config.symbol, tf, spec.frame_start, spec.frame_end,
             root=data_root, exchange=synth)

    dev = _dev_config(FULL_PIPELINE, full_eval=True)  # 4.8 reads subperiod.* only
    candidate = Candidate(strategy=spec.strategy, base_config=spec.base_config,
                          hypothesis=spec.hypothesis)
    ctx = context_for_config(store, dev, gauntlet_seed=spec.gauntlet_seed, candidate=candidate)
    original_run = ctx.run

    def wrapped(**kw):
        return original_run(data_root=data_root, exchange=synth, **kw)

    ctx.run = wrapped  # type: ignore[method-assign]
    return SubPeriod().evaluate(None, ctx)


def _m48(verdict):
    for o in verdict.outcomes:
        if o.moira_id == "M4.8-subperiod":
            return o
    raise LookupError("no M4.8-subperiod outcome in verdict")


def _row(canary, seed, k_label, ev, passed, score):
    gi = ev.get("gate_i_positive_sharpe")
    gii = ev.get("gate_ii_hac_t")
    giii = ev.get("gate_iii_concentration")
    pos_frac = ev.get("positive_sharpe_frac")
    hac_t = ev.get("hac_t")
    max_share = ev.get("max_window_pnl_share")
    k = ev.get("n_windows")
    fails = ev.get("subperiod_fail_detail", [])
    return (f"{canary:5} | {seed:4} | K={k} ({k_label:4}) | "
            f"(i) {str(gi):5} pos={pos_frac if pos_frac is None else round(pos_frac,3)!s:5} | "
            f"(ii) {str(gii):5} t={hac_t if hac_t is None else round(hac_t,3)!s:6} | "
            f"(iii) {str(giii):5} share={max_share if max_share is None else round(max_share,3)!s:6} | "
            f"4.8 {'PASS' if passed else 'FAIL':4} | fail={','.join(fails) or '-'}")


# =====================================================================================
def step1():
    print("=" * 100)
    print("STEP 1 — reproduce the pinned K=3 evidence (full judge, full_eval) + verify isolation")
    print("=" * 100)
    recorded = {"T-a1": 1.915, "T-a2": 4.391}
    builders = {"T-a1": build_t_a1, "T-a2": build_t_a2}
    for canary, builder in builders.items():
        spec = builder()
        verdict, _ = judge(spec, store_path=_tmp_store(), full_eval=True)
        o = _m48(verdict)
        ev = o.evidence
        print(f"\n--- {canary}: M4.8 via full judge() ---")
        print(f"  score (== hac_t, floored 0)      : {o.score:.4f}   (recorded {recorded[canary]})")
        print(f"  K (n_windows)                    : {ev['n_windows']}")
        print(f"  gate (i)  positive-Sharpe        : pass={ev['gate_i_positive_sharpe']}  "
              f"frac={ev['positive_sharpe_frac']:.3f}  ({ev['positive_sharpe_windows']}/{ev['n_windows']})")
        print(f"  gate (ii) HAC t                  : pass={ev['gate_ii_hac_t']}  "
              f"hac_t={ev['hac_t']}  m={ev['nw_lag_m']}  bracket={ev['hac_t_bracket']}  "
              f"threshold={ev['hac_t_threshold']}")
        print(f"  gate (iii) max window PnL share  : pass={ev['gate_iii_concentration']}  "
              f"max_share={ev['max_window_pnl_share']}  total_pnl={ev['total_net_pnl']:.2f}")
        print(f"  passed / fail detail             : {o.passed}  {ev.get('subperiod_fail_detail')}")

        match = abs(o.score - recorded[canary]) < 0.01
        print(f"  SELF-CONSISTENCY vs recorded     : {'MATCH' if match else '*** MISMATCH ***'}")
        if not match:
            raise SystemExit(f"STOP: {canary} 4.8 score {o.score} != recorded {recorded[canary]} "
                             "— reproduction drifted; nothing downstream is trustworthy.")

        iso = run_48_isolated(spec)
        iso_match = abs(iso.score - o.score) < 1e-9 and iso.passed == o.passed \
            and iso.evidence.get("subperiod_fail_detail") == ev.get("subperiod_fail_detail")
        print(f"  ISOLATED runner vs full judge    : {'MATCH' if iso_match else '*** MISMATCH ***'}"
              f"  (isolated score {iso.score:.4f})")
        if not iso_match:
            raise SystemExit(f"STOP: isolated 4.8 for {canary} does not match the full judge — "
                             "the isolated runner is not faithful; Step 2 cannot use it.")


def step2():
    print("\n" + "=" * 100)
    print("STEP 2 — 4.8 at K=3 (3yr) vs K=7 (7yr), pre-registered seeds, every cell reported")
    print("=" * 100)
    header = ("canary| seed | K            | gate (i)            | gate (ii)          | "
              "gate (iii)             | 4.8  | failed")
    rows = []
    summary = {}
    for canary in ("T-a1", "T-a2"):
        for k_label, years in (("3yr", 3), ("7yr", 7)):
            passes = 0
            for seed in _CANARY[canary]["seeds"]:
                spec = build_spec(canary, frame_seed=seed, base_years=years)
                o = run_48_isolated(spec)
                rows.append(_row(canary, seed, k_label, o.evidence, o.passed, o.score))
                passes += int(o.passed)
            summary[(canary, k_label)] = (passes, len(_CANARY[canary]["seeds"]))

    print("\n" + header)
    print("-" * len(header))
    for r in rows:
        print(r)

    print("\n--- 4.8 pass-rate: K=3 vs K=7 ---")
    for canary in ("T-a1", "T-a2"):
        p3, n3 = summary[(canary, "3yr")]
        p7, n7 = summary[(canary, "7yr")]
        print(f"  {canary}:  K=3  {p3}/{n3} pass   |   K=7  {p7}/{n7} pass")


def prefix_check():
    print("\n" + "=" * 100)
    print("PREFIX CHECK (canonical seed, non-gating) — is the K=7 frame a strict extension of K=3?")
    print("=" * 100)
    for canary, seed in (("T-a1", TA1_FRAME_SEED), ("T-a2", TA2_FRAME_SEED)):
        f3 = build_spec(canary, frame_seed=seed, base_years=3).frame
        f7 = build_spec(canary, frame_seed=seed, base_years=7).frame
        n3 = len(f3)
        c3 = f3["close"].to_numpy()[:n3]
        c7 = f7["close"].to_numpy()[:n3]
        identical = np.allclose(c3, c7)
        print(f"  {canary} (seed {seed}): first {n3} closes identical in K=7 frame? {identical} "
              f"— {'strict extension' if identical else 'per-length reseed (draw-count shifts rng state)'}")


if __name__ == "__main__":
    step1()
    step2()
    prefix_check()
