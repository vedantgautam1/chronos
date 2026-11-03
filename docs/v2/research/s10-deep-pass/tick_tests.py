"""Parameter-recovery test for tick Hawkes (S10 deep pass). Run: python -I -W ignore tick_tests.py"""
import time, numpy as np
from tick.hawkes import SimuHawkesExpKernels, HawkesExpKern, HawkesEM

# Bivariate buy/sell process with known truth.
mu = np.array([0.30, 0.25])                    # baseline events/sec (buy, sell)
adj = np.array([[0.45, 0.10],                  # branching (L1 norm of each kernel)
                [0.15, 0.40]])
beta = 2.0                                     # decay 1/s (memory ~0.5 s)
T = 20_000                                     # seconds of simulated "trades"

sim = SimuHawkesExpKernels(adjacency=adj, decays=beta, baseline=mu,
                           end_time=T, seed=11, verbose=False)
sim.simulate()
ts = sim.timestamps
print(f"simulated events: buys={len(ts[0])}, sells={len(ts[1])}")
print(f"true spectral radius (overall branching) = {max(abs(np.linalg.eigvals(adj))):.3f}")

from tick.hawkes.model import ModelHawkesExpKernLogLik
def negll(decay, lr, events=None):
    m = ModelHawkesExpKernLogLik(decay).fit(events if events is not None else ts)
    return m.loss(np.concatenate([lr.baseline, lr.adjacency.ravel()]))

def fit(decay, label):
    t0 = time.time()
    lr = HawkesExpKern(decays=decay, verbose=False, max_iter=2000, tol=1e-10)   # default gofit: least-squares
    lr.fit(ts)
    rad = max(abs(np.linalg.eigvals(lr.adjacency)))
    ll = negll(decay, lr)
    print(f"{label}: decay={decay}  baseline={lr.baseline.round(3)}  adjacency={lr.adjacency.round(3).tolist()}"
          f"  radius={rad:.3f}  neg-loglik/event={ll:.4f}  {time.time()-t0:.2f}s")
    return -ll

fit(beta, "A. correct decay ")
s = {d: fit(d, "B. wrong decay   ") for d in (0.2, 20.0)}

# C. Does a fit to PURE Poisson (no clustering) report false clustering?
from tick.hawkes import SimuPoissonProcess
pp = SimuPoissonProcess(intensities=mu * 2, end_time=T, seed=3, verbose=False); pp.simulate()
lr = HawkesExpKern(decays=beta, verbose=False); lr.fit(pp.timestamps)
print(f"C. Poisson (no clustering) fit: adjacency={lr.adjacency.round(3).tolist()} radius="
      f"{max(abs(np.linalg.eigvals(lr.adjacency))):.3f}")

# D. Decay chosen by likelihood over a grid recovers the truth?
grid = [0.25, 0.5, 1, 2, 4, 8, 16]
scores = {}
for d in grid:
    m = HawkesExpKern(decays=d, verbose=False); m.fit(ts); scores[d] = -negll(d, m)
print("D. log-likelihood by decay:", {k: round(v, 1) for k, v in scores.items()}, "-> best", max(scores, key=scores.get))
