"""Phase 0 sanity check: proves the environment and imports work.

If this prints "Oceanus setup OK", the virtual environment is healthy,
all required libraries are installed, and our own package is importable.
"""

import sys

# Import each library Oceanus depends on. If any is missing or broken,
# this script fails loudly instead of printing OK.
import ccxt
import matplotlib
import numpy
import pandas
import pyarrow
import pytest

# Import our own package to confirm the src layout is wired up.
import chronos.oceanus

assert sys.version_info >= (3, 11), "Python 3.11+ required"

print("Oceanus setup OK")
