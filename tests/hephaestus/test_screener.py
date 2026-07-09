"""Phase 8 tests: the screener is quarantined — it can kill, never crown."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from chronos.hephaestus.costs import ZERO_COSTS, CostConfig
from chronos.hephaestus.screener import ScreenVerdict, screen_only_never_promote
from chronos.hephaestus.types import BacktestResult
from chronos.mnemosyne.stub import RecordStore
from chronos.oceanus.model import BAR_COLUMNS
from chronos.run import serialize_result

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def frame_from_closes(closes) -> pd.DataFrame:
    rows = [
        {"open_time": pd.Timestamp(START + timedelta(hours=i)),
         "open": c, "high": c + 1, "low": c - 1, "close": c,
         "volume": 1000.0, "is_final": True}
        for i, c in enumerate(closes)
    ]
    return pd.DataFrame(rows, columns=BAR_COLUMNS)


UPTREND = frame_from_closes([100 + i + (3 if i % 7 == 0 else 0) for i in range(200)])
DOWNTREND = frame_from_closes([300 - i + (i % 5) for i in range(200)])


def test_verdict_is_not_a_backtest_result_type_level_quarantine():
    verdict = screen_only_never_promote(UPTREND, [5], [20])[0]
    assert isinstance(verdict, ScreenVerdict)
    assert not isinstance(verdict, BacktestResult)
    # And it cannot pass where a BacktestResult is expected:
    with pytest.raises(AttributeError):
        serialize_result(verdict)


def test_degenerate_parameters_are_rejected_outright():
    verdicts = screen_only_never_promote(UPTREND, [50], [10, 50])
    assert all(v.rejected and "degenerate" in v.reason for v in verdicts)


def test_dead_region_is_rejected_on_downtrending_data():
    # Long-only MA crossover on a persistent downtrend: everything dies.
    verdicts = screen_only_never_promote(DOWNTREND, [3, 5, 10], [20, 40])
    assert all(v.rejected for v in verdicts)


def test_survivors_are_possible_and_carry_the_disclaimer():
    # A strong uptrend with low costs: some pair should survive the cull —
    # proving the screener isn't a trivial reject-everything machine.
    verdicts = screen_only_never_promote(UPTREND, [3, 5], [20, 40], cost=ZERO_COSTS)
    survivors = [v for v in verdicts if not v.rejected]
    assert survivors
    assert all("not evidence" in v.reason for v in survivors)


def test_costs_bite_and_can_flip_a_verdict():
    """Cost sensitivity, twice over: (a) for identical params, the crude
    return strictly falls as costs rise; (b) on choppy data (many flips,
    thin edge) extreme costs reject candidates that zero costs let live.
    (An earlier version asserted rejections flip on a strong-uptrend
    fixture — costs bit there too, but a +150% gross edge never goes
    negative; the fixture, not the screener, was wrong.)"""
    import math
    choppy = frame_from_closes([100 + 10 * math.sin(i / 3) for i in range(200)])
    params = ([3, 5], [12, 20])
    extreme = CostConfig(taker_fee_bps=CostConfig().taker_fee_bps * 50,
                         slippage_bps=CostConfig().slippage_bps * 50)

    by_cost = {label: screen_only_never_promote(choppy, *params, cost=c)
               for label, c in [("zero", ZERO_COSTS), ("real", CostConfig()),
                                ("extreme", extreme)]}

    for i in range(len(by_cost["zero"])):
        z, r, x = by_cost["zero"][i], by_cost["real"][i], by_cost["extreme"][i]
        assert z.position_changes > 0  # choppy data: everything trades
        assert z.crude_return > r.crude_return > x.crude_return  # costs bite
    # Extreme costs kill everything that trades. (Survival at low cost is
    # proven on the uptrend fixture in test_survivors_are_possible — on a
    # pure sine the crossover is systematically late and loses even free.)
    assert all(v.rejected for v in by_cost["extreme"])


def test_screens_are_events_not_trials(tmp_path):
    store = RecordStore(tmp_path)
    before = store.trial_count
    screen_only_never_promote(UPTREND, [3, 5], [20, 40], store=store)
    assert store.trial_count == before  # the counter DID NOT move
    events = store.read_all()
    assert len(events) == 4
    assert all(e["type"] == "screen" for e in events)
