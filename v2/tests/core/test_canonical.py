"""Known-answer tests for ``chronos2.core.canonical``."""

from datetime import datetime
from decimal import Decimal

import pytest

from chronos2.core.canonical import canonical_json, content_hash
from chronos2.core.timeutil import UTC


def test_content_hash_is_order_independent():
    left = content_hash({"b": 1, "a": [1.0, Decimal("0.10")]})
    right = content_hash({"a": [1.0, Decimal("0.10")], "b": 1})
    assert left == right


def test_content_hash_changes_with_float_bit():
    a = content_hash({"x": [1.0]})
    b = content_hash({"x": [1.0000000000000002]})
    assert a != b


def test_content_hash_rejects_nan():
    with pytest.raises(ValueError):
        content_hash({"x": float("nan")})


def test_content_hash_rejects_naive_datetime():
    with pytest.raises(ValueError):
        content_hash({"x": datetime(2026, 4, 1)})


def test_canonical_json_datetime_uses_z():
    assert (
        canonical_json({"t": datetime(2026, 4, 1, tzinfo=UTC)})
        == '{"t":"2026-04-01T00:00:00Z"}'
    )


def test_canonical_rejects_infinity():
    with pytest.raises(ValueError):
        canonical_json({"x": float("inf")})


def test_canonical_rejects_set():
    with pytest.raises(TypeError):
        canonical_json({"x": {1, 2}})


def test_canonical_rejects_unknown_type():
    with pytest.raises(TypeError):
        canonical_json({"x": object()})
