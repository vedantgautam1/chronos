"""Structural known-answer tests for Newey & West (1987), Econometrica 55(3),
Eq 5 (the HAC long-run variance) and Theorem 1 (positive semi-definiteness).

The paper gives NO lag-selection rule — it explicitly calls the choice of `m`
"an important topic of future research" — so these pin the estimator's exact
Bartlett weights and its structural guarantees rather than a published table.
[R4 — SOURCED structurally; the lag choice D-R4-m is a documented decision.]

Ported from chronos_math_probe.py Part 1 (R4).
"""

import numpy as np
import pytest

from chronos.moirai.statistics import newey_west, nw_weights


@pytest.mark.parametrize("j, expected", [(1, 0.75), (2, 0.50), (3, 0.25)])
def test_bartlett_weights_exact(j, expected):
    """Modified Bartlett weight w(j, m=3) = 1 - j/(m+1), exact."""
    assert abs(nw_weights(3)[j - 1] - expected) <= 1e-12


def test_m0_reduces_to_omega0():
    """m=0 collapses to Omega_0, the heteroskedasticity-only estimator."""
    rng = np.random.default_rng(11)
    z = rng.normal(size=5000)
    assert abs(newey_west(z, 0) - np.var(z)) <= 1e-12


def test_theorem1_positive_semidefinite():
    """Theorem 1: the estimator is PSD (scalar case => nonnegative) — zero
    negatives across 200 random series."""
    rng = np.random.default_rng(11)
    neg = sum(1 for _ in range(200) if newey_west(rng.normal(size=300), 8) < 0)
    assert neg == 0


def test_iid_hac_matches_ols():
    """iid returns: the HAC long-run variance ~ the OLS variance (ratio ~ 1)."""
    rng = np.random.default_rng(11)
    z = rng.normal(size=200_000)
    assert abs(newey_west(z, 12) / np.var(z) - 1.0) <= 0.05


def test_ar1_hac_ratio():
    """AR(1) rho=0.5: long-run var / var -> (1+rho)/(1-rho) = 3."""
    rng = np.random.default_rng(11)
    rho = 0.5
    e = rng.normal(size=400_000)
    x = np.zeros_like(e)
    for i in range(1, len(e)):
        x[i] = rho * x[i - 1] + e[i]
    assert abs(newey_west(x, 60) / np.var(x) - 3.0) <= 0.15
