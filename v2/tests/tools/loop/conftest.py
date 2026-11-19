"""Path setup for the loop tests (B03 step 1).

Fixtures and helpers only. No ``pytest_*`` hooks, no ``autouse``, nothing that
changes which tests run or how they are collected -- the ``plumbing`` guard
forbids exactly that.

One import-affecting line lives here, disclosed in the build report and copied
from the precedent B02 set in ``tests/tools/guards/conftest.py``: the loop code
is at ``v2/tools/loop/``, outside the ``chronos2`` package, and B03's spec does
not list ``v2/pyproject.toml`` in ``touches``, so ``pythonpath`` cannot be set
there. The path is added here instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
LOOP_DIR = REPO_ROOT / "v2" / "tools" / "loop"
if str(LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(LOOP_DIR))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
