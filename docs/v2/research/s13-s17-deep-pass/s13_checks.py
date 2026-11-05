"""S13-S17 deep-pass checks on the agentlab-lab pack (Parts 3-7). Rules and expectations: PREREGISTERED.md (written before running).
Usage: python -I s13_checks.py /path/to/agentlab-lab out.json [K1,K2,K3,K4]
Run from OUTSIDE the pack folder with -I so nothing in it is imported by accident; the pack path is added explicitly below."""
import json, math, os, sys, time, warnings
PACK, OUT = sys.argv[1], sys.argv[2]
ONLY = sys.argv[3].split(",") if len(sys.argv) > 3 else ["K1", "K2", "K3", "K4"]
sys.path.insert(0, PACK)
import numpy as np
from agentlab import world, engine as E, evalr as V, ladder as Lr, registry as Rg, audit as Au, risk as Rk, papersim as S, loop as L, system as Y
from agentlab.ledger import h12
warnings.filterwarnings("ignore")
C = V.Contract(); GOOD = {**E.BASE, "vol_max": 1.0}; DECOY = {**E.BASE, "trend": 1}; T0 = time.time()
R = json.load(open(OUT)) if os.path.exists(OUT) else {}
def save(): json.dump(R, open(OUT, "w"), indent=1, default=float)
def tick(s): print(f"[{time.time()-T0:6.0f}s] {s}", flush=True)

# ---------------------------------------------------------------- K1: forged promotion evidence
def k1():
    def setup():                                                     # the author's registry-matrix set-up (scripts/p6_experiments.py section 6)
        a = Au.AuditLog(C.hash()); reg = Rg.Registry(a); reg.register("v1", E.BASE); reg.register("v2", GOOD); reg.register("v3", DECOY)
        b = world.make_bars(4242, n_days=1500, edge=1.0); sh = world.make_bars(99, n_days=500, edge=1.0)
        lad = Lr.climb(b, GOOD, E.BASE, C, n_attempts=12, shadow_bars=sh); bad = Lr.climb(b, DECOY, E.BASE, C, n_attempts=12, shadow_bars=sh)
        ctx = dict(risk=Rk.RiskEngine(audit=a), monitor_cfg=dict(false_alarm_rate=0.04, target_far=0.05, reference_trades=300), audit=a, contract_hash=C.hash(), first_deployment_ack=True)
        return a, reg, lad, bad, ctx
    out = {}
    def attempt(name, fn):
        a, reg, lad, bad, ctx = setup(); extra = {}
        try: fn(a, reg, lad, bad, ctx, extra); res = "ACCEPTED"
        except Rg.PromotionRefused as e: res = "refused: " + str(e)
        out[name] = dict(result=res, live_after=reg.live(), **extra); tick(f"K1 {name}: {res}")
    def forged_ladder(a, reg, lad, bad, ctx, extra):
        extra["real_decoy_ladder"] = dict(passed=bad["passed"], stopped_at=bad["stopped_at"])
        fake = dict(candidate_hash=h12(DECOY), dataset="none", contract=C.hash(), rungs=[dict(name=n, status="PASS", detail={}) for n in Lr.RUNGS], passed=True, stopped_at=None, hash="forged")
        reg.promote("v3", "SHADOW", "az", ladder=fake); reg.promote("v3", "LIVE", "az", approver="az", ladder=fake, context=ctx)
    def typed_monitor(a, reg, lad, bad, ctx, extra):
        reg.promote("v2", "SHADOW", "az", ladder=lad); reg.promote("v2", "LIVE", "az", approver="az", ladder=lad, context=dict(ctx, monitor_cfg=dict(false_alarm_rate=0.0, target_far=0.05, reference_trades=10 ** 6)))
    def swapped_audit(a, reg, lad, bad, ctx, extra):
        reg.promote("v2", "SHADOW", "az", ladder=lad); a.db.execute("DROP TRIGGER audit_no_update"); a.db.execute("UPDATE audit SET payload='{}' WHERE seq=2")
        extra["real_audit_verifies"] = a.verify()[0]; fresh = Au.AuditLog(C.hash()); extra["fresh_audit_verifies"] = fresh.verify()[0]
        reg.promote("v2", "LIVE", "az", approver="az", ladder=lad, context=dict(ctx, audit=fresh))
    attempt("K1a forged ladder record for the decoy", forged_ladder)
    attempt("K1b hand-typed monitor calibration", typed_monitor)
    attempt("K1c tampered audit log swapped for a fresh one (no anchor)", swapped_audit)
    R["K1"] = out; save()

