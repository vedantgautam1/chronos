"""cost_stress.py — stage 4.5, Cost stress at absolute slippage levels (spec §4.5,
D-05, M-d; trap #6).

Re-run the candidate (same params, same window) at ABSOLUTE slippage levels
`cost_stress.levels_bps` = [5, 10, 25] bps, with the modeled half-spread scaled in
proportion to the slippage level and the taker fee HELD at the published schedule.
Three full `kind=VERIFICATION` re-runs through the shared `rerun_candidate` helper.

**Never a rescale of line items.** `cost_summary` exists and will tempt a linear
extrapolation; it is IGNORED for stressing. Costs are path-dependent — the engine's
own scar is the −8.6% linear prediction vs the −9.08% actual re-run (trap #6). Each
level is a genuine engine re-run at that absolute `CostConfig`.

Spread-scaling rule (stamped verbatim into evidence, per §4.5's "spread scaled in
proportion"): at slippage level L, `half_spread_bps = base_half_spread_bps ×
(L / base_slippage_bps)`, `slippage_bps = L`, `taker_fee_bps` = base (held). With the
milestone's measured base (slippage 1 bps, half-spread 1 bps) the factor is L, so the
half-spread equals the slippage at each level.

Gate (at `cost_stress.gate_level_bps` = 10):
  - net return strictly positive AND per-bar Sharpe strictly positive; and
  - **margin criterion** (active whenever the judged result still carries the
    `provisional_cost_constants` warning — always, at Stage 0; re-checked directly on
    `result.warnings`, no cross-stage state): the 10 bps per-bar Sharpe must be
    >= `cost_stress.margin_per_bar_sharpe` (0.005/bar), not merely > 0.
  - the 5 bps run (dominated) must ALSO pass the same criterion; a 5-bps failure while
    10 bps passes is a non-monotone cost response → FAIL `non_monotone_cost_response`.
  - 25 bps is REPORTING-ONLY.

v001-vs-spec key drift (v002 reconciliation, recorded): spec `cost_stress.gate_level`
→ v001 `cost_stress.gate_level_bps`; spec `cost_stress.margin_sharpe` → v001
`cost_stress.margin_per_bar_sharpe`. v001 is the frozen hashed judge; the stage binds
to v001's actual names.

Kind accounting: 3 × VERIFICATION (never toward N).
"""

from dataclasses import replace
from decimal import Decimal

from chronos.hephaestus.types import BacktestResult
from chronos.moirai.context import GauntletContext
from chronos.moirai.rerun import net_return, per_bar_sharpe, rerun_candidate
from chronos.moirai.types import TestOutcome

MOIRA_ID = "M4.5-cost-stress"

_LEVELS_KEY = "cost_stress.levels_bps"
_GATE_LEVEL_KEY = "cost_stress.gate_level_bps"      # spec: cost_stress.gate_level (v002)
_MARGIN_KEY = "cost_stress.margin_per_bar_sharpe"   # spec: cost_stress.margin_sharpe (v002)

# The engine's own marker that spread/slippage are configured guesses, not measured
# from real fills (hephaestus/costs.py PROVISIONAL_WARNING). Its presence in the
# judged result's warnings turns on the stricter margin criterion (§4.0(c), §4.5).
_PROVISIONAL_MARK = "provisional_cost_constants"


def _stressed_config(base_config, level_bps: int, base_slippage_bps: Decimal):
    """A copy of `base_config` at absolute slippage `level_bps`, half-spread scaled in
    proportion, taker fee held. Returns (config, scaling_note)."""
    level = Decimal(str(level_bps))
    base_half = base_config.cost.half_spread_bps
    if base_slippage_bps > 0:
        factor = level / base_slippage_bps
        stressed_half = base_half * factor
        note = (f"half_spread_bps = {base_half} × (L={level} / base_slippage="
                f"{base_slippage_bps}) = {stressed_half}")
    else:
        # A zero measured-slippage base has no proportion to scale off; hold the
        # half-spread and record it. (Never hit by the milestone; kept honest.)
        stressed_half = base_half
        note = (f"base_slippage_bps == 0: no proportion to scale; half_spread held at "
                f"{base_half}")
    stressed_cost = replace(base_config.cost, slippage_bps=level,
                            half_spread_bps=stressed_half)
    return replace(base_config, cost=stressed_cost), note


def _gate_ok(net: float, sr: float, sr_floor: float) -> bool:
    """The 10-bps gate criterion, reused for the dominated 5-bps run: net return
    strictly positive AND per-bar Sharpe at least the (margin-or-zero) floor."""
    return bool(net > 0.0 and sr >= sr_floor)


