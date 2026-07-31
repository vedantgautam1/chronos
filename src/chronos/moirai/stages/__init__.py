"""stages/ — the Moirai test roster (spec §4).

The free stages (zero engine runs) land in Phase 4a: 4.0 eligibility, 4.3 deflated
Sharpe, 4.4 trade-shuffle. Each reads the BacktestResult and/or the store, computes,
compares to a config threshold, and returns a TestOutcome. Re-run stages (4.1, 4.2,
4.5–4.10) arrive in later phases.

Every gate threshold is read from `ctx.config.thresholds` (I9); no numeric gate
literal appears in this package (probe G2 greps for exactly that).
"""

from chronos.moirai.stages.eligibility import Eligibility
from chronos.moirai.stages.deflated_sharpe import DeflatedSharpe
from chronos.moirai.stages.trade_shuffle import TradeShuffle

__all__ = ["Eligibility", "DeflatedSharpe", "TradeShuffle"]
