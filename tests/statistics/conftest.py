"""Shared fixtures for the statistics known-answer suite.

Kept deliberately minimal. Every stochastic check in this suite is seeded so it
is byte-reproducible across processes (the suite is run twice in CI, the second
pass in a fresh process, to catch machine dependence). Most tests construct
their generator inline where the exact seed and draw order are load-bearing for
the known answer; this fixture is provided for the cases that only need "some
deterministic generator."
"""

import numpy as np
import pytest


@pytest.fixture
def seeded_rng():
    """A deterministic NumPy Generator (fixed seed) for reproducible draws."""
    return np.random.default_rng(0)
