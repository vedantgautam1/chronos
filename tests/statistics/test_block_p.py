"""test_block_p.py — pins `statistics.block_p_from_returns` (D-R5-p).

D-R5-p is a DOCUMENTED DECISION (Politis–Romano's own §5 procedure), provisional —
not a primary-source known-answer like the JPM values. These tests pin its
BEHAVIOUR: the two clamp bounds, the settle rule, invariance to affine transforms
of the series, and determinism. Protected path (statistics.py); CI-required.
"""

import numpy as np

from chronos.moirai.statistics import block_p_from_returns


def test_perfectly_alternating_series_never_settles_uses_cap():
    """A ±1 alternating series has |acf(k)| = 1 at every lag — it NEVER falls inside
    the white-noise band, so the procedure uses the cap T/50. Exact known-answer:
    T=100 → cap = 2 → mean block 2 → p = 0.5."""
    x = np.array([1.0, -1.0] * 50)  # length 100, perfectly alternating
    assert block_p_from_returns(x) == 0.5


def test_zero_variance_series_returns_iid():
    """A constant series has no dependence to preserve (C_N(0)=0) → p=1 (block 1,
    i.i.d.)."""
    assert block_p_from_returns(np.full(200, 3.14)) == 1.0


def test_too_short_series_returns_iid():
    assert block_p_from_returns([0.1, -0.2]) == 1.0


def test_white_noise_settles_immediately_iid():
    """Uncorrelated returns settle inside the band at the first lag → block 1 → p=1.
    Fixed seed, large T (deterministic)."""
    x = np.random.default_rng(12345).normal(0.0, 1.0, 5000)
    assert block_p_from_returns(x) == 1.0


def test_strong_positive_autocorrelation_gives_longer_blocks():
    """A strongly autocorrelated AR(1) series settles far later than white noise →
    a LONGER mean block → a SMALLER p, still within [50/T, 1]."""
    rng = np.random.default_rng(7)
    T = 4000
    e = rng.normal(0.0, 1.0, T)
    x = np.empty(T)
    x[0] = e[0]
    for i in range(1, T):
        x[i] = 0.9 * x[i - 1] + e[i]
    p_ar1 = block_p_from_returns(x)
    p_noise = block_p_from_returns(rng.normal(0.0, 1.0, T))
    assert p_ar1 < p_noise            # autocorrelation → longer blocks
    assert 50.0 / T <= p_ar1 <= 1.0   # clamped to [50/T (cap), 1 (floor)]


def test_invariant_to_affine_transform_of_returns():
    """The block choice depends only on autocorrelations, which are invariant to
    scaling and shifting the series."""
    x = np.random.default_rng(3).normal(0.0, 2e-3, 1500)
    base = block_p_from_returns(x)
    assert block_p_from_returns(5.0 * x) == base
    assert block_p_from_returns(x + 10.0) == base
    assert block_p_from_returns(5.0 * x - 7.0) == base


def test_deterministic():
    x = np.random.default_rng(99).normal(0.0, 1e-3, 2000)
    assert block_p_from_returns(x) == block_p_from_returns(x)
