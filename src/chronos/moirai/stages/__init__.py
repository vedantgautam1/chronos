"""stages/ — the Moirai test roster (spec §4).

The free stages (zero engine runs) landed in Phase 4a: 4.0 eligibility, 4.3 deflated
Sharpe, 4.4 trade-shuffle. Phase 4b adds the first re-run stages: 4.1 signal-only
null gate (a capture pass) and 4.2 parameter plateau (0–K SEARCH neighbor runs; the
only stage that finalizes N). Each reads the BacktestResult and/or the store,
computes, compares to a config threshold, and returns a TestOutcome. The remaining
re-run stages (4.5–4.10) arrive in later phases.

Every gate threshold is read from `ctx.config.thresholds` (I9); no numeric gate
literal appears in this package (probe G2 greps for exactly that).
"""

from chronos.moirai.stages.eligibility import Eligibility
from chronos.moirai.stages.signal_null import SignalNull
from chronos.moirai.stages.plateau import Plateau
from chronos.moirai.stages.deflated_sharpe import DeflatedSharpe
from chronos.moirai.stages.trade_shuffle import TradeShuffle

__all__ = ["Eligibility", "SignalNull", "Plateau", "DeflatedSharpe", "TradeShuffle"]
