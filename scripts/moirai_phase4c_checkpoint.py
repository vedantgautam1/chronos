"""Phase 4c checkpoint — the milestone through stages 4.0–4.7 (real output).

Builds a dev GauntletConfig from the frozen v001 thresholds (v001.json UNTOUCHED),
with pipeline_order = the stages built so far (4.0–4.7) and full_evaluation_mode=True
(REQUIRED: the milestone FAILS 4.1 at p=0.1045 > α and would otherwise short-circuit
before 4.5/4.6/4.7 ever run). Judges the milestone MA(20/50) crossover candidate and
prints the cost-stress curve, capacity degradation + remainder fraction, shifted-
window Sharpes, and the median per-run wall-clock.

Uses a temp record store so the real records/ log is not polluted by the checkpoint.

Run:  uv run python scripts/moirai_phase4c_checkpoint.py
"""

import statistics as pystats
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.config import load_config
from chronos.moirai.context import Candidate, context_for_config
from chronos.moirai.pipeline import run_gauntlet
from chronos.moirai.stages import (
    Capacity,
    CostStress,
    DeflatedSharpe,
    Eligibility,
    Plateau,
    ShiftedWindow,
    SignalNull,
    TradeShuffle,
)
from chronos.run import RunKind, run_experiment
from scripts.run_milestone import CONFIG, HYPOTHESIS
from chronos.strategies.ma_crossover import MACrossover

PIPELINE_4C = (
    "M4.0-eligibility", "M4.1-signal-null", "M4.2-plateau", "M4.3-dsr",
    "M4.4-shuffle", "M4.5-cost-stress", "M4.6-capacity", "M4.7-shift",
)
REGISTRY = {
    "M4.0-eligibility": Eligibility(), "M4.1-signal-null": SignalNull(),
    "M4.2-plateau": Plateau(), "M4.3-dsr": DeflatedSharpe(),
    "M4.4-shuffle": TradeShuffle(), "M4.5-cost-stress": CostStress(),
    "M4.6-capacity": Capacity(), "M4.7-shift": ShiftedWindow(),
}


def _outcome(verdict, moira_id):
    return next(o for o in verdict.outcomes if o.moira_id == moira_id)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="moirai-4c-"))
    store = RecordStore(tmp / "records")

    v001 = load_config(REPO / "configs" / "gauntlet" / "v001.json")  # untouched on disk
    dev_config = replace(v001, pipeline_order=PIPELINE_4C, full_evaluation_mode=True)

    candidate = Candidate(strategy=MACrossover(), base_config=CONFIG, hypothesis=HYPOTHESIS)
    ctx = context_for_config(store, dev_config, gauntlet_seed=20260803, candidate=candidate)

    print("=" * 74)
    print("PHASE 4c CHECKPOINT — MA(20/50) BTC/USDT 1h, H1 2026 dev window")
    print("full_evaluation_mode=True; v001 thresholds; pipeline 4.0–4.7")
    print("=" * 74)

    # The verdict-grade base run (measured costs), then judge it.
    base = run_experiment(MACrossover(), CONFIG, HYPOTHESIS,
                          kind=RunKind.VERIFICATION, store=store).result
    verdict = run_gauntlet(base, REGISTRY, ctx)

    print(f"\nverdict status: {verdict.status}   authority: {verdict.authority}")
    print(f"cause_of_death: {verdict.cause_of_death}")

    # --- 4.5 cost stress ---
    ev = _outcome(verdict, "M4.5-cost-stress").evidence
    print("\n--- 4.5 COST STRESS (net return / per-bar Sharpe) ---")
    print(f"  spread scaling: {ev['spread_scaling_rule']}")
    print(f"  margin active: {ev['margin_active']}  floor: {ev['sharpe_floor_applied']}")
    for key in ("base", "5", "10", "25"):
        c = ev["cost_curve"][key]
        tag = "  (gate)" if key == "10" else ("  (reporting)" if key == "25" else "")
        print(f"  {key:>4} bps: net {c['net_return']:+.4%}  "
              f"per-bar Sharpe {c['per_bar_sharpe']:+.5f}{tag}")
    print(f"  passed: {_outcome(verdict, 'M4.5-cost-stress').passed}  "
          f"reason: {ev.get('reason')}")

    # --- 4.6 capacity ---
    ev6 = _outcome(verdict, "M4.6-capacity").evidence
    print("\n--- 4.6 CAPACITY (Sharpe degradation + remainder fraction) ---")
    print(f"  base per-bar Sharpe: {ev6['base_per_bar_sharpe']:+.5f}")
    for scale in ("10", "100"):
        r = ev6["runs"][scale]
        tag = "  (gate)" if scale == "10" else "  (reporting)"
        print(f"  {scale:>3}×: per-bar Sharpe {r['per_bar_sharpe']:+.5f}  "
              f"remainder frac {r['remainder_fraction']:.4f}{tag}")
    print(f"  degradation_frac: {ev6['degradation_fraction']}  "
          f"passed: {_outcome(verdict, 'M4.6-capacity').passed}")

    # --- 4.7 shifted window ---
    ev7 = _outcome(verdict, "M4.7-shift").evidence
    print("\n--- 4.7 SHIFTED WINDOW (per-bar Sharpe per offset) ---")
    print(f"  base per-bar Sharpe: {ev7['base_per_bar_sharpe']:+.5f}")
    for o in ev7["per_offset"]:
        if o["refused"]:
            print(f"  {o['offset_weeks']:+d}w: REFUSED ({o['reason']})")
        else:
            print(f"  {o['offset_weeks']:+d}w: per-bar Sharpe {o['per_bar_sharpe']:+.5f}  "
                  f"dev {o['deviation_frac']:.3f}  within_band={o['within_band']}")
    print(f"  evaluated {ev7['n_evaluated']}/{ev7['n_offsets']}, "
          f"refused {ev7['n_refused']}; passed: {_outcome(verdict, 'M4.7-shift').passed}")

    # --- throughput ---
    per_run = (ev["run_wall_clock_s"] + ev6["run_wall_clock_s"] + ev7["run_wall_clock_s"])
    print("\n--- THROUGHPUT (per-engine-run wall-clock, shared helper) ---")
    print(f"  {len(per_run)} re-runs via rerun_candidate")
    print(f"  per-run seconds: {[round(x, 3) for x in per_run]}")
    if per_run:
        print(f"  median: {pystats.median(per_run):.3f}s   "
              f"min {min(per_run):.3f}s  max {max(per_run):.3f}s")
    print("\n(temp store: %s)" % (tmp / "records"))


if __name__ == "__main__":
    main()
