"""Reading ``v2/config/protected/validation.yaml``, strictly.

The file holds only numbers the master doc has already locked. This loader
refuses anything else: an unknown key, a missing key, or a value of the wrong
shape. A loose loader on a protected file is worse than none, because it would
let a later build add a threshold of its own and have it read as settled.

Loading these values at run time belongs to the builds that use them (B11, B14,
B16, B18). B02 delivers the file, this loader and the schema test.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

SEAL_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SEAL_SYMBOLS = ("BTC", "ETH")

# key -> (python type, decision id)
SCHEMA: dict[str, tuple[type | tuple[type, ...], str]] = {
    "seal": (dict, "V2-D38"),
    "stress_friction_multiplier": (float, "V2-D35"),
    "adverse_funding_percentile": (int, "V2-D39"),
    "adverse_funding_hourly_rate": (dict, "V2-D39"),
    "fragmentation_window_days": (int, "V2-D31"),
    "sealed_confirm_min_trades": (int, "V2-D38"),
}


class ProtectedValuesError(Exception):
    """The protected values are not the shape the master doc locked."""


def load(path: str | Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ProtectedValuesError(f"{path}: expected a mapping at the top level")

    for key in sorted(set(raw) - set(SCHEMA)):
        raise ProtectedValuesError(
            f"{path}: unknown key {key!r}. This file holds only the values the master "
            f"doc has locked: {', '.join(sorted(SCHEMA))}. A new one is a protected "
            "change and needs the founder."
        )
    for key in sorted(set(SCHEMA) - set(raw)):
        raise ProtectedValuesError(
            f"{path}: {key!r} is missing ({SCHEMA[key][1]}). Every locked value must be "
            "present; an absent one is not a default."
        )

    for key, (expected, decision) in SCHEMA.items():
        value = raw[key]
        # bool is a subclass of int in Python: a flag is never a number here.
        if isinstance(value, bool) or not isinstance(value, expected):
            raise ProtectedValuesError(
                f"{path}: {key!r} ({decision}) must be {expected.__name__}, got "
                f"{type(value).__name__} ({value!r})."
            )

    _check_seal(path, raw["seal"])
    if raw["adverse_funding_percentile"] not in range(1, 100):
        raise ProtectedValuesError(
            f"{path}: 'adverse_funding_percentile' (V2-D39) must be a percentile "
            f"between 1 and 99, got {raw['adverse_funding_percentile']!r}."
        )
    for key in ("fragmentation_window_days", "sealed_confirm_min_trades"):
        if raw[key] <= 0:
            raise ProtectedValuesError(
                f"{path}: {key!r} ({SCHEMA[key][1]}) must be positive, got {raw[key]!r}."
            )
    return raw


def _check_seal(path: str | Path, seal: dict) -> None:
    for symbol in SEAL_SYMBOLS:
        if symbol not in seal:
            raise ProtectedValuesError(f"{path}: 'seal' (V2-D38) has no entry for {symbol}.")
    for symbol in sorted(set(seal) - set(SEAL_SYMBOLS)):
        raise ProtectedValuesError(
            f"{path}: 'seal' (V2-D38) has an entry for {symbol!r}, which the master doc "
            "has not sealed. A new instrument's seal is a protected change."
        )
    for symbol, instant in seal.items():
        if not isinstance(instant, str) or not SEAL_INSTANT.fullmatch(instant):
            raise ProtectedValuesError(
                f"{path}: seal[{symbol!r}] must be a full tz-aware UTC instant like "
                f"'2026-04-01T00:00:00Z', got {instant!r}. A bare date is never a range "
                "end in this repository."
            )
