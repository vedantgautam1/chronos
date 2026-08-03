"""statistics.py — the Moirai's pure-math statistical core.

Promoted from the standalone `chronos_math_probe.py` (repo root, retained as a
historical artifact). This is the module every Moira calls for anything
statistical. It is deliberately pure math:

  * No engine imports (nothing from `chronos.hephaestus`, `chronos.run`,
    `chronos.mnemosyne`).
  * No data imports (nothing from `chronos.oceanus`).
  * No I/O (no file reads, no prints, no network).
  * Only `numpy` and `scipy.stats` as dependencies.

Every function is derived from a primary source and pinned by a known-answer
test in `tests/statistics/`. The implementations are byte-identical in logic to
the probe's; if a known-answer test disagrees, the implementation is wrong until
proven otherwise against the primary paper — the numbers do not change.

SOURCES
  Lo (2002)  "The Statistics of Sharpe Ratios", FAJ 58(4)   -> Eq 9, Eq 22, Tables 1 & 2
  Newey & West (1987), Econometrica 55(3)                   -> Eq 5, Theorem 1
  Politis & Romano (1994), JASA 89(428)                     -> Sec 2, Lemma 1 Eq 5
  Bailey & López de Prado (2014), JPM 40(5)                 -> PSR, DSR (SR*) — R1 PRIMARY
        The DSR/PSR forms below match AFML (2018) §14.7; R1's four JPM
        known-answer assertions (§4.3 of the spec) pin them to the published
        worked example. R1 register status: SOURCED.
"""

import numpy as np
from scipy.stats import norm

EULER = 0.5772156649015329
HOURS_PER_YEAR = 8760.0


# =====================================================================
# METHOD IMPLEMENTATIONS  (each derived from the cited equation)
# =====================================================================

def lo_se_sharpe(sr, T):
    """Lo (2002) Eq 9.  IID standard error of the Sharpe estimator."""
    return np.sqrt((1.0 + 0.5 * sr ** 2) / T)


def lo_eta(q, rho):
    """Lo (2002) Eq 22.  Time-aggregation scale factor under AR(1) returns."""
    if abs(rho) < 1e-15:
        return np.sqrt(q)
    inner = q + 2.0 * rho / (1.0 - rho) * (q - (1.0 - rho ** q) / (1.0 - rho))
    return q / np.sqrt(inner)


def newey_west(h, m):
    """Newey & West (1987) Eq 5, scalar case.
    S_hat = Om_0 + sum_{j=1..m} w(j,m) * (Om_j + Om_j')  with w = 1 - j/(m+1).
    """
    h = np.asarray(h, float)
    h = h - h.mean()
    T = len(h)
    S = np.dot(h, h) / T                      # Omega_0
    for j in range(1, m + 1):
        w = 1.0 - j / (m + 1.0)               # modified Bartlett weight
        om = np.dot(h[j:], h[:-j]) / T        # Omega_j
        S += 2.0 * w * om                     # + Omega_j + Omega_j'
    return S


def nw_weights(m):
    return np.array([1.0 - j / (m + 1.0) for j in range(1, m + 1)])


def circ_autocov(x):
    """C_N(i), the circular autocovariances used in Politis-Romano Lemma 1."""
    x = np.asarray(x, float)
    N = len(x)
    d = x - x.mean()
    dd = np.concatenate([d, d])               # wrap the series around a circle
    return np.array([np.dot(d, dd[i:i + N]) / N for i in range(N)])


def pr_lemma1_variance(x, p):
    """Politis & Romano (1994) Lemma 1, Eq 5.
    Closed form for var(sqrt(N) * Xbar*) under the stationary bootstrap.
    Requires NO resampling -- which is what makes it a known-answer test.
    """
    N = len(x)
    C = circ_autocov(x)
    s = C[0]
    for i in range(1, N):
        s += 2.0 * (1.0 - i / N) * ((1.0 - p) ** i) * C[i]
    return s


