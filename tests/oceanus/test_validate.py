"""Phase 4 tests: validate() catches every planted problem and fixes nothing."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from chronos.oceanus.model import BAR_COLUMNS, Timeframe
from chronos.oceanus.validate import validate

from .corrupted_fixture import PLANTED, make_corrupted_frame
from .test_store import make_bars


def test_clean_data_gets_a_clean_report():
    report = validate(make_bars(48), Timeframe.H1)
    assert report.ok
    assert report.n_bars == 48
    assert "no problems found" in report.summary()


def test_every_planted_problem_is_caught():
    report = validate(make_corrupted_frame(), Timeframe.H1)
    assert not report.ok
    for kind, description in PLANTED.items():
        assert kind in report.kinds(), f"validate() missed the planted {kind} ({description})"


def test_validate_does_not_modify_its_input():
    frame = make_corrupted_frame()
    before = frame.copy(deep=True)
    validate(frame, Timeframe.H1)
    pd.testing.assert_frame_equal(frame, before)


def test_gap_reports_how_many_bars_are_missing():
    bars = make_bars(24)
    with_gap = pd.concat([bars.iloc[:6], bars.iloc[9:]])  # hours 6,7,8 removed
    report = validate(with_gap, Timeframe.H1)
    gap_messages = [i.message for i in report.issues if i.kind == "gap"]
    assert len(gap_messages) == 1
    assert "3 bar(s) missing" in gap_messages[0]


def test_outlier_threshold_is_respected():
    bars = make_bars(10, base_price=100.0)
    bars.loc[5, "close"] = bars.loc[4, "close"] * 1.10  # +10% move
    bars.loc[5, "high"] = bars.loc[5, "close"] + 1

    default = validate(bars, Timeframe.H1)  # threshold 25%
    assert "outlier" not in default.kinds()

    strict = validate(bars, Timeframe.H1, outlier_threshold=0.05)  # 5%
    assert "outlier" in strict.kinds()


def test_report_reads_like_english():
    report = validate(make_corrupted_frame(), Timeframe.H1)
    text = report.summary()
    assert "problem(s) found" in text
    assert "missing between" in text  # gap location
    assert "already appeared" in text  # duplicate location


def test_empty_frame_is_ok():
    empty = pd.DataFrame(columns=BAR_COLUMNS)
    report = validate(empty, Timeframe.H1)
    assert report.ok and report.n_bars == 0
