"""Known-answer tests for Lo (2002), "The Statistics of Sharpe Ratios",
FAJ 58(4). Every target value below is printed in the paper's own tables:
Eq 9 vs Table 1 (asymptotic SE of the Sharpe estimator) and Eq 22 vs Table 2
(AR(1) time-aggregation scale factor). [R3 — SOURCED.]

Ported verbatim from chronos_math_probe.py Part 1 (R3a, R3b). The numbers do
not change; if a check fails, the port is wrong.
"""

import pytest

from chronos.moirai.statistics import lo_eta, lo_se_sharpe

# Lo (2002) Eq 9 vs Table 1 — (SR, T) -> asymptotic SE, tolerance ±0.0005.
LO_EQ9_TABLE1 = [
    (0.50, 12, 0.306),
    (0.50, 60, 0.137),
    (0.50, 500, 0.047),
    (1.00, 60, 0.158),
    (1.50, 60, 0.188),
    (3.00, 60, 0.303),
    (2.00, 250, 0.110),
    (3.00, 500, 0.105),
]

# Lo (2002) Eq 22 vs Table 2 — (rho, q) -> eta scale factor, tolerance ±0.005.
LO_EQ22_TABLE2 = [
    (0.00, 12, 3.46),
    (0.20, 12, 2.88),
    (-0.20, 12, 4.17),
    (0.00, 250, 15.81),
    (0.50, 24, 2.91),
    (-0.50, 24, 8.26),
    (0.90, 250, 3.70),
    (-0.90, 2, 4.47),
]


@pytest.mark.parametrize("sr, T, want", LO_EQ9_TABLE1)
def test_lo_eq9_se_sharpe(sr, T, want):
    """Lo (2002) Eq 9 reproduces Table 1's asymptotic Sharpe SE."""
    assert abs(lo_se_sharpe(sr, T) - want) <= 5e-4


@pytest.mark.parametrize("rho, q, want", LO_EQ22_TABLE2)
def test_lo_eq22_eta(rho, q, want):
    """Lo (2002) Eq 22 reproduces Table 2's AR(1) time-aggregation factor."""
    assert abs(lo_eta(q, rho) - want) <= 5e-3
