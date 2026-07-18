"""
chronos_math_probe.py
=====================
Standalone. No Chronos code required. Depends only on numpy + scipy.

Run:   python chronos_math_probe.py

WHAT IT DOES
------------
Part 1  KNOWN-ANSWER TESTS. Reimplements four statistical methods straight
        from their primary sources and checks each against a value that is
        PRINTED IN THE PAPER (or, for the bootstrap, against the paper's own
        closed-form identity). If a line says FAIL, the method is wrong.
        These are the tests the Derive-From-Source Register (spec s.11) demands.

Part 2  CALIBRATION. Uses those verified methods to compute the numbers the
        Moirai spec currently leaves as "quant decides":
          - how many years Atropos must hold to have real power
          - the multiple-testing bar a parameter sweep imposes
          - the gauntlet's DETECTION FLOOR: the smallest true edge it can see

Every number is derived, not asserted. Change the assumptions at the bottom
and rerun.

SOURCES
  Lo (2002)  "The Statistics of Sharpe Ratios", FAJ 58(4)   -> Eq 9, Eq 22, Tables 1 & 2
  Newey & West (1987), Econometrica 55(3)                   -> Eq 5, Theorem 1
  Politis & Romano (1994), JASA 89(428)                     -> Sec 2, Lemma 1 Eq 5
  Lopez de Prado, AFML (2018) s.14.7                        -> PSR, DSR (SR*)
        NOTE: AFML is a SECONDARY source. The primary is Bailey & Lopez de
        Prado (2014), JPM 40(5). The formula below is from AFML s.14.7.3.
        Confirm it against the JPM paper before this enters the frozen core.
"""

import numpy as np
from scipy.stats import norm

EULER = 0.5772156649015329
PASS, FAIL = "PASS", "FAIL  <-- INVESTIGATE"


def check(name, got, want, tol):
    ok = abs(got - want) <= tol
    print(f"  [{PASS if ok else FAIL}] {name:<52} got={got: .6f}  want={want: .6f}")
    return ok


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
# PART 1 -- KNOWN-ANSWER TESTS
# =====================================================================