def stationary_bootstrap_indices(N, p, rng):
    """Politis & Romano (1994) Sec 2.
    Start uniform. Each step: continue to the next observation w.p. 1-p
    (wrapping X_1 after X_N); otherwise jump to a fresh uniform draw.
    Block lengths are therefore geometric with mean 1/p.
    """
    new = rng.random(N) < p
    new[0] = True
    jump = rng.integers(0, N, N)
    seg = np.maximum.accumulate(np.where(new, np.arange(N), 0))
    return (jump[seg] + (np.arange(N) - seg)) % N


def block_p_from_returns(returns, *, consecutive=5, z=1.96, cap_divisor=50):
    """D-R5-p (spec SPEC_MOIRAI.md s.10): the stationary-bootstrap mean block
    length, chosen per Politis & Romano's own s.5 procedure, returned as the
    block probability p = 1 / mean_block that `stationary_bootstrap_indices`
    consumes.

    Procedure (documented decision, PROVISIONAL — not a primary-source
    known-answer): the mean block 1/p is the SMALLEST lag L at which the
    series' sample autocorrelations sit inside the two-sided 95% white-noise
    band (|acf| <= z/sqrt(T)) for `consecutive` consecutive lags. Clamped to
    [floor 1, cap T/`cap_divisor`]. If the autocorrelations never settle, the
    cap is used (largest block, smallest p — the conservative choice for
    autocorrelated data). Uncorrelated returns settle at L=1 -> mean block 1
    -> p=1, i.e. i.i.d. resampling, which is exactly right when there is no
    dependence to preserve.

    Pure math: consumes `circ_autocov`; no resampling, no I/O, no RNG. The
    band and lag rule are recomputed per evaluation window (T-dependent), as
    the decision requires. Evidence brackets at {p/2, 2p} live in the caller
    (stage 4.1), not here."""
    x = np.asarray(returns, float)
    T = x.size
    if T < 3:
        return 1.0  # too short to estimate dependence — i.i.d. is the honest default
    C = circ_autocov(x)
    c0 = C[0]
    if c0 <= 0.0:
        return 1.0  # zero-variance / degenerate series — no dependence to preserve
    acf = C / c0
    band = z / np.sqrt(T)
    cap = max(1.0, T / cap_divisor)

    settled_lag = None
    for lag in range(1, T):
        window = acf[lag:lag + consecutive]
        if window.size < consecutive:
            break  # not enough lags left to confirm `consecutive` in-band
        if np.all(np.abs(window) <= band):
            settled_lag = lag
            break
    mean_block = cap if settled_lag is None else min(max(float(settled_lag), 1.0), cap)
    return 1.0 / mean_block


def sr_star(V, N):
    """AFML s.14.7.3.  Expected max Sharpe across N trials under H0: SR = 0.
    V is the CROSS-TRIAL VARIANCE of the estimated Sharpes, in the
    ORIGINAL (non-annualized) sampling frequency.
    """
    return np.sqrt(V) * ((1 - EULER) * norm.ppf(1 - 1.0 / N)
                         + EULER * norm.ppf(1 - 1.0 / (N * np.e)))


def psr(sr_hat, sr_bench, T, skew=0.0, kurt=3.0):
    """AFML s.14.7.2.  P(true SR > sr_bench).  sr_hat non-annualized."""
    den = np.sqrt(1.0 - skew * sr_hat + (kurt - 1.0) / 4.0 * sr_hat ** 2)
    return norm.cdf((sr_hat - sr_bench) * np.sqrt(T - 1.0) / den)


def dsr(sr_hat, T, V, N, skew=0.0, kurt=3.0, floor_at_zero=True):
    """DSR = PSR evaluated at the estimated SR*.  See the negative-SR* probe."""
    b = sr_star(V, N)
    if floor_at_zero:
        b = max(b, 0.0)
    return psr(sr_hat, b, T, skew, kurt)


# =====================================================================
# SAMPLE MOMENTS AND EFFECTIVE-N  (consumed by stage 4.3; pure math)
# =====================================================================

def per_bar_sharpe(returns, ddof=1):
    """Non-annualized Sharpe of one return series at its native frequency:
    mean / std(ddof=1). Zero std -> 0.0 (a flat series has no edge to measure).
    This is the SR_hat the DSR consumes (Appendix A: native H1, never annualized)
    and the per-trial statistic V is the cross-trial variance of."""
    r = np.asarray(returns, float)
    if r.size == 0:
        return 0.0
    sd = r.std(ddof=ddof)
    return float(r.mean() / sd) if sd > 0 else 0.0


