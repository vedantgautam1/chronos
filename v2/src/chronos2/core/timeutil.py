"""Time helpers: tz-aware UTC everywhere.

Conventions (CLAUDE.md): tz-aware UTC everywhere; half-open ``[start, end)``
ranges with full timestamps, never bare dates. Every Chronos process runs with
``TZ=UTC`` (``BUILD_NOTES.md`` §1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

__all__ = ["UTC", "HalfOpen", "assert_process_utc", "require_utc"]


def require_utc(dt: datetime) -> datetime:
    """Return ``dt`` unchanged if it is timezone-aware and in UTC.

    Raises ``TypeError`` if ``dt`` is not a ``datetime``, ``ValueError`` if it
    is naive, and ``ValueError`` if it carries a non-UTC offset.
    """
    if not isinstance(dt, datetime):
        raise TypeError(f"expected a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (got a naive datetime)")
    if dt.utcoffset() != timedelta(0):
        raise ValueError("datetime must be in UTC")
    return dt


def assert_process_utc() -> None:
    """Raise unless the process's local time zone is UTC.

    A library that reads the machine's local clock can shift a date when the
    machine sits in Toronto, so every Chronos process asserts UTC at startup.
    """
    offset = datetime.now().astimezone().utcoffset()
    if offset != timedelta(0):
        raise RuntimeError(f"process must run with TZ=UTC (local offset is {offset})")


class HalfOpen:
    """A half-open interval ``[start, end)`` in tz-aware UTC."""

    def __init__(self, start: datetime, end: datetime) -> None:
        require_utc(start)
        require_utc(end)
        if start >= end:
            raise ValueError(f"start must be < end (got {start!r} >= {end!r})")
        self.start = start
        self.end = end

    def contains(self, ts: datetime) -> bool:
        """True for ``start <= ts < end``."""
        require_utc(ts)
        return self.start <= ts < self.end
