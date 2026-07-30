"""moirai_verify.py — "which of our conclusions still stand?" (§5.3).

Reads every `gauntlet_verdict` record from the production store, recomputes each
verdict's validity AT READ TIME against the currently ACTIVE GauntletConfig, the
current `moirai/` code version, and the current engine core version, and renders a
table marking stale verdicts `INVALIDATED(<reason>)`.

Strictly read-only: it never edits, deletes, or rewrites a record. Invalidation is
computed on read, never stored — the underlying record is immutable.

Phase 2 skeleton: the staleness rows that need Oceanus snapshot infrastructure
(data restatement, §5.3) are deferred; it grows as verdict records begin to exist
(Phase 3+). Run:

    uv run python scripts/moirai_verify.py

Exit 0 on success (including an empty verdict set); exit 1 on error.
"""

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIGS_DIR = _REPO_ROOT / "configs" / "gauntlet"
RECORDS_DIR = _REPO_ROOT / "records"


def _engine_core_version() -> str:
    """Current engine core version — mirrors `chronos.run._core_version` (git HEAD
    + '-dirty' if the working tree has uncommitted changes). Computed locally so
    this read-only tool need not import the engine (and ccxt) merely to read a SHA;
    'unknown' on failure."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=_REPO_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def main() -> int:
    from chronos.moirai.config import load_active_config, moirai_code_version
    from chronos.moirai.verify import verdict_validity
    from chronos.mnemosyne.stub import RecordStore

    config, active_hash, is_calibrated = load_active_config(CONFIGS_DIR)
    current_moirai = moirai_code_version()
    current_engine = _engine_core_version()

    authority = "CALIBRATED" if is_calibrated else "NO_AUTHORITY (uncalibrated)"
    print(f"ACTIVE config      : v{config.version:03d}  hash={active_hash}")
    print(f"authority          : {authority}")
    print(f"moirai code version: {current_moirai}")
    print(f"engine core version: {current_engine}")
    print()

    store = RecordStore(RECORDS_DIR)
    verdicts = [r for r in store.read_all() if r.get("type") == "gauntlet_verdict"]

    if not verdicts:
        print("No verdict records found. Gauntlet has not yet judged anything.")
        return 0

    print(f"{'verdict_id':<22} {'hypothesis_id':<26} {'status':<18} validity")
    print("-" * 96)
    for r in verdicts:
        is_valid, reasons = verdict_validity(
            r,
            active_config_hash=active_hash,
            current_moirai_version=current_moirai,
            current_engine_version=current_engine,
        )
        validity = "valid" if is_valid else "INVALIDATED(" + ",".join(reasons) + ")"
        print(f"{r.get('verdict_id', ''):<22} {r.get('hypothesis_id', ''):<26} "
              f"{r.get('status', ''):<18} {validity}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"moirai_verify: error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