# ---------------------------------------------------------------- K2: is the sealed look one look?
def k2():
    out = {}; sh = world.make_bars(99, n_days=500, edge=1.0)
    b = world.make_bars(4242, n_days=1500, edge=1.0); looks = []
    for i in range(2):
        try:
            r = Lr.climb(b, GOOD, E.BASE, C, n_attempts=12, shadow_bars=sh, stop_on_fail=False); s = next(x for x in r["rungs"] if x["name"] == "sealed"); looks.append(dict(status=s["status"], detail=s["detail"]))
        except V.SealedTestBurned as e: looks.append(dict(status="BURNED", detail=str(e)))
    st = V.SealedTest(); shared = []
    for i in range(2):
        try: Lr.climb(b, GOOD, E.BASE, C, n_attempts=12, sealed=st, shadow_bars=sh, stop_on_fail=False); shared.append("looked")
        except V.SealedTestBurned: shared.append("BURNED")
    out["K2a default climb twice on one dataset"] = dict(looks=looks, with_shared_SealedTest=shared); tick(f"K2a {[l['status'] for l in looks]} shared={shared}")
    big = world.make_bars(4242, n_days=1501, edge=1.0); b1 = big.slice_days(0, 1500); w1 = V.windows(b1, C)[2]; w2 = V.windows(big, C)[2]
    ov = max(0, min(w1[1], w2[1]) - max(w1[0], w2[0])); st = V.SealedTest(); st.look(b1, GOOD, E.BASE, C)
    try: st.look(big, GOOD, E.BASE, C); second = "allowed"
    except V.SealedTestBurned: second = "BURNED"
    same_prefix = bool(np.array_equal(b1.close, big.slice_days(0, 1500).close))
    out["K2b dataset one day longer"] = dict(sha_1500=b1.sha, sha_1501=big.sha, sealed_1500=w1, sealed_1501=w2, overlap_share_of_first=ov / (w1[1] - w1[0]), second_look=second, identical_first_1500_days=same_prefix); tick(f"K2b {out['K2b dataset one day longer']}")
    wins = [V.windows(type("B", (), {"n_days": T})(), C)[2] for T in L.CYCLE_DAYS]
    out["K2c Part 5 sealed windows"] = dict(windows=wins, overlap_with_previous=[None] + [max(0, min(a[1], p[1]) - max(a[0], p[0])) / (a[1] - a[0]) for p, a in zip(wins, wins[1:])]); tick(f"K2c {out['K2c Part 5 sealed windows']}")
    # K2d: guided + memory loop, edge worlds, the author's seeds and replication data
    rel = []; per_world = []
    for w in range(60):
        bw = world.make_bars(11000 + w, n_days=1800, edge=1.0); cache = {}
        def rep(i, T, _w=w, _c=cache):
            if (i, T) not in _c: _c[(i, T)] = [world.make_bars(30000 + 100 * _w + 10 * i + k, n_days=T, edge=1.0) for k in range(2)]
            return _c[(i, T)]
        lp = L.Loop(bw, rep, mode="guided", k=3, memory_skip=True, seed=w); lg = lp.run(); seen = {}; ev = []
        for e in lg:
            if not e["sealed"]: continue
            lab = next(r["label"] for r in e["proposals"] if "sealed" in r); win = V.windows(type("B", (), {"n_days": e["days"]})(), C)[2]; key = (e["version"], lab)
            prior = seen.get(key, []); reused = max([max(0, min(win[1], p[1]) - max(win[0], p[0])) for p in prior], default=0) / (win[1] - win[0])
            ev.append(dict(cycle=e["cycle"], version=e["version"], label=lab, confirmed=bool(e["sealed"]["confirmed"]), nth_look_same_idea=len(prior) + 1, share_of_days_already_looked=reused)); seen.setdefault(key, []).append(win)
        per_world.append(ev); rel.extend(ev)
    rep_looks = [x for x in rel if x["nth_look_same_idea"] > 1]
    out["K2d Part 5 loop re-looks"] = dict(worlds=60, sealed_looks=len(rel), worlds_with_a_look=sum(1 for e in per_world if e), repeat_looks_same_idea_same_version=len(rep_looks), worlds_with_repeat=sum(1 for e in per_world if any(x["nth_look_same_idea"] > 1 for x in e)),
                                         median_share_already_looked_on_repeats=float(np.median([x["share_of_days_already_looked"] for x in rep_looks])) if rep_looks else None,
                                         confirmed_on_repeat=sum(x["confirmed"] for x in rep_looks), confirmed_on_first=sum(x["confirmed"] for x in rel if x["nth_look_same_idea"] == 1), labels_repeated=sorted({x["label"] for x in rep_looks}))
    tick(f"K2d {out['K2d Part 5 loop re-looks']}")
    # K2e: optional stopping on overlapping sealed windows, null idea
    rng = np.random.default_rng(1301); N = 20000; Tm = max(L.CYCLE_DAYS); z = V.sidak_z(1, C.confirm_alpha)
    d = rng.standard_normal((N, Tm)); cs = np.concatenate([np.zeros((N, 1)), np.cumsum(d, 1)], 1); cs2 = np.concatenate([np.zeros((N, 1)), np.cumsum(d * d, 1)], 1)
    def tstat(a, b):
        n = b - a; m = (cs[:, b] - cs[:, a]) / n; v = ((cs2[:, b] - cs2[:, a]) - n * m * m) / (n - 1); return m / np.sqrt(v / n)
    hit = np.zeros(N, bool); hit_ind = np.zeros(N, bool); ov_rate = []; ind_rate = []
    for (a, b) in wins:
        hit |= tstat(a, b) >= z; ov_rate.append(float(hit.mean()))
        e = rng.standard_normal((N, b - a)); t = e.mean(1) / (e.std(1, ddof=1) / math.sqrt(b - a)); hit_ind |= t >= z; ind_rate.append(float(hit_ind.mean()))
    out["K2e null idea, P(confirmed at least once)"] = dict(z=z, reps=N, overlapping_loop_windows=ov_rate, non_overlapping_windows=ind_rate); tick(f"K2e {out['K2e null idea, P(confirmed at least once)']}")
    R["K2"] = out; save()

