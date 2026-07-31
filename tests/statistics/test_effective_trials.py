"""Known-answer tests for the JPM Appendix C effective-N estimator (R7, D-08).

Source: Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio", JPM 40(5),
Appendix C. The estimator N_hat = rho_bar + (1 - rho_bar) * M collapses M
correlated trials to an effective count of independent ones.

Added in Moirai Phase 4a: stage 4.3 reports DSR at N_hat as evidence (never as
the gate — the gate stays on raw N, strictly conservative since N_hat <= M). The
estimator is pure math here and is NEVER reimplemented inside a Moira.

Like the rest of tests/statistics/, this suite is seeded/deterministic and is run
twice in CI (the second pass in a fresh process) to catch machine dependence.
"""

import numpy as np

from chronos.moirai.statistics import (
    effective_trials,
    mean_pairwise_correlation,
    per_bar_sharpe,
)


# --- effective_trials: the JPM Appendix C formula, at its exact anchor points ---

def test_independent_trials_effective_equals_actual():
    """rho_bar = 0 (independent trials) -> N_hat = M. Exact."""
    assert effective_trials(0.0, 100) == 100.0
    assert effective_trials(0.0, 1) == 1.0


def test_identical_trials_collapse_to_one():
    """rho_bar = 1 (perfectly correlated trials) -> N_hat = 1. Exact: the whole
    search was effectively one trial, no matter how many cells were swept."""
    assert effective_trials(1.0, 100) == 1.0
    assert effective_trials(1.0, 280) == 1.0


def test_half_correlated_midpoint():
    """rho_bar = 0.5, M = 100 -> 0.5 + 0.5*100 = 50.5. Exact."""
    assert effective_trials(0.5, 100) == 50.5


def test_effective_n_never_exceeds_m_for_nonneg_correlation():
    """For 0 <= rho_bar <= 1, N_hat in [1, M] — the gate on raw N is therefore
    strictly conservative (N_hat <= M). Property check across a grid."""
    for M in (2, 10, 280):
        for rho in np.linspace(0.0, 1.0, 11):
            n_hat = effective_trials(rho, M)
            assert 1.0 - 1e-9 <= n_hat <= M + 1e-9


# --- mean_pairwise_correlation: known correlation structures --------------------

def test_identical_series_correlation_is_one():
    """Two identical (non-constant) series -> mean pairwise correlation 1.0."""
    base = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
    assert mean_pairwise_correlation([base, base.copy()]) == 1.0


def test_negated_series_correlation_is_minus_one():
    """A series and its negation -> correlation -1.0."""
    base = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
    assert abs(mean_pairwise_correlation([base, -base]) - (-1.0)) < 1e-12


def test_single_trial_correlation_is_nan():
    """Fewer than two trials -> undefined (NaN), so the caller's D-08 guard fires."""
    assert np.isnan(mean_pairwise_correlation([np.array([0.1, 0.2, 0.3])]))


def test_effective_n_from_correlation_roundtrip():
    """Two identical trials -> rho_bar 1.0 -> N_hat 1.0 (the collapse, end to end)."""
    base = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
    rho = mean_pairwise_correlation([base, base.copy()])
    assert effective_trials(rho, 2) == 1.0


# --- per_bar_sharpe: the DSR's non-annualized input -----------------------------

def test_per_bar_sharpe_matches_definition():
    r = np.array([0.01, -0.005, 0.02, 0.0, -0.01])
    assert abs(per_bar_sharpe(r) - r.mean() / r.std(ddof=1)) < 1e-15


def test_per_bar_sharpe_flat_series_is_zero():
    assert per_bar_sharpe(np.zeros(10)) == 0.0
    assert per_bar_sharpe(np.array([])) == 0.0
