"""capacity.py — stage 4.6, Capacity (spec §4.6).

Re-run the candidate at `capacity.scale_factors` = [10, 100] × `initial_cash`. The
participation cap (5% of bar volume) either binds as size grows or it does not.

`initial_cash` is a `Decimal` (the ledger's exact accounting unit) — it is scaled in
Decimal (`base × 10`, `base × 100`), never through float.

Gate (at `capacity.gate_scale` = 10):
  - per-bar Sharpe degrades by <= `capacity.max_degradation_frac` (0.3) of the base
    Sharpe, AND
  - remainder-cancelled notional <= `capacity.max_remainder_frac` (0.2) of intended
    notional.
The 100× run is REPORTING-ONLY: visible degradation there is the honest expectation;
a 100× run that does NOT degrade means the cap is not binding at BTC/USDT depth (R6
measured zero liquidity failures at $90k) — informative, not suspicious.

Remainder fraction = cancelled intended notional / total intended notional. A
participation-cap `REMAINDER_CANCELLED` event shares its `order_id` with the fill of
the same bar (hephaestus/broker.py), so its notional is `qty × that fill's execution
price`; total intended = filled notional + cancelled notional. A remainder with no
matching fill (a limit that never traded through — not produced by the market-only
milestone) has no execution price and is excluded, counted honestly as
`unpriced_remainders` rather than silently dropped.

Provisional-threshold note: `max_degradation_frac` / `max_remainder_frac` are weakly
derived §14 numbers (STATE.md "Blocking"); the outcome stamps them provisional.

Kind accounting: 2 × VERIFICATION (never toward N).
"""

from dataclasses import replace
from decimal import Decimal

from chronos.hephaestus.types import BacktestResult, OrderEventKind
from chronos.moirai.context import GauntletContext
from chronos.moirai.rerun import per_bar_sharpe, rerun_candidate
from chronos.moirai.types import TestOutcome

MOIRA_ID = "M4.6-capacity"

_SCALE_FACTORS_KEY = "capacity.scale_factors"
_GATE_SCALE_KEY = "capacity.gate_scale"
_MAX_DEGRADATION_KEY = "capacity.max_degradation_frac"
_MAX_REMAINDER_KEY = "capacity.max_remainder_frac"


def remainder_notional_fraction(trades, order_events) -> tuple[float, dict]:
    """(cancelled intended notional / total intended notional, detail) from a run's
    fills and order events. Decimal throughout (ledger exactness); the returned
    fraction is a float for the gate/evidence. Total 0 (nothing traded) → 0.0."""
    price_by_order = {f.order_id: f.price for f in trades}
    filled_notional = sum((f.qty_filled * f.price for f in trades), Decimal("0"))
    cancelled_notional = Decimal("0")
    unpriced = 0
    for event in order_events:
        if event.kind != OrderEventKind.REMAINDER_CANCELLED:
            continue
        price = price_by_order.get(event.order_id)
        if price is None:
            unpriced += 1
            continue
        cancelled_notional += event.qty * price
    total = filled_notional + cancelled_notional
    frac = float(cancelled_notional / total) if total > 0 else 0.0
    detail = {
        "cancelled_notional": str(cancelled_notional),
        "filled_notional": str(filled_notional),
        "total_intended_notional": str(total),
        "unpriced_remainders": unpriced,
    }
    return frac, detail


class Capacity:
    """Stage 4.6. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        if ctx.candidate is None:
            raise ValueError(
                "stage 4.6 needs ctx.candidate (strategy + base config + hypothesis) "
                "to re-run at scaled capital; none was provided."
            )
        base_config = ctx.candidate.base_config
        base_sr = per_bar_sharpe(result)

        scale_factors = list(ctx.config.thresholds[_SCALE_FACTORS_KEY])
        gate_scale = ctx.config.thresholds[_GATE_SCALE_KEY]
        max_deg = ctx.config.thresholds[_MAX_DEGRADATION_KEY]
        max_rem = ctx.config.thresholds[_MAX_REMAINDER_KEY]

        runs: dict = {}
        wall_clocks: list[float] = []
        for scale in scale_factors:
            scaled_cash = base_config.initial_cash * scale  # Decimal × int → Decimal
            modified = replace(base_config, initial_cash=scaled_cash)
            rr = rerun_candidate(ctx, modified)
            wall_clocks.append(rr.wall_clock_s)
            sr = per_bar_sharpe(rr.result)
            rem_frac, rem_detail = remainder_notional_fraction(
                rr.result.trades, rr.result.order_events)
            runs[str(scale)] = {
                "initial_cash": str(scaled_cash),
                "per_bar_sharpe": sr,
                "remainder_fraction": rem_frac,
                "remainder_detail": rem_detail,
                "config_hash": rr.result.config_hash,
                "data_snapshot_hash": rr.result.data_snapshot_hash,
                "wall_clock_s": rr.wall_clock_s,
            }

        gate = runs[str(gate_scale)]
        gate_sr = gate["per_bar_sharpe"]
        gate_rem = gate["remainder_fraction"]

        # Degradation floor works for either sign of base_sr and reduces to the
        # fractional rule when base_sr > 0: the scaled Sharpe may fall no further than
        # max_deg × |base_sr| below the base.
        allowed_floor = base_sr - max_deg * abs(base_sr)
        deg_ok = gate_sr >= allowed_floor
        rem_ok = gate_rem <= max_rem
        passed = bool(deg_ok and rem_ok)

        deg_frac = ((base_sr - gate_sr) / base_sr) if base_sr != 0.0 else None

        evidence: dict = {
            "base_per_bar_sharpe": base_sr,
            "scale_factors": list(scale_factors),
            "gate_scale": gate_scale,
            "runs": runs,
            "max_degradation_frac": max_deg,
            "max_remainder_frac": max_rem,
            "degradation_fraction": deg_frac,
            "degradation_floor": allowed_floor,
            "degradation_ok": deg_ok,
            "remainder_ok": rem_ok,
            "provisional_thresholds_note": (
                "capacity.max_degradation_frac / max_remainder_frac are weakly-derived "
                "§14 numbers, provisional until Phase 6 calibrates them."),
            "reporting_only_scales": [s for s in scale_factors if s != gate_scale],
            "run_wall_clock_s": wall_clocks,
            "kind_accounting": "2 × VERIFICATION (never toward N)",
        }
        if base_sr <= 0.0:
            evidence["base_nonpositive_note"] = (
                "base per-bar Sharpe is non-positive: the fractional-degradation "
                "criterion is ill-posed, so the gate uses the absolute floor "
                "(base − max_deg×|base|). 4.6 tests capacity/liquidity, not "
                "profitability — 4.3/4.5 gate that.")
        if not passed:
            failed = []
            if not deg_ok:
                failed.append("sharpe_degradation")
            if not rem_ok:
                failed.append("remainder_notional")
            evidence["reason"] = "capacity_gate_fail"
            evidence["capacity_gate_fail_detail"] = failed

        return TestOutcome(moira_id=self.moira_id, passed=passed,
                           score=float(gate_sr), evidence=evidence)