# ---------------------------------------------------------------- K3: risk-engine bypass with the engine in its own process
def k3():
    out = {}
    def setup():
        a = Au.AuditLog(C.hash()); reg = Rg.Registry(a); reg.register("v1", E.BASE); reg.grandfather("v1", "az", "az", "first deployment"); rp = Rk.RiskProcess(token="s3cret"); br = Rg.PaperBroker(); ex = Rg.Executor(reg, rp, br, a); ex.start(E.BASE)
        return a, reg, rp, br, ex
    big = lambda cid: Rk.Order(cid, "buy", 60.0, 100.0, last_price=100.0); ok = lambda cid: Rk.Order(cid, "buy", 1.0, 100.0, last_price=100.0)
    a, reg, rp, br, ex = setup()
    ctrl = ex.submit(big("ctrl")); n0 = len(br.fills); ex.broker.send(big("bypass1")); orders_logged = [e["payload"]["client_id"] for e in a.entries("ORDER")]
    out["K3a call the broker handle directly"] = dict(control_oversize_via_submit=ctrl, fills_before=n0, fills_after=len(br.fills), bypass_in_audit="bypass1" in orders_logged, audit_verifies=a.verify()[0])
    class Yes:
        def check(self, o): return True, []
        def fill(self, o): return None
    ex.risk = Yes(); r = ex.submit(big("bypass2")); ex.risk = rp
    out["K3b swap the executor's risk handle"] = dict(result=r, audit_verifies=a.verify()[0]); rp.stop(); tick(f"K3a {out['K3a call the broker handle directly']}  K3b {r}")
    for how in ("insert", "delete"):
        a, reg, rp, br, ex = setup(); reg.halt("monitor", "drift"); before = ex.submit(ok("h1"))
        if how == "insert": reg.db.execute("INSERT INTO halt (halted, actor, why) VALUES (0,'research','')")
        else: reg.db.execute("DELETE FROM halt")
        reg.db.commit(); after = ex.submit(ok("h2"))
        out[f"K3c un-halt by direct SQL ({how})"] = dict(before=before, halted_after=reg.halted(), after=after, audit_verifies=a.verify()[0], resume_in_audit=bool(a.entries("RESUME"))); rp.stop(); tick(f"K3c {how} {out[f'K3c un-halt by direct SQL ({how})']}")
    a, reg, rp, br, ex = setup(); rp._p.terminate(); rp._p.join(2); n0 = len(br.fills)
    try: r = ex.submit(ok("d1")); res = dict(result=r)
    except Exception as e: res = dict(exception=type(e).__name__)
    out["K3d risk process killed, then submit"] = dict(**res, fills_before=n0, fills_after=len(br.fills)); tick(f"K3d {out['K3d risk process killed, then submit']}")
    # K3e: size-bug sweep
    LEV = 3.0; W = 100; trs = [E.run(world.make_bars(15000 + w, n_days=3000, edge=1.0), GOOD) for w in range(W)]; rng = np.random.default_rng(6); d0s = [int(rng.integers(1700, 2500)) for _ in range(W)]
    def summ(rs): return dict(ruined=float(np.mean([r["ruined"] for r in rs])), max_dd_median=float(np.median([r["max_dd"] for r in rs])), max_dd_p90=float(np.percentile([r["max_dd"] for r in rs], 90)), final_median=float(np.median([r["final"] for r in rs])),
                              killed=float(np.mean([r["killed_day"] is not None for r in rs])), blocked_median=float(np.median([r["blocked"] for r in rs])), reasons={k: int(sum(r["reasons"].get(k, 0) for r in rs)) for k in ("MAX_ORDER_SIZE", "MAX_POSITION", "KILL_SWITCH", "DAILY_LOSS_HALT")})
    sweep = {}
    for m in (1.0, 1.25, 1.5, 1.6, 2.0, 5.0, 20.0):
        free = []; eng = []
        for tr, d0 in zip(trs, d0s):
            bug = (lambda d, d0=d0, m=m: m if d >= d0 else 1.0); free.append(S.simulate(tr, 1500, 3000, LEV, size_mult=bug)); eng.append(S.simulate(tr, 1500, 3000, LEV, risk=Rk.RiskEngine(), size_mult=bug))
        sweep[str(m)] = dict(order_size=LEV * m, free=summ(free), engine=summ(eng)); tick(f"K3e x{m}: free ruined {sweep[str(m)]['free']['ruined']:.2f} dd {sweep[str(m)]['free']['max_dd_median']:.2f} | engine ruined {sweep[str(m)]['engine']['ruined']:.2f} dd {sweep[str(m)]['engine']['max_dd_median']:.2f} reasons {sweep[str(m)]['engine']['reasons']}")
    out["K3e size-bug sweep"] = dict(leverage=LEV, worlds=W, max_order=Rk.RiskLimits().max_order, results=sweep)
    R["K3"] = out; save()

