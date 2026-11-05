"""S12 deep-pass checks (see PREREGISTERED.md). Run: python -I s12_checks.py <path-to-agentlab-lab> <out.json>"""
import sys, json, time, warnings
import numpy as np
sys.path.insert(0, sys.argv[1]); warnings.filterwarnings("ignore")
from agentlab import world, engine as E, evalr as V, ledger as L
from agentlab.stats import wilson

T0 = time.time(); OUT = {}
POOL = [{"vol_max": 1.0}, {"vol_max": 1.25}, {"vol_max": 1.5}, {"vol_max": 2.0}, {"trend": 1}, {"skip_open": 2}, {"skip_open": 4}, {"skip_open": 6}, {"lookback": 15}, {"lookback": 30}, {"hold": 6}, {"hold": 15}]
TRUTH = np.array([True, True, True, False, False, False, True, True, False, False, False, False])
FAMILY = ["vol"] * 4 + ["trend"] + ["session"] * 3 + ["lookback"] * 2 + ["hold"] * 2
cands = [{**E.BASE, **h} for h in POOL]; lg = L.Ledger()
rate = lambda hits: dict(rate=float(np.mean(hits)), k=int(np.sum(hits)), n=len(hits), wilson95=wilson(int(np.sum(hits)), len(hits)))

# ---------- the ledger's own counts under fragmentation
b = world.make_bars(6000, edge=0.0); a = lg.register_version(E.BASE)
for i, h in enumerate(cands):
    v = lg.register_version(h); lg.plan(f"candidate {i} helps", f"fam{i}", a, v, b, 0, 750, 0.0)
OUT["ledger_counts"] = dict(attempts_one_family=lg.attempts("fam0"), attempts_all=lg.attempts())

# ---------- P-3: false finds on a pure null under four counting rules
t_all = []
for s in range(6000, 6100):
    b = world.make_bars(s, edge=0.0)
    t_all.append([lg.measure(b, E.BASE, h, 0, 750, 0.0, check_leak=False)["diff_t"] for h in cands])
t_all = np.array(t_all)
fam_sizes = {f: FAMILY.count(f) for f in set(FAMILY)}
bar_nat = np.array([V.sidak_z(fam_sizes[f]) for f in FAMILY])
OUT["P3"] = dict(
    one_family_12=rate((t_all >= V.sidak_z(12)).any(1)),
    natural_families=rate((t_all >= bar_nat).any(1)),
    each_own_family=rate((t_all >= V.sidak_z(1)).any(1)),
    union_N_12=rate((t_all >= V.sidak_z(12)).any(1)),
    bars=dict(single=V.sidak_z(1), N12=V.sidak_z(12), natural={f: V.sidak_z(n) for f, n in fam_sizes.items()}))
print("P3", json.dumps(OUT["P3"], default=float), f"{time.time()-T0:.0f}s", flush=True)

# ---------- P-4: change check with and without "candidate must make money"
D0, D1 = 750, 1125; z = V.sidak_z(12)
def judge(b):
    r2 = [lg.measure(b, E.BASE, h, D0, D1, 4.0, check_leak=False) for h in cands]
    r1 = [lg.measure(b, E.BASE, h, D0, D1, 2.0, check_leak=False) for h in cands]
    A = np.array([r["diff_t"] >= z for r in r2])
    net2 = np.array([r["cand"]["net_bps"] > 0 for r in r2]); net1 = np.array([r["cand"]["net_bps"] > 0 for r in r1])
    return A, A & net2, A & net1, r2[0]["base"]["net_bps"], np.array([r["cand"]["net_bps"] for r in r2])
res = {}
for name, edge, seeds in (("no_edge", 0.0, range(6100, 6160)), ("planted", 1.0, range(6200, 6260))):
    rows = [judge(world.make_bars(s, edge=edge)) for s in seeds]
    out = dict(baseline_net_bps_2x=float(np.mean([r[3] for r in rows])),
               best_candidate_net_bps_2x=float(np.mean([r[4].max() for r in rows])))
    for k, lab in ((0, "A_paired_only"), (1, "B_net_pos_2x"), (2, "B1_net_pos_1x")):
        acc = np.array([r[k] for r in rows])
        out[lab] = dict(any_accept=rate(acc.any(1)), helpful_accept=rate((acc & TRUTH).any(1)), unhelpful_accept=rate((acc & ~TRUTH).any(1)),
                        mean_accepted=float(acc.sum(1).mean()))
    res[name] = out; print("P4", name, json.dumps(out, default=float), f"{time.time()-T0:.0f}s", flush=True)
OUT["P4"] = res
json.dump(OUT, open(sys.argv[2], "w"), indent=1, default=float); print("done", f"{time.time()-T0:.0f}s")
