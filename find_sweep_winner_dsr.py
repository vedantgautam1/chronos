"""Find the best (fast, slow) cell in the 280-point sweep and compute its
DSR under two different N assumptions: as if it were a single
pre-registered hypothesis (N~1) vs. honestly, as a search of 280 (N=280).

Re-derives (fast, slow, sharpe, T) directly from records/runs.jsonl per
trial — rather than trusting positional alignment with sweep_sharpes.npy —
so the winning cell's params are unambiguous. Cross-checks against
sweep_sharpes.npy as a sanity check only.
"""

import json
from pathlib import Path

import numpy as np

from chronos_math_probe import dsr

RECORDS_FILE = Path(__file__).resolve().parent / "records" / "runs.jsonl"
SHARPES_FILE = Path(__file__).resolve().parent / "sweep_sharpes.npy"

LO, HI = 5, 284


def main() -> None:
    with open(RECORDS_FILE) as f:
        lines = [json.loads(line) for line in f]

    selected = [
        r for r in lines
        if r["type"] == "run"
        and r.get("status") == "COMPLETED"
        and LO <= r.get("trial_index", -1) <= HI
    ]

    cells = []  # (trial_index, fast, slow, sharpe, T)
    for r in selected:
        params = r["config"]["strategy_params"]
        pairs = r["result"]["returns"]
        values = np.array([v for _ts, v in pairs], dtype=float)
        T = values.size
        mean = values.mean()
        std = values.std(ddof=1)
        sharpe = mean / std
        cells.append((r["trial_index"], params["fast"], params["slow"], sharpe, T))

    # Sanity check against the previously saved array (same order as this
    # extraction, since both iterate records/runs.jsonl in file order).
    if SHARPES_FILE.exists():
        saved = np.load(SHARPES_FILE)
        recomputed = np.array([c[3] for c in cells])
        if saved.shape == recomputed.shape and np.allclose(saved, recomputed, equal_nan=True):
            print(f"[sanity check] recomputed Sharpes match {SHARPES_FILE.name} exactly\n")
        else:
            print(f"[sanity check] WARNING: recomputed Sharpes do NOT match {SHARPES_FILE.name}\n")

    # Winning cell: highest per-bar Sharpe among the 280.
    trial_index, fast, slow, sharpe, T = max(cells, key=lambda c: c[3])

    print(f"Winning combination : fast={fast}, slow={slow}  (trial_index={trial_index})")
    print(f"Sharpe               : {sharpe}")
    print(f"T                    : {T}")
    print()

    dsr_naive = dsr(sharpe, T=T, V=1e-4, N=1.0001)
    dsr_honest = dsr(sharpe, T=T, V=8.659587301602424e-05, N=280)

    print(f"{'':20} {'N=1.0001, V=1e-4':>22} {'N=280, V=8.6596e-05':>22}")
    print(f"{'DSR':<20} {dsr_naive:>22.6f} {dsr_honest:>22.6f}")


if __name__ == "__main__":
    main()
