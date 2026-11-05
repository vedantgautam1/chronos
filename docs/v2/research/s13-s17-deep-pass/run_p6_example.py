"""The author's p6_experiments.py ends with `import p6_example`, which fails under python -I (the script folder is not on sys.path). This wrapper runs that last step the same way."""
import json, os, sys, time
ROOT = sys.argv[1]; sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
OUTP = os.path.join(ROOT, "figs", "results_p6.json"); R = json.load(open(OUTP)); T0 = time.time()
def save(): json.dump(R, open(OUTP, "w"), indent=1, default=float)
def tick(s): print(s, f"{time.time()-T0:.0f}s", flush=True)
import p6_example
p6_example.run(R, save, tick, R["monitor"]); print("done")