def part1():
    print("=" * 78)
    print("PART 1  KNOWN-ANSWER TESTS  (each value is printed in the cited paper)")
    print("=" * 78)
    ok = []

    print("\nR3a  Lo (2002) Eq 9  vs  Table 1 (asymptotic SE of the Sharpe estimator)")
    for (sr, T, want) in [(0.50, 12, 0.306), (0.50, 60, 0.137), (0.50, 500, 0.047),
                          (1.00, 60, 0.158), (1.50, 60, 0.188), (3.00, 60, 0.303),
                          (2.00, 250, 0.110), (3.00, 500, 0.105)]:
        ok.append(check(f"SE(SR={sr:.2f}, T={T})", lo_se_sharpe(sr, T), want, 5e-4))

    print("\nR3b  Lo (2002) Eq 22  vs  Table 2 (AR(1) time-aggregation scale factor)")
    for (rho, q, want) in [(0.00, 12, 3.46), (0.20, 12, 2.88), (-0.20, 12, 4.17),
                           (0.00, 250, 15.81), (0.50, 24, 2.91), (-0.50, 24, 8.26),
                           (0.90, 250, 3.70), (-0.90, 2, 4.47)]:
        ok.append(check(f"eta(q={q}, rho={rho:+.2f})", lo_eta(q, rho), want, 5e-3))

    print("\nR4   Newey & West (1987)  -- structural properties, not a table")
    print("     (the paper gives NO lag-selection rule; it says so explicitly,")
    print("      calling the choice of m 'an important topic of future research')")
    w = nw_weights(3)
    ok.append(check("w(1,3) exact", w[0], 0.75, 1e-12))
    ok.append(check("w(2,3) exact", w[1], 0.50, 1e-12))
    ok.append(check("w(3,3) exact", w[2], 0.25, 1e-12))

    rng = np.random.default_rng(11)
    # m=0 must collapse to Omega_0 (the heteroskedasticity-only estimator)
    z = rng.normal(size=5000)
    ok.append(check("m=0 reduces to Omega_0", newey_west(z, 0),
                    np.var(z), 1e-12))
    # Theorem 1: positive semi-definite (scalar => nonnegative), on 200 random draws
    neg = sum(1 for _ in range(200) if newey_west(rng.normal(size=300), 8) < 0)
    ok.append(check("Theorem 1: PSD on 200 random series (0 negatives)", neg, 0, 0))
    # iid  => HAC ~ OLS
    z = rng.normal(size=200_000)
    ok.append(check("iid: HAC/OLS ratio ~ 1", newey_west(z, 12) / np.var(z), 1.0, 0.05))
    # AR(1) rho=0.5 => long-run var / var = (1+rho)/(1-rho) = 3
    rho = 0.5
    e = rng.normal(size=400_000)
    x = np.zeros_like(e)
    for i in range(1, len(e)):
        x[i] = rho * x[i - 1] + e[i]
    ok.append(check("AR(1) 0.5: HAC/OLS -> (1+r)/(1-r) = 3",
                    newey_west(x, 60) / np.var(x), 3.0, 0.15))

    print("\nR5   Politis & Romano (1994)  -- resampler validated against Lemma 1")
    print("     (Lemma 1 gives var(sqrt(N) Xbar*) in closed form, no resampling.")
    print("      If the resampler disagrees with it, the resampler is wrong.)")
    rng = np.random.default_rng(2024)
    N, p, B = 200, 0.10, 40_000
    e = rng.normal(size=N + 50)
    x = np.array([e[i + 4] + 0.7 * e[i + 3] + 0.4 * e[i + 2] for i in range(N)])  # MA(2)
    want = pr_lemma1_variance(x, p)
    means = np.empty(B)
    for b in range(B):
        means[b] = x[stationary_bootstrap_indices(N, p, rng)].mean()
    got = N * np.mean((means - x.mean()) ** 2)
    ok.append(check(f"MA(2), p={p}: bootstrap var vs Lemma 1", got, want, 0.06 * want))

    # p = 1 must degenerate to the iid bootstrap: Lemma 1's sum vanishes -> C_N(0)
    ok.append(check("p=1 reduces to iid bootstrap (C_N(0))",
                    pr_lemma1_variance(x, 1.0), circ_autocov(x)[0], 1e-12))

    print("\nR1   PSR / DSR  (AFML s.14.7 -- SECONDARY SOURCE, verify vs Bailey & LdP 2014)")
    # Property: DSR decreases monotonically as trial count rises (spec s.7 requires this)
    vals = [dsr(0.05, 50_000, V=1e-4, N=n) for n in [1, 10, 100, 1000, 10_000]]
    mono = all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))
    ok.append(check("DSR monotonically decreasing in N", float(mono), 1.0, 0))
    # Property: SR* scales exactly with sqrt(V)  -- this is why correlated sweeps self-correct
    ok.append(check("SR* scales as sqrt(V)  [4x V -> 2x SR*]",
                    sr_star(4e-4, 280) / sr_star(1e-4, 280), 2.0, 1e-10))

    print("\n     *** THE TRAP: SR* is NEGATIVE for small N ***")
    for n in [1.0001, 2, 5, 10, 50]:
        print(f"       N={n:>8.0f}   SR* = {sr_star(1e-4, n): .6f}"
              + ("   <-- negative benchmark" if sr_star(1e-4, n) < 0 else ""))
    raw = psr(0.0, sr_star(1e-4, 1.0001), 50_000)
    print(f"     An UNFLOORED DSR passes a zero-edge strategy at N=1 with p={raw:.3f}")
    ok.append(check("floored DSR at N=1, zero edge, ~ 0.50",
                    dsr(0.0, 50_000, V=1e-4, N=1.0001), 0.50, 0.01))

    print(f"\n  {sum(ok)}/{len(ok)} checks passed.")
    return all(ok)


# =====================================================================
# PART 2 -- CALIBRATION
# =====================================================================

HOURS_PER_YEAR = 8760.0


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


