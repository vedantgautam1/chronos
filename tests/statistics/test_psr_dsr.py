"""Known-answer tests for the Probabilistic / Deflated Sharpe Ratio.

Primary source: Bailey & López de Prado (2014), "The Deflated Sharpe Ratio",
JPM 40(5). The four JPM assertions reproduce the paper's worked example exactly.
On green, R1's register status upgrades FORMULA-SOURCED -> SOURCED (spec §4.3,
§10). [R1 — SOURCED.]

Ported from chronos_math_probe.py Part 1 (R1 properties + the TRAP), plus the
four JPM known-answer assertions transcribed in SPEC_MOIRAI §4.3.

If any JPM assertion fails: the implementation or the transcribed value is
wrong. Do NOT widen the tolerance — resolve it against the primary paper.
"""

import numpy as np

from chronos.moirai.statistics import dsr, psr, sr_star

# JPM (2014) worked example: N=100 trials, V annual = 0.5 at 250 obs/yr, so
# per-bar V = 0.5/250 = 0.002; T=1250; skew = -3; raw kurtosis = 10;
# SR_hat (non-annualized) = 2.5/sqrt(250) ~= 0.158114.
SR_HAT = 2.5 / np.sqrt(250)


# --- The four JPM known-answers (SPEC_MOIRAI §4.3) --------------------------

def test_jpm_sr_star():
    """JPM 2014 worked example: SR* (non-annualized)."""
    result = sr_star(V=0.002, N=100)
    assert abs(result - 0.1132) < 0.0002, f"SR* = {result}, expected 0.1132"


def test_jpm_dsr_rejection():
    """JPM 2014 worked example: DSR = 0.9004 — rejected at 95%."""
    result = dsr(sr_hat=SR_HAT, T=1250, V=0.002, N=100, skew=-3.0, kurt=10.0)
    assert abs(result - 0.9004) < 0.0005, f"DSR = {result}, expected 0.9004"


def test_jpm_dsr_fewer_trials():
    """JPM 2014 counterfactual: N=46 → DSR crosses 0.95."""
    result = dsr(sr_hat=SR_HAT, T=1250, V=0.002, N=46, skew=-3.0, kurt=10.0)
    assert abs(result - 0.9505) < 0.0005, f"DSR = {result}, expected 0.9505"


def test_jpm_dsr_normal_returns():
    """JPM 2014 counterfactual: N=88, normal returns → DSR crosses 0.95."""
    result = dsr(sr_hat=SR_HAT, T=1250, V=0.002, N=88, skew=0.0, kurt=3.0)
    assert abs(result - 0.9505) < 0.0005, f"DSR = {result}, expected 0.9505"


# --- Property tests retained from the probe --------------------------------

def test_dsr_monotone_decreasing_in_n():
    """DSR decreases monotonically as the trial count N rises (spec §7)."""
    vals = [dsr(0.05, 50_000, V=1e-4, N=n) for n in [1, 10, 100, 1000, 10_000]]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))


def test_sr_star_scales_as_sqrt_v():
    """SR* scales exactly with sqrt(V): 4x V -> 2x SR* (why correlated sweeps
    self-correct)."""
    assert abs(sr_star(4e-4, 280) / sr_star(1e-4, 280) - 2.0) <= 1e-10


def test_floored_dsr_zero_edge_at_n1():
    """Floored DSR at N=1 on a zero-edge strategy is ~0.50, not ~1.0."""
    result = dsr(0.0, 50_000, V=1e-4, N=1.0001)
    assert abs(result - 0.50) < 0.01, f"Floored DSR = {result}, expected ~0.50"


# --- The trap: an unfloored SR* passes zero-edge strategies ----------------

def test_unfloored_trap():
    """The unfloored SR* trap: SR* is negative at small N, so an unfloored DSR
    passes a zero-edge strategy ~99.9% of the time at N=1. The floor is the fix."""
    raw = psr(0.0, sr_star(1e-4, 1.0001), 50_000)
    assert raw > 0.99, f"Unfloored should pass zero-edge, got {raw}"
    floored = dsr(0.0, 50_000, V=1e-4, N=1.0001)
    assert abs(floored - 0.50) < 0.01, f"Floored should be ~0.50, got {floored}"
