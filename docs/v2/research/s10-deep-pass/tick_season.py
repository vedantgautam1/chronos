"""Does a time-varying (seasonal) but non-clustered arrival rate fool a constant-baseline Hawkes fit?"""
import numpy as np
from tick.hawkes import HawkesExpKern
rng = np.random.default_rng(5)
T = 20_000.0; period = 2_000.0                   # 10 "days" of 2,000 s each
lam = lambda t: 0.5 * (1 + 0.8 * np.sin(2*np.pi*t/period))   # rate swings 0.1..0.9 /s, NO clustering
def inhom(lmax=0.9):
    n = rng.poisson(lmax*T); t = np.sort(rng.uniform(0, T, n))
    return t[rng.uniform(0, lmax, n) < lam(t)]
ev = [inhom(), inhom()]
print("events:", [len(e) for e in ev])
for d in (0.05, 0.2, 2.0):
    m = HawkesExpKern(decays=d, verbose=False); m.fit(ev)
    print(f"decay {d:>5}: fitted adjacency={m.adjacency.round(3).tolist()} radius={max(abs(np.linalg.eigvals(m.adjacency))):.3f}  (truth: 0)")
# duplicate timestamps (one taker order hitting several resting orders prints several trades at the same time)
t = np.sort(np.concatenate([inhom(), ]))
dup = np.sort(np.concatenate([t, t[::3]]))      # a third of trades printed twice at the same time
m = HawkesExpKern(decays=2.0, verbose=False); m.fit([dup])
print(f"with duplicate timestamps (no real clustering): radius={m.adjacency.ravel()[0]:.3f}")
