"""K0: compare the author's shipped results JSON with a rerun at the same settings. Usage: python -I compare_k0.py author.json rerun.json"""
import json, math, sys
A, B = (json.load(open(p)) for p in sys.argv[1:3])
diffs = []; n = [0]
SKIP = ("secs", "seconds", "time", "elapsed", "runtime", "wall")
def walk(a, b, path):
    if any(s in path.lower() for s in SKIP): return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if k not in a or k not in b: diffs.append((path + "/" + str(k), "missing in " + ("author" if k not in a else "rerun"))); continue
            walk(a[k], b[k], path + "/" + str(k))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): diffs.append((path, f"length {len(a)} vs {len(b)}")); return
        for i, (x, y) in enumerate(zip(a, b)): walk(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        n[0] += 1
        if not (a == b or (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))): diffs.append((path, f"{a} vs {b}"))
    else:
        n[0] += 1
        if a != b: diffs.append((path, f"{str(a)[:60]} vs {str(b)[:60]}"))
walk(A, B, "")
print(f"compared {n[0]} values; {len(diffs)} differ")
for p, d in diffs[:40]: print("  ", p, d)
