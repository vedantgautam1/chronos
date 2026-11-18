"""Known-answer tests for ``chronos2.core.timeutil``."""

import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

from chronos2.core.timeutil import UTC, HalfOpen, require_utc


def test_require_utc_accepts_utc():
    dt = datetime(2026, 4, 1, tzinfo=UTC)
    assert require_utc(dt) is dt


def test_require_utc_rejects_naive():
    with pytest.raises(ValueError):
        require_utc(datetime(2026, 4, 1))


def test_require_utc_rejects_non_utc_offset():
    tz = timezone(timedelta(hours=-5))
    with pytest.raises(ValueError):
        require_utc(datetime(2026, 4, 1, tzinfo=tz))


def test_halfopen_contains_start_excludes_end():
    rng = HalfOpen(datetime(2026, 3, 31, tzinfo=UTC), datetime(2026, 4, 1, tzinfo=UTC))
    assert rng.contains(datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC)) is True
    assert rng.contains(datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)) is False


def test_halfopen_rejects_bare_date():
    with pytest.raises((TypeError, ValueError)):
        HalfOpen(date(2026, 3, 31), date(2026, 4, 1))


def test_halfopen_rejects_backwards_range():
    with pytest.raises(ValueError):
        HalfOpen(datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC))


def test_assert_process_utc_passes_under_utc_and_raises_otherwise():
    code = "from chronos2.core.timeutil import assert_process_utc; assert_process_utc()"
    base_env = dict(os.environ)

    utc_env = dict(base_env, TZ="UTC")
    utc_run = subprocess.run(
        [sys.executable, "-c", code], check=False, env=utc_env, capture_output=True, text=True
    )
    assert utc_run.returncode == 0, utc_run.stderr

    toronto_env = dict(base_env, TZ="America/Toronto")
    toronto_run = subprocess.run(
        [sys.executable, "-c", code], check=False, env=toronto_env, capture_output=True, text=True
    )
    assert toronto_run.returncode != 0
