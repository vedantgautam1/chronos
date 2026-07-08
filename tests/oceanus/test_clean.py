"""Phase 5 tests: the policy does exactly what was decided — no more, no less."""

import pandas as pd
import pytest

from chronos.oceanus.clean import CleaningPolicy, clean
from chronos.oceanus.model import Timeframe
from chronos.oceanus.validate import validate

from .corrupted_fixture import make_corrupted_frame
from .test_store import make_bars


def test_clean_data_passes_through_untouched():
    bars = make_bars(24)
    result = clean(bars)
    assert not result.actions
    pd.testing.assert_frame_equal(result.frame, bars)
    assert "no changes were needed" in result.summary()


def test_input_frame_is_never_modified():
    frame = make_corrupted_frame()
    before = frame.copy(deep=True)
    clean(frame)
    pd.testing.assert_frame_equal(frame, before)


def test_default_policy_drops_garbage_keeps_outliers_and_gaps():
    result = clean(make_corrupted_frame())

    report = validate(result.frame, Timeframe.H1)
    kinds = report.kinds()
    # Fixed by the policy:
    assert "duplicate" not in kinds
    assert "ohlc" not in kinds
    assert "impossible_value" not in kinds
    assert "out_of_order" not in kinds
    # Deliberately NOT fixed (leave/flag, per the founder's policy):
    assert "gap" in kinds  # original gap + honest holes from dropped rows
    assert "outlier" in kinds
    assert "naive_timestamp" in kinds


def test_every_change_is_reported():
    result = clean(make_corrupted_frame())
    text = result.summary()
    assert "sorted by open_time" in text
    assert "duplicate bar" in text
    # Two impossible rows were planted: high<low and negative volume.
    assert sum("impossible bar" in a for a in result.actions) == 2
    # Fixture: 24 hours - 1 deleted (gap) + 1 duplicate = 24 rows in;
    # dropping 1 duplicate + 2 impossible rows = 21 out.
    assert len(result.frame) == 21


def test_drop_outliers_only_when_asked():
    frame = make_bars(10)
    frame.loc[5, "close"] = frame.loc[4, "close"] * 1.5  # +50% jump
    frame.loc[5, "high"] = frame.loc[5, "close"] + 1

    kept = clean(frame)  # default: flag only
    assert len(kept.frame) == 10

    dropped = clean(frame, CleaningPolicy(drop_outliers=True))
    assert len(dropped.frame) < 10
    assert any("outlier" in a for a in dropped.actions)


def test_gap_filling_is_refused():
    with pytest.raises(ValueError, match="fabricates"):
        clean(make_bars(10), CleaningPolicy(fill_gaps=True))


def test_flag_only_policy_changes_nothing():
    conservative = CleaningPolicy(drop_broken_rows=False)
    result = clean(make_corrupted_frame(), conservative)
    # Only the non-destructive sort is allowed to happen.
    assert all("sorted" in a for a in result.actions)
    assert len(result.frame) == len(make_corrupted_frame())