class CostStress:
    """Stage 4.5. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        if ctx.candidate is None:
            raise ValueError(
                "stage 4.5 needs ctx.candidate (strategy + base config + hypothesis) "
                "to re-run at stressed costs; none was provided."
            )
        base_config = ctx.candidate.base_config
        base_slippage = base_config.cost.slippage_bps

        levels = list(ctx.config.thresholds[_LEVELS_KEY])
        gate_level = ctx.config.thresholds[_GATE_LEVEL_KEY]
        margin = ctx.config.thresholds[_MARGIN_KEY]
        margin_active = any(_PROVISIONAL_MARK in w for w in result.warnings)
        sr_floor = margin if margin_active else 0.0

        # The base point is the judged result itself (measured-cost run) — not a
        # re-run. Curve carries {base, then each stressed level}.
        curve: dict = {
            "base": {
                "slippage_bps": str(base_slippage),
                "half_spread_bps": str(base_config.cost.half_spread_bps),
                "taker_fee_bps": str(base_config.cost.taker_fee_bps),
                "net_return": net_return(result),
                "per_bar_sharpe": per_bar_sharpe(result),
                "config_hash": result.config_hash,
                "data_snapshot_hash": result.data_snapshot_hash,
            }
        }
        wall_clocks: list[float] = []
        scaling_note = ""
        for level in levels:
            stressed, scaling_note = _stressed_config(base_config, level, base_slippage)
            rr = rerun_candidate(ctx, stressed)
            wall_clocks.append(rr.wall_clock_s)
            curve[str(level)] = {
                "slippage_bps": str(stressed.cost.slippage_bps),
                "half_spread_bps": str(stressed.cost.half_spread_bps),
                "taker_fee_bps": str(stressed.cost.taker_fee_bps),
                "net_return": net_return(rr.result),
                "per_bar_sharpe": per_bar_sharpe(rr.result),
                "config_hash": rr.result.config_hash,
                "data_snapshot_hash": rr.result.data_snapshot_hash,
                "wall_clock_s": rr.wall_clock_s,
            }

        gate = curve[str(gate_level)]
        dominated = [level for level in levels if level < gate_level]
        gate_pass = _gate_ok(gate["net_return"], gate["per_bar_sharpe"], sr_floor)
        dominated_pass = all(
            _gate_ok(curve[str(level)]["net_return"],
                     curve[str(level)]["per_bar_sharpe"], sr_floor)
            for level in dominated
        )

        # Net return should be monotone non-increasing as cost rises (base → high).
        ordered_nets = [curve["base"]["net_return"]] + [
            curve[str(level)]["net_return"] for level in sorted(levels)
        ]
        monotone = all(a >= b for a, b in zip(ordered_nets, ordered_nets[1:]))

        evidence: dict = {
            "cost_curve": curve,
            "gate_level_bps": gate_level,
            "levels_bps": list(levels),
            "spread_scaling_rule": scaling_note,
            "taker_fee_held_note": (
                "taker fee held at the published schedule (base taker_fee_bps); only "
                "slippage and the modeled spread are stressed (fees are known; "
                "slippage/spread are the R6 uncertainty, §4.5)."),
            "no_line_item_rescale_note": (
                "each level is a full engine re-run; cost_summary is never scaled "
                "(costs are path-dependent — trap #6, the −8.6% vs −9.08% scar)."),
            "margin_active": margin_active,
            "margin_per_bar_sharpe": margin,
            "sharpe_floor_applied": sr_floor,
            "net_return_monotone_non_increasing": monotone,
            "run_wall_clock_s": wall_clocks,
            "kind_accounting": "3 × VERIFICATION (never toward N)",
        }

        if not gate_pass:
            evidence["reason"] = "cost_gate_fail"
            evidence["cost_gate_fail_note"] = (
                f"at {gate_level} bps: net_return={gate['net_return']:.6f}, "
                f"per_bar_sharpe={gate['per_bar_sharpe']:.6f}; required net>0 and "
                f"per-bar Sharpe >= {sr_floor} "
                f"({'margin' if margin_active else 'zero'} floor).")
            return TestOutcome(moira_id=self.moira_id, passed=False,
                               score=float(gate["per_bar_sharpe"]), evidence=evidence)

        if not dominated_pass:
            evidence["reason"] = "non_monotone_cost_response"
            evidence["non_monotone_note"] = (
                f"the {gate_level} bps gate passed but a dominated (cheaper) level "
                f"{dominated} did not — a non-monotone cost response is itself a red "
                f"flag (§4.5).")
            return TestOutcome(moira_id=self.moira_id, passed=False,
                               score=float(gate["per_bar_sharpe"]), evidence=evidence)

        return TestOutcome(moira_id=self.moira_id, passed=True,
                           score=float(gate["per_bar_sharpe"]), evidence=evidence)
