"""Deterministic canonical serialization and content hashing.

Ported from v1 ``chronos.run._canonical`` / ``_config_hash`` and
``chronos.moirai.config._canonical`` (sorted keys, ``Decimal`` as its string,
``datetime`` as ISO-8601, enums by value), tightened for v2: floats by
``repr``, tuples as lists, and it raises on NaN, infinities, naive datetimes,
sets and unknown types.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any


def _datetime_to_iso(dt: datetime) -> str:
    """ISO-8601 with a trailing ``Z`` (requires tz-aware UTC)."""
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    if dt.utcoffset() != timedelta(0):
        raise ValueError("datetime must be in UTC")
    base = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if dt.microsecond:
        base += f".{dt.microsecond:06d}".rstrip("0")
    return base + "Z"


def _canonical(obj: Any) -> Any:
    if isinstance(obj, dict):
        for key in obj:
            if not isinstance(key, str):
                raise TypeError(f"dict keys must be str, got {type(key).__name__}")
        return {
            key: _canonical(value)
            for key, value in sorted(obj.items())
        }
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return _datetime_to_iso(obj)
    if isinstance(obj, Enum):
        return _canonical(obj.value)
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError("float must be finite (NaN and infinity are refused)")
        return repr(obj)
    if isinstance(obj, (str, int)):
        return obj
    if obj is None:
        return None
    if isinstance(obj, set):
        raise TypeError("sets have no canonical order")
    raise TypeError(f"cannot canonicalize {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON string of ``obj`` (sorted keys, no whitespace)."""
    return json.dumps(_canonical(obj), sort_keys=True, separators=(",", ":"))


def content_hash(obj: Any) -> str:
    """SHA-256 hex digest of the canonical JSON of ``obj``."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
