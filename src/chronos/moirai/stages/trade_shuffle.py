"""trade_shuffle.py — stage 4.4, Trade-shuffle Monte Carlo (spec §4.4, A-MC-1).

Was the *path shape* luck? Take the candidate's closed round trips as per-trade
return factors, reshuffle their order `mc_shuffle.n_shuffles` times (drawing ONLY
from `ctx.rng` — I10, no global RNG), rebuild equity under proportional
reinvestment, and read off the max-drawdown distribution.

Two outputs:
  (i)  risk band — the (1 - luck_pct) percentile shuffled maxDD is THE drawdown
       expectation; gate: p95 maxDD <= thresholds["mc_shuffle.ruin_dd"].
  (ii) sequence-luck flag — realized maxDD below the luck_pct percentile of the
       shuffle distribution -> `sequence_luck_warning` (warn-only).

Two honest limitations stamped verbatim (in substance) into the record:
  - Terminal equity is ORDER-INVARIANT under proportional reinvestment (the product
    of per-trade factors commutes), so this test contains ZERO information about
    returns — it is a path-risk diagnostic only.
  - The reconstruction assumes proportional sizing, whereas the ledger sizes by
    strategy logic — a diagnostic approximation, not accounting-grade.

Register A-MC-1 (§16 Assumptions): no primary source for trade-shuffle bands;
evidence carries the FULL percentile table so a future sourced method can back-check.

The gate threshold `mc_shuffle.ruin_dd` is provisional — a placeholder for Themis's
future risk limits and the weakest-derived threshold in the spec (§14). The record
says so; this gate carries little information until Phase 6 calibration.
"""

import numpy as np

from chronos.hephaestus.types import BacktestResult
from chronos.moirai.context import GauntletContext
from chronos.moirai.round_trips import reconstruct_round_trips
from chronos.moirai.types import TestOutcome

MOIRA_ID = "M4.4-shuffle"

_N_SHUFFLES_KEY = "mc_shuffle.n_shuffles"
_RUIN_DD_KEY = "mc_shuffle.ruin_dd"
# NOTE: spec §4.4 names this `mc_shuffle.luck_pct`, but the frozen v001.json
# artifact (Phase 2) ships it as `mc_shuffle.luck_threshold`. v001 is hashed and
# must not be re-keyed here (that would change the judge's hash), so the code binds
# to the artifact's actual key. Flagged in the Phase 4a handoff.
_LUCK_PCT_KEY = "mc_shuffle.luck_threshold"

# Percentile table reported in evidence (the full A-MC-1 distribution).
_REPORT_PERCENTILES = (5, 25, 50, 75, 90, 95, 99)


def max_drawdown(equity: np.ndarray) -> float:
    """Largest peak-to-trough fractional decline of an equity path, in [0, 1]."""
    running_peak = np.maximum.accumulate(equity)
    drawdowns = 1.0 - equity / running_peak
    return float(drawdowns.max()) if len(drawdowns) else 0.0


def equity_path(factors: np.ndarray) -> np.ndarray:
    """Proportional-reinvestment equity from unit start: cumulative product."""
    return np.cumprod(np.concatenate([[1.0], factors]))


class TradeShuffle:
    """Stage 4.4. moira_id matches configs/gauntlet/v001.json pipeline_order."""

    moira_id = MOIRA_ID

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome:
        round_trips = reconstruct_round_trips(result.trades)
        factors = np.array([rt.factor for rt in round_trips], dtype=float)

        limitations = {
            "terminal_equity_order_invariant": (
                "terminal equity is order-invariant under proportional "
                "reinvestment; this test contains zero information about returns "
                "— path-risk diagnostic only"),
            "proportional_sizing_assumption": (
                "reconstruction assumes proportional sizing; the ledger sizes by "
                "strategy logic — diagnostic approximation, not accounting-grade"),
        }
        ruin_dd = ctx.config.thresholds[_RUIN_DD_KEY]
        luck_pct = ctx.config.thresholds[_LUCK_PCT_KEY]

        if len(factors) < 2:
            # Nothing to shuffle — cannot form a distribution. Warn, don't gate.
            return TestOutcome(
                moira_id=self.moira_id, passed=True, score=0.0,
                evidence={
                    "n_round_trips": int(len(factors)),
                    "insufficient_trades_to_shuffle": True,
                    "limitations": limitations,
                    "ruin_dd_threshold": ruin_dd,
                    "ruin_dd_threshold_note": (
                        "provisional Themis placeholder — weakest-derived "
                        "threshold (§14); little information until Phase 6"),
                })

        n_shuffles = ctx.config.thresholds[_N_SHUFFLES_KEY]
        realized_dd = max_drawdown(equity_path(factors))

        shuffled_dds = np.empty(n_shuffles, dtype=float)
        for i in range(n_shuffles):
            order = ctx.rng.permutation(len(factors))
            shuffled_dds[i] = max_drawdown(equity_path(factors[order]))

        risk_pct = 100.0 * (1.0 - luck_pct)  # e.g. 95 when luck_pct = 0.05
        luck_percentile = 100.0 * luck_pct   # e.g. 5
        p_risk_dd = float(np.percentile(shuffled_dds, risk_pct))
        p_luck_dd = float(np.percentile(shuffled_dds, luck_percentile))

        passed = bool(p_risk_dd <= ruin_dd)
        sequence_luck = bool(realized_dd < p_luck_dd)

        terminal_equity = float(equity_path(factors)[-1])
        evidence = {
            "n_round_trips": int(len(factors)),
            "realized_max_drawdown": realized_dd,
            "risk_band_drawdown": p_risk_dd,        # THE drawdown expectation
            "risk_band_percentile": risk_pct,
            "ruin_dd_threshold": ruin_dd,
            "ruin_dd_threshold_note": (
                "provisional Themis placeholder — weakest-derived threshold "
                "(§14); little information until Phase 6 calibration"),
            "sequence_luck_warning": sequence_luck,
            "luck_percentile": luck_percentile,
            "terminal_equity": terminal_equity,
            "n_shuffles": n_shuffles,
            "percentile_table": {
                str(p): float(np.percentile(shuffled_dds, p))
                for p in _REPORT_PERCENTILES
            },
            "limitations": limitations,
            "register": "A-MC-1 (§16 Assumptions) — no primary source; drawdown "
                        "gate only; full percentile table retained for back-check",
        }
        return TestOutcome(moira_id=self.moira_id, passed=passed,
                           score=p_risk_dd, evidence=evidence)