def sample_skewness(returns):
    """Biased sample skewness g1 (scipy default). Feeds the PSR denominator's
    gamma_3 term; normal -> 0."""
    from scipy.stats import skew as _skew

    r = np.asarray(returns, float)
    if r.size < 2 or r.std() == 0:
        return 0.0
    return float(_skew(r, bias=True))


def sample_kurtosis(returns):
    """Biased RAW sample kurtosis (scipy `fisher=False`); normal -> 3. Feeds the
    PSR denominator's gamma_4 term. Raw, not excess — the DSR form here expects
    the normal baseline at 3 (see `psr`)."""
    from scipy.stats import kurtosis as _kurtosis

    r = np.asarray(returns, float)
    if r.size < 2 or r.std() == 0:
        return 3.0
    return float(_kurtosis(r, fisher=False, bias=True))


def mean_pairwise_correlation(trial_returns):
    """Average off-diagonal Pearson correlation across a set of trial return
    series (rows = trials, columns = aligned observations). Undefined with fewer
    than two trials -> NaN. Used by the JPM Appendix C effective-N estimator."""
    mat = np.asarray(trial_returns, float)
    M = mat.shape[0]
    if M < 2:
        return float("nan")
    C = np.corrcoef(mat)
    iu = np.triu_indices(M, k=1)
    return float(np.nanmean(C[iu]))


def effective_trials(rho_bar, M):
    """Bailey & Lopez de Prado (2014), JPM 40(5), Appendix C:
        N_hat = rho_bar + (1 - rho_bar) * M
    the effective number of INDEPENDENT trials among M correlated ones. At
    rho_bar = 0 (independent) N_hat = M; at rho_bar = 1 (identical) N_hat = 1.
    Pure formula; the paper's own guard (compute only when M < T/2, else the
    estimate is unreliable) lives in the caller (stage 4.3, D-08), not here.
    R7 register: partial promotion per D-08 — gate stays on raw N; N_hat is
    evidence only."""
    return float(rho_bar + (1.0 - rho_bar) * M)


# =====================================================================
# CALIBRATION SUPPORT  (used by the Phase 5 calibration harness)
# =====================================================================

def atropos_years(sr_annual, alpha=0.05, power=0.80):
    """Years of SEALED data needed to detect a true annual Sharpe with `power`.
    Derived from Lo Eq 9. The sampling frequency cancels: z ~= sqrt(years)*SR_ann.
    """
    z = norm.ppf(1 - alpha) + norm.ppf(power)
    return z ** 2 / sr_annual ** 2


def sweep_trial_variance(n_bars, cost_bps=42.0, seed=1, ann_vol=0.60):
    """Simulate the 280-point MA sweep on a ZERO-EDGE path and return
    V[{SR_n}] -- the cross-trial variance of per-bar Sharpes. This is the
    quantity the DSR actually consumes, and nothing in Chronos computes it yet.
    """
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, ann_vol / np.sqrt(HOURS_PER_YEAR), n_bars)
    px = np.exp(np.cumsum(r))
    cs = np.cumsum(np.insert(px, 0, 0.0))
    sma = lambda w: np.concatenate([np.full(w - 1, np.nan), (cs[w:] - cs[:-w]) / w])
    fasts, slows = np.arange(5, 55, 5), np.arange(60, 200, 5)   # 10 x 28 = 280
    cache = {w: sma(w) for w in set(fasts) | set(slows)}
    out = []
    for f in fasts:
        for s in slows:
            pos = np.roll(np.nan_to_num((cache[f] > cache[s]).astype(float)), 1)
            pos[0] = 0.0
            turn = np.abs(np.diff(np.insert(pos, 0, 0.0)))
            ret = pos * r - turn * (cost_bps / 1e4)
            sd = ret.std(ddof=1)
            out.append(ret.mean() / sd if sd > 0 else 0.0)
    return float(np.var(out, ddof=1))
