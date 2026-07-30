"""config.py — the GauntletConfig: the judge's identity as a hashed artifact (I9).

The judge is a frozen, versioned, hashed artifact that exists *before* any test is
judged by it. Changing a threshold changes the hash, which visibly invalidates
every verdict the old judge issued (§5.3). Enforcement — which SPEC_HEPHAESTUS
deliberately deferred, leaving only the `RunConfig.gauntlet_config_hash` anchor —
lands here.

Serialization mechanism is IDENTICAL to `chronos.run.serialize_result` /
`_config_hash`: sorted keys, no whitespace, Decimals as strings, datetimes as ISO,
Enums as `.value`. `_canonical()` below is copied verbatim from `chronos.run`
rather than imported: importing `chronos.run` would transitively pull in the whole
engine, Oceanus, and ccxt, and the judge (and the read-only verify script) must
stay importable without any of that. `tests/moirai/test_config.py` pins the two
copies together by byte-comparing their output, so they cannot drift.

This module imports only the standard library — no engine, data, or ccxt imports.
"""

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOIRAI_SUBTREE = "src/chronos/moirai"


@dataclass(frozen=True)
class GauntletConfig:
    """THE judge (spec §2). One frozen artifact; §5 governs it.

    Canonical serialization → sha256 = `gauntlet_config_hash`. Every field
    participates in the hash, so any change to any threshold, the pipeline order,
    the evaluation mode, the cost-defaults pin, or the calibration-report path
    produces a new judge identity."""

    version: int                                 # monotonic; v001 = 1
    thresholds: Mapping[str, Any]                # every named key in §4
    pipeline_order: tuple[str, ...]              # moira_ids in execution order
    full_evaluation_mode: bool = False           # §3.2
    cost_defaults_version: str = ""              # pins the CostConfig defaults (§5.3)
    calibration_report: str = ""                 # repo-relative path to the report


def _canonical(obj):
    """Recursively convert to JSON-safe, deterministic primitives.

    Copied verbatim from `chronos.run._canonical` — the shared serialization
    contract. Pinned to that copy by `test_serialization_mechanism_matches_run`."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return _canonical(asdict(obj))
    if isinstance(obj, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    return obj


def serialize_config(config: GauntletConfig) -> str:
    """Canonical serialization, identical mechanism to serialize_result()."""
    return json.dumps(_canonical(config), sort_keys=True, separators=(",", ":"))


def config_hash(config: GauntletConfig) -> str:
    """sha256 of the canonical serialization — the `gauntlet_config_hash`."""
    return hashlib.sha256(serialize_config(config).encode()).hexdigest()


def load_config(path: Path) -> GauntletConfig:
    """Load a GauntletConfig from a JSON file. Raises FileNotFoundError if the
    file does not exist (used by the dangling-ACTIVE-pointer guard)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return GauntletConfig(
        version=data["version"],
        thresholds=data["thresholds"],
        pipeline_order=tuple(data["pipeline_order"]),
        full_evaluation_mode=data.get("full_evaluation_mode", False),
        cost_defaults_version=data.get("cost_defaults_version", ""),
        calibration_report=data.get("calibration_report", ""),
    )


def load_active_config(configs_dir: Path) -> tuple[GauntletConfig, str, bool]:
    """Load the ACTIVE config. Returns (config, hash, is_calibrated).

    `is_calibrated` is True iff `config.calibration_report` resolves (relative to
    the repo root) to an existing file. When False — as for v001 until Phase 6
    produces CAL-001.md — every verdict this config stamps must carry
    authority='NO_AUTHORITY' (§5.2). A `NO_AUTHORITY` verdict is a smoke test,
    not a judgment."""
    configs_dir = Path(configs_dir)
    active_name = (configs_dir / "ACTIVE").read_text(encoding="utf-8").strip()
    config = load_config(configs_dir / active_name)
    is_calibrated = bool(config.calibration_report) and (
        _REPO_ROOT / config.calibration_report
    ).exists()
    return config, config_hash(config), is_calibrated


def moirai_code_version() -> str:
    """Git SHA of HEAD, with a '-dirty' suffix iff the `moirai/` subtree has
    uncommitted changes. Same pattern as `chronos.run._core_version`, but the
    dirty check is scoped to `src/chronos/moirai/`. Returns 'unknown' on failure
    (honest, not crashing)."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", _MOIRAI_SUBTREE],
                               cwd=_REPO_ROOT, capture_output=True, text=True,
                               check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"