# ---------------------------------------------------------------- K4: CUSUM slack and the break-even reference
def k4():
    PLAN = Y.Plan(); SHIFT = PLAN.l0 + 500; GRID = [float(x) for x in np.arange(1.0, 120.5, 0.5)]; NC = 200
    def streams(seed, shift):
        b = world.make_bars(seed, n_days=PLAN.total, edge=1.0, shift_day=shift); tr = E.run(b, GOOD); sh = tr.select(PLAN.s0, PLAN.l0); lv = tr.select(PLAN.l0, PLAN.total)
        return sh.net * 1e4, lv.net * 1e4, lv.exit_day
    def path(x, mu0, sd, k):
        s = 0.0; out = np.empty(len(x))
        for i, v in enumerate(x): s = max(0.0, s + (mu0 - v) / sd - k); out[i] = s
        return out
    def first(p, h):
        i = np.flatnonzero(p > h); return int(i[0]) if len(i) else None
    DET = {"1 shadow ref, k=0.10 (book)": ("shadow", 0.10), "2 break-even ref, k=0.10 (book)": ("zero", 0.10), "3 break-even ref, k=0.065": ("zero", 0.065), "4 shadow ref, k=0.17": ("shadow", 0.17)}
    def load(seeds, shift): return [streams(s, shift) for s in seeds]
    cal = load(range(20000, 20000 + NC), -1); tp = load(range(21000, 21000 + NC), -1); td = load(range(21000, 21000 + NC), SHIFT); tick("K4 streams built")
    out = dict(n_cal=NC, n_test=NC, ref_sd_median=float(np.median([np.std(c[0], ddof=1) for c in cal])), ref_mean_median=float(np.median([np.mean(c[0]) for c in cal])), post_mean=float(np.mean([np.mean(c[1][c[2] >= SHIFT]) for c in td])), detectors={})
    for name, (ref, k) in DET.items():
        def paths(ws): return [path(lv, (np.mean(sh) if ref == "shadow" else 0.0), np.std(sh, ddof=1), k) for sh, lv, ex in ws]
        pc, pp, pd = paths(cal), paths(tp), paths(td)
        h = next((g for g in GRID if np.mean([first(p, g) is not None for p in pc]) <= 0.05), None)
        far_test = float(np.mean([first(p, h) is not None for p in pp])); hits = []; early = 0; dd = []; dt = []
        for p, (sh, lv, ex) in zip(pd, td):
            i = first(p, h)
            if i is None: continue
            if ex[i] < SHIFT: early += 1; continue
            hits.append(i); dd.append(int(ex[i] - SHIFT)); dt.append(int(i - int(np.searchsorted(ex, SHIFT))))
        out["detectors"][name] = dict(h=h, far_test=far_test, detected=len(hits) / NC, early_alarm=early / NC, delay_days_median=float(np.median(dd)) if dd else None, delay_trades_median=float(np.median(dt)) if dt else None, delay_days_p90=float(np.percentile(dd, 90)) if dd else None)
        tick(f"K4 {name}: {out['detectors'][name]}")
    R["K4"] = out; save()

for k in ONLY: dict(K1=k1, K2=k2, K3=k3, K4=k4)[k]()
tick("done")
