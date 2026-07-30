"""Known-answer tests for Politis & Romano (1994), JASA 89(428), the stationary
bootstrap. Lemma 1 (Eq 5) gives var(sqrt(N) * Xbar*) in CLOSED FORM with no
resampling — so it is a true known-answer for the resampler: if the empirical
bootstrap variance disagrees with Lemma 1, the resampler is wrong. [R5 —
SOURCED (Lemma 1 pinned); the block length D-R5-p is a documented decision.]

Ported from chronos_math_probe.py Part 1 (R5), plus a determinism check.
"""

import numpy as np

from chronos.moirai.statistics import (
    circ_autocov,
    pr_lemma1_variance,
    stationary_bootstrap_indices,
)


def _ma2_series(n=200, seed=2024):
    """The paper-style MA(2) series used as the fixed test process."""
    rng = np.random.default_rng(seed)
    e = rng.normal(size=n + 50)
    return np.array([e[i + 4] + 0.7 * e[i + 3] + 0.4 * e[i + 2] for i in range(n)])


def test_bootstrap_variance_matches_lemma1():
    """MA(2) series: empirical var(sqrt(N) Xbar*) matches Lemma 1's closed form
    within 6% relative (40,000 resamples)."""
    rng = np.random.default_rng(2024)
    N, p, B = 200, 0.10, 40_000
    e = rng.normal(size=N + 50)
    x = np.array([e[i + 4] + 0.7 * e[i + 3] + 0.4 * e[i + 2] for i in range(N)])
    want = pr_lemma1_variance(x, p)
    means = np.empty(B)
    for b in range(B):
        means[b] = x[stationary_bootstrap_indices(N, p, rng)].mean()
    got = N * np.mean((means - x.mean()) ** 2)
    assert abs(got - want) <= 0.06 * want


def test_p1_degenerates_to_iid_bootstrap():
    """p=1: block length 1 everywhere => Lemma 1's sum vanishes -> C_N(0),
    exactly the iid-bootstrap variance."""
    x = _ma2_series()
    assert abs(pr_lemma1_variance(x, 1.0) - circ_autocov(x)[0]) <= 1e-12


def test_bootstrap_indices_deterministic():
    """Same seed => byte-identical bootstrap indices (I10 determinism precursor:
    the gauntlet's only randomness is the single injected, seeded RNG)."""
    a = stationary_bootstrap_indices(200, 0.10, np.random.default_rng(7))
    b = stationary_bootstrap_indices(200, 0.10, np.random.default_rng(7))
    assert np.array_equal(a, b)