def detection_floor(V, N_trials, train_years, hold_years, sharpes,
                    nsim=200_000, seed=5, dsr_thresh=0.95, t_crit=1.645):
    """Monte Carlo the two-gate pipeline: DSR on train, then t-test on holdout.

    Exact and fast: for iid normal returns the sample mean and sample variance
    are independent, mean ~ N(mu, 1/T) and (T-1)s^2 ~ chi2_{T-1}. So we draw
    the two sufficient statistics directly instead of simulating 54,000 bars.
    """
    rng = np.random.default_rng(seed)
    Tt, Th = int(train_years * HOURS_PER_YEAR), int(hold_years * HOURS_PER_YEAR)
    bench = max(sr_star(V, N_trials), 0.0)
    rows = []
    for S in sharpes:
        mu = S / np.sqrt(HOURS_PER_YEAR)
        m_tr = rng.normal(mu, 1.0 / np.sqrt(Tt), nsim)
        s_tr = np.sqrt(rng.chisquare(Tt - 1, nsim) / (Tt - 1))
        g1 = psr(m_tr / s_tr, bench, Tt) > dsr_thresh

        m_ho = rng.normal(mu, 1.0 / np.sqrt(Th), nsim)
        s_ho = np.sqrt(rng.chisquare(Th - 1, nsim) / (Th - 1))
        g2 = (m_ho / s_ho) * np.sqrt(Th) > t_crit
        rows.append((S, g1.mean(), (g1 & g2).mean(), g2.mean()))
    return bench, rows


def part2():
    print("\n" + "=" * 78)
    print("PART 2  CALIBRATION  (the numbers the spec leaves to 'quant decides')")
    print("=" * 78)

    print("\nA. ATROPOS SIZING.  Sealed years needed for 80% power, one-sided 5%.")
    print("   (Lo Eq 9. Sampling frequency cancels -- this is in YEARS, not bars.)")
    for S in [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
        print(f"     true annual Sharpe {S:>4.2f}  ->  {atropos_years(S):>6.2f} years")
    print("   BTC/USDT history begins 2017-08-17: about 8.9 years TOTAL.")

    print("\nB. THE MULTIPLE-TESTING BAR from a 280-point sweep.")
    print("   V[{SR_n}] shrinks as the sample lengthens, so SR* does too.")
    print(f"   {'train':>10} {'V[{SR_n}]':>13} {'SR*/bar':>10} {'SR* ANNUALIZED':>16}")
    for yrs in [0.5, 1, 2, 4, 6.2, 8.9]:
        V = sweep_trial_variance(int(yrs * HOURS_PER_YEAR))
        s = sr_star(V, 280)
        print(f"   {yrs:>7.1f} yr {V:>13.3e} {s:>10.5f} {s*np.sqrt(HOURS_PER_YEAR):>16.3f}")
    print("   Read the last column: the annualized Sharpe you must beat BEFORE")
    print("   the PSR test even begins, purely as a toll for having searched.")

    print("\nC. DETECTION FLOOR.  Gate 1 = DSR>0.95 on train. Gate 2 = t>1.645 on holdout.")
    V = sweep_trial_variance(int(6.2 * HOURS_PER_YEAR))
    for (Ntr, label) in [(280, "280-point sweep"), (1.0001, "pre-registered, N=1")]:
        bench, rows = detection_floor(V, Ntr, 6.2, 2.7,
                                      [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
        print(f"\n   {label}:  SR* = {bench*np.sqrt(HOURS_PER_YEAR):.3f} annualized")
        print(f"   {'true ann SR':>12} {'DSR gate':>10} {'BOTH':>9} {'holdout only':>14}")
        for S, a, b, c in rows:
            tag = "   <-- FALSE POSITIVE RATE" if S == 0 else ""
            print(f"   {S:>12.2f} {a:>9.1%} {b:>8.1%} {c:>13.1%}{tag}")

    print("\n   The S=1.00 row is the whole argument. A real, deployable Sharpe-1")
    print("   strategy is rejected ~99.8% of the time after a 280-point search,")
    print("   and ~50% of the time with no search at all. The lever is the SEARCH,")
    print("   not the estimator. Searching less buys power that no math can.")


if __name__ == "__main__":
    all_ok = part1()
    part2()
    print("\n" + "=" * 78)
    print("VERDICT: " + ("all known-answer tests green." if all_ok
                         else "SOME TESTS FAILED -- do not trust Part 2."))
    print("=" * 78)
