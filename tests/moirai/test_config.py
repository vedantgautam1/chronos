"""Phase 2 — GauntletConfig, I9 enforcement, and the read-time validity logic.

Covers: config fundamentals (round-trip + cross-process hash determinism, ACTIVE
pointer resolution, the §5.2 activation guard, dangling-pointer error, spec-§4 key
coverage), probe G2 (fixed judge — hash mismatch + no hardcoded gate literals), and
probe G3 (visible invalidation — INVALIDATED rendered at read time, record bytes
untouched). Protected-path file (`tests/moirai/`).
"""

import json
import re
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from chronos.moirai.config import (
    GauntletConfig,
    config_hash,
    load_active_config,
    load_config,
    serialize_config,
)
from chronos.moirai.verify import (
    ENGINE_CHANGED,
    JUDGE_CHANGED,
    JUDGE_CODE_CHANGED,
    verdict_validity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = REPO_ROOT / "configs" / "gauntlet"
V001_PATH = CONFIGS_DIR / "v001.json"


# --- Serialization contract: the copied _canonical must not drift from run's ----

def test_serialization_mechanism_matches_run():
    """config.py copies `_canonical` from run.py; this pins the two byte-for-byte
    on inputs exercising every branch (dataclass, mapping, tuple, Decimal,
    datetime, Enum), so a change to one that isn't mirrored fails CI."""
    from chronos.run import RunKind, _canonical as run_canonical
    from chronos.moirai.config import _canonical as moirai_canonical

    sample = {
        "b": [1, 2, Decimal("3.5")],
        "a": {"z": True, "y": (1, 2, "x")},
        "d": datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        "kind": RunKind.SEARCH,
    }
    dump = lambda c: json.dumps(c, sort_keys=True, separators=(",", ":"))
    assert dump(run_canonical(sample)) == dump(moirai_canonical(sample))


# --- Config fundamentals --------------------------------------------------------

def test_config_round_trip_determinism():
    """Same config file → same hash, twice, same process."""
    assert config_hash(load_config(V001_PATH)) == config_hash(load_config(V001_PATH))


def test_config_hash_cross_process():
    """Same config → same hash in a fresh subprocess (the I9 foundation)."""
    code = (
        "from pathlib import Path;"
        "from chronos.moirai.config import load_config, config_hash;"
        f"print(config_hash(load_config(Path(r'{V001_PATH}'))))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, check=True)
    assert out.stdout.strip() == config_hash(load_config(V001_PATH))


def test_active_pointer_resolution():
    """ACTIVE points to v001.json, which exists and loads to version 1."""
    config, hash_, _ = load_active_config(CONFIGS_DIR)
    assert config.version == 1
    assert isinstance(hash_, str) and len(hash_) == 64


def test_uncalibrated_flag():
    """v001 has no calibration report on disk → is_calibrated is False (§5.2).
    CAL-001.md is produced in Phase 6; until then verdicts stamp NO_AUTHORITY."""
    _, _, is_cal = load_active_config(CONFIGS_DIR)
    assert is_cal is False


def test_dangling_active_pointer(tmp_path):
    """ACTIVE pointing to a nonexistent file → a clear FileNotFoundError."""
    (tmp_path / "ACTIVE").write_text("v999.json\n")
    with pytest.raises(FileNotFoundError):
        load_active_config(tmp_path)


def test_all_spec_threshold_keys_present():
    """Every threshold family referenced in spec §4 exists in v001."""
    config = load_config(V001_PATH)
    required_prefixes = [
        "eligibility", "null_signal", "plateau", "dsr",
        "mc_shuffle", "cost_stress", "capacity", "shift",
        "subperiod", "null_bench", "calibration", "nw_lag", "bootstrap_p",
    ]
    for prefix in required_prefixes:
        matching = [k for k in config.thresholds if k.startswith(prefix)]
        assert matching, f"No threshold keys with prefix '{prefix}'"


# --- Probe G2 — fixed judge (I9) ------------------------------------------------

def test_g2_hash_mismatch_refuses_judgment():
    """In-memory threshold mutation → the hash changes (a mutated judge is a
    different judge; the verify path refuses to treat it as the same one)."""
    config = load_config(V001_PATH)
    original_hash = config_hash(config)
    mutated_thresholds = dict(config.thresholds)
    mutated_thresholds["dsr.confidence"] = 0.99  # was 0.95
    mutated = replace(config, thresholds=mutated_thresholds)
    assert config_hash(mutated) != original_hash


def test_g2_no_numeric_gate_literals():
    """No numeric literals adjacent to comparison operators in moirai/ gate code
    (SPEC §9 G2). Crude and broad by design — the contract Phase 4's gate code
    must satisfy. Allowed exceptions: the config loader, statistics.py (pure
    math), package init, tests, and calibration."""
    moirai_dir = REPO_ROOT / "src" / "chronos" / "moirai"
    gate_pattern = re.compile(
        r'(?:score|passed|result|sharpe|dsr|psr|pvalue|p_value|drawdown|degradation|fraction)'
        r'\s*(?:>=?|<=?|==|!=)\s*\d+\.?\d*'
        r'|'
        r'\d+\.?\d*\s*(?:>=?|<=?|==|!=)\s*'
        r'(?:score|passed|result|sharpe|dsr|psr|pvalue|p_value|drawdown|degradation|fraction)',
        re.IGNORECASE,
    )
    violations = []
    for py_file in moirai_dir.rglob("*.py"):
        if py_file.name in ("config.py", "statistics.py", "__init__.py"):
            continue
        if "test" in py_file.name or "calibration" in str(py_file):
            continue
        for i, line in enumerate(py_file.read_text().splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if gate_pattern.findall(line):
                violations.append(f"{py_file.name}:{i}: {line.strip()}")
    assert not violations, (
        "Hardcoded gate literals found in moirai/ (must read from config):\n"
        + "\n".join(violations)
    )


# --- Probe G3 — visible invalidation --------------------------------------------

def _sample_verdict(config_hash_: str, moirai_ver: str, engine_ver: str) -> dict:
    return {
        "type": "gauntlet_verdict",
        "verdict_id": "000001-verdict",
        "judged_run_id": "000285-H-001-ma-crossover",
        "hypothesis_id": "H-001-ma-crossover",
        "status": "FAIL",
        "gauntlet_config_hash": config_hash_,
        "moirai_code_version": moirai_ver,
        "engine_core_version": engine_ver,
    }


def test_g3_visible_invalidation(tmp_path):
    """Verdict written under v001; activate v002 → verify renders
    INVALIDATED(judge_changed); the stored record bytes are untouched."""
    from chronos.mnemosyne.stub import RecordStore

    v001 = load_config(V001_PATH)
    v001_hash = config_hash(v001)
    moirai_ver, engine_ver = "aaa111-moirai", "bbb222-engine"
    verdict = _sample_verdict(v001_hash, moirai_ver, engine_ver)

    store = RecordStore(tmp_path)
    store.append({"type": "run", "run_id": "x"})  # a non-verdict record, ignored
    store.append(verdict)
    records_file = tmp_path / "runs.jsonl"
    before = records_file.read_bytes()

    # Under the unchanged judge + matching versions → valid.
    ok, reasons = verdict_validity(
        verdict, active_config_hash=v001_hash,
        current_moirai_version=moirai_ver, current_engine_version=engine_ver)
    assert ok and reasons == []

    # Activate v002 (one threshold changed) → the verdict is now stale.
    mutated = dict(v001.thresholds)
    mutated["dsr.confidence"] = 0.99
    v002_hash = config_hash(replace(v001, thresholds=mutated, version=2))
    assert v002_hash != v001_hash

    invalid, reasons2 = verdict_validity(
        verdict, active_config_hash=v002_hash,
        current_moirai_version=moirai_ver, current_engine_version=engine_ver)
    assert invalid is False
    assert reasons2 == [JUDGE_CHANGED]

    # Invalidation is computed at read time, never stored: record bytes unchanged.
    assert records_file.read_bytes() == before


def test_verdict_validity_reason_codes():
    """All three implemented staleness rows fire; a None engine version skips the
    engine row rather than reporting a spurious change."""
    rec = _sample_verdict("H", "M", "E")
    ok, reasons = verdict_validity(
        rec, active_config_hash="H", current_moirai_version="M",
        current_engine_version="E")
    assert ok and reasons == []

    bad, reasons = verdict_validity(
        rec, active_config_hash="X", current_moirai_version="Y",
        current_engine_version="Z")
    assert not bad
    assert set(reasons) == {JUDGE_CHANGED, JUDGE_CODE_CHANGED, ENGINE_CHANGED}

    ok2, reasons2 = verdict_validity(
        rec, active_config_hash="H", current_moirai_version="M",
        current_engine_version=None)
    assert ok2 and reasons2 == []
