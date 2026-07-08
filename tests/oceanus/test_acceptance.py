"""Phase 7 — the acceptance tests: Oceanus's definition of done.

Each test encodes one promise from the build brief. Some overlap with
the per-phase tests on purpose: this file is the contract, in one place,
so a reviewer (or a future change) is checked against all of it at once.
"""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from chronos.oceanus.access import get_bars
from chronos.oceanus.ingest import fetch_bars
from chronos.oceanus.model import Timeframe
from chronos.oceanus.store import snapshot_hash
from chronos.oceanus.validate import validate

from .corrupted_fixture import PLANTED, make_corrupted_frame
from .test_ingest import FakeExchange
from .test_store import START, START_MS, make_bars

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_acceptance_1_ingestion_is_idempotent():
    """Protects against: the same request quietly returning different data.

    Fetching one range twice must give identical rows with no duplicates —
    otherwise nothing downstream is reproducible.
    """
    fake = FakeExchange(START_MS, n_bars=100)
    end = START + timedelta(hours=100)
    first = fetch_bars("BTC/USDT", Timeframe.H1, START, end, exchange=fake)
    second = fetch_bars("BTC/USDT", Timeframe.H1, START, end, exchange=fake)
    pd.testing.assert_frame_equal(first, second)
    assert not first["open_time"].duplicated().any()


def test_acceptance_2_validation_catches_every_planted_problem():
    """Protects against: data problems slipping through unreported.

    The corrupted fixture plants a gap, duplicate, out-of-order pair,
    OHLC violation, impossible value, naive timestamp, and outlier.
    validate() must flag every single one.
    """
    report = validate(make_corrupted_frame(), Timeframe.H1)
    for kind, description in PLANTED.items():
        assert kind in report.kinds(), f"validate() missed the planted {kind} ({description})"


def test_acceptance_3_the_door_never_serves_a_partial_bar(tmp_path):
    """Protects against: look-ahead on the newest data.

    The bar still forming right now has an unknowable close. get_bars()
    must exclude it even when the requested range covers the present.
    """
    now = datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    first = current_hour - timedelta(hours=47)
    fake = FakeExchange(int(first.timestamp() * 1000), n_bars=48)  # incl. forming bar

    bars = get_bars("BTC/USDT", Timeframe.H1, first, current_hour + timedelta(hours=1),
                    root=tmp_path, exchange=fake)
    assert bars["is_final"].all()
    assert current_hour not in set(bars["open_time"])  # the forming bar
    assert len(bars) == 47


def test_acceptance_4_snapshot_hash_is_stable_across_runs_and_machines():
    """Protects against: results that can't be tied to their exact data.

    The hash is computed from the data's canonical text form, so this
    EXACT value must come out on any machine, any OS, any library
    version, forever. If this test fails, reproducibility is broken —
    do not "fix" it by updating the constant without understanding why.
    """
    expected = "ac030e556e04f630e5aa932b17f1fbf8b6a581e05fa09c8e96a95b8520227e77"
    assert snapshot_hash(make_bars(24)) == expected


def test_acceptance_5_one_door_guard_nothing_bypasses_oceanus():
    """Protects against: back-door reads that skip validation.

    No application code outside oceanus/ may import ccxt (raw exchange
    access) or oceanus internals (ingest/store), or reference the bar
    data directory. Everything goes through chronos.oceanus.access.
    """
    forbidden_imports = {
        "ccxt": "raw exchange access",
        "chronos.oceanus.ingest": "oceanus internal (use access.get_bars)",
        "chronos.oceanus.store": "oceanus internal (use access.get_bars)",
    }
    offenders = []

    # The ONLY exemption: the Phase 0 setup checker imports every dependency
    # (ccxt included) purely to prove the environment installs correctly.
    # It never touches market data. Anything else added here is a red flag.
    exempt = {REPO_ROOT / "scripts" / "check_setup.py"}

    application_code = list((REPO_ROOT / "src").rglob("*.py"))
    application_code += (REPO_ROOT / "scripts").rglob("*.py")
    for path in application_code:
        if "oceanus" in path.parts or path in exempt:
            continue  # oceanus itself is the one place allowed to do this
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            imported = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            for name in imported:
                for bad, why in forbidden_imports.items():
                    if name == bad or name.startswith(bad + "."):
                        offenders.append(f"{path.relative_to(REPO_ROOT)} imports {name} ({why})")
        if "data/bars" in path.read_text():
            offenders.append(f"{path.relative_to(REPO_ROOT)} references the data directory directly")

    assert not offenders, "one-door rule violated:\n" + "\n".join(offenders)
