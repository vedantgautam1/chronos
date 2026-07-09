"""
╔══════════════════════════════════════════════════════════════════════╗
║  UNTRUSTED — this module has NONE of the engine's guarantees.         ║
║                                                                        ║
║  No MarketView bound (it sees the whole series at once), no broker,   ║
║  no participation caps, no exact ledger, no invariant probes. It      ║
║  exists to KILL bad ideas fast. Its verdict can only ever be          ║
║  "rejected" or "needs the real engine" — it can never promote.        ║
║  Nothing it produces is a BacktestResult and nothing it produces      ║
║  counts as evidence a strategy works.                                 ║
╚══════════════════════════════════════════════════════════════════════╝

Phase 8 — vectorized screener (spec §11): whole-series array math for a
fast first cull of MA-crossover parameter ideas. It SHARES the cost
parameters (so its rejections aren't cost-naive) but approximates their
application crudely (flat per-side fraction on every position change).

Screen outcomes are logged as SCREEN EVENTS, not trials: they do not
advance the trial counter. (Recommendation per spec §11 — only full
engine evaluations feed selection. The quant may overrule; recorded in
HANDOFF.md as a pending decision.)
"""

from dataclasses import dataclass
from itertools import product
from typing import Mapping

import numpy as np
import pandas as pd

from chronos.hephaestus.costs import CostConfig
from chronos.mnemosyne.stub import RecordStore


@dataclass(frozen=True)
class ScreenVerdict:
    """Deliberately NOT a BacktestResult and convertible to nothing.

    rejected=True  -> the idea is dead; do not spend engine time on it.
    rejected=False -> the idea MAY deserve a real engine run. That is the
                      strongest thing a screen can ever say.
    """

    fast: int
    slow: int
    rejected: bool
    reason: str
    crude_return: float  # cost-adjusted, approximate, UNTRUSTED
    position_changes: int


def screen_only_never_promote(
    bars: pd.DataFrame,
    fast_windows: list[int],
    slow_windows: list[int],
    cost: CostConfig = CostConfig(),
    store: RecordStore | None = None,
) -> list[ScreenVerdict]:
    """Sweep MA-crossover (fast, slow) pairs over the whole series at once.

    Crude model, biased toward rejection being trustworthy: signals use
    only closes through bar t (positions shift one bar — even the crude
    path avoids blatant same-bar leakage), and every position change pays
    the shared per-side cost fraction. A negative crude return under this
    generous model is a reliable "dead"; a positive one proves nothing.
    """
    closes = bars["close"].astype(float)
    bar_returns = closes.pct_change().fillna(0.0)
    per_side_cost = float(
        (cost.taker_fee_bps + cost.slippage_bps + cost.half_spread_bps) / 10000
    )

    verdicts = []
    for fast, slow in product(fast_windows, slow_windows):
        if fast >= slow:
            verdict = ScreenVerdict(fast, slow, True,
                                    "degenerate: fast window >= slow window", 0.0, 0)
        else:
            fast_ma = closes.rolling(fast).mean()
            slow_ma = closes.rolling(slow).mean()
            # In the market when fast MA is above slow MA; acting one bar
            # AFTER the signal (shift), long-only, all-in/all-out.
            position = (fast_ma > slow_ma).astype(float).shift(1).fillna(0.0)
            flips = position.diff().abs().fillna(0.0)
            net_returns = position * bar_returns - flips * per_side_cost
            crude_return = float((1.0 + net_returns).prod() - 1.0)
            n_changes = int(flips.sum())

            if n_changes == 0:
                verdict = ScreenVerdict(fast, slow, True,
                                        "never trades on this data", crude_return, 0)
            elif crude_return <= 0.0:
                verdict = ScreenVerdict(
                    fast, slow, True,
                    f"crude cost-adjusted return {crude_return:+.2%} <= 0 "
                    "under a generous fill model", crude_return, n_changes)
            else:
                verdict = ScreenVerdict(
                    fast, slow, False,
                    f"crude return {crude_return:+.2%}: MAY deserve a real "
                    "engine run — this is not evidence of anything",
                    crude_return, n_changes)
        verdicts.append(verdict)

        if store is not None:
            # A screen EVENT — never a trial; the counter must not move.
            store.append({
                "type": "screen", "screener": "ma_crossover",
                "fast": fast, "slow": slow, "rejected": verdict.rejected,
                "reason": verdict.reason, "crude_return": verdict.crude_return,
            })
    return verdicts
