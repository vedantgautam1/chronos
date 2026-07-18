"""Ad-hoc analysis: summary stats, per-bar Sharpe, and (if available) DSR
for the trial-4 milestone returns.

NOTE — this is a scratch calculation, NOT the trusted Moirai. Per
HEPHAESTUS_SPEC §10 the engine is a witness, not a judge: real Sharpe/DSR
validation belongs in the quant's reviewed component, with annualization
(R3) and the true trial count fed from the Mnemosyne counter (I6). Read
the caveats this script prints before trusting any number it produces.
"""

import json
from pathlib import Path

import numpy as np

RETURNS_FILE = Path(__file__).resolve().parent / "records" / "trial4_returns.json"


def main() -> None:
    # (1) read the returns file
    pairs = json.loads(RETURNS_FILE.read_text())

    # (2) strip timestamps, keep the numeric values in order
    values = np.array([v for _ts, v in pairs], dtype=float)

    # (3) count / mean / std (sample std, ddof=1)
    count = values.size
    mean = values.mean()
    std = values.std(ddof=1)
    print(f"count            : {count}")
    print(f"mean             : {mean:.10g}")
    print(f"std (ddof=1)     : {std:.10g}")

    # (4) raw per-bar Sharpe = mean / std
    sharpe = mean / std
    print(f"sharpe (mean/std): {sharpe:.10g}")

    # (5) + (6) DSR — needs chronos_math_probe.dsr
    try:
        from chronos_math_probe import dsr
    except ModuleNotFoundError:
        print()
        print("DSR               : NOT COMPUTED")
        print("  chronos_math_probe.py was not found on the import path.")
        print("  Provide its location and I'll wire in steps 5-6.")
        return

    dsr_value = dsr(sharpe, T=count, V=1e-4, N=1.0001)
    print()
    print(f"DSR (deflated Sharpe): {dsr_value}")


if __name__ == "__main__":
    main()
