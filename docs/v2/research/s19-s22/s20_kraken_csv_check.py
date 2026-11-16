"""S20 check F1: does freqtrade's Kraken trade-CSV importer keep every trade?

Usage (inside a venv with freqtrade installed, from outside the freqtrade folder):
    python -I s20_kraken_csv_check.py results.json

Builds synthetic Kraken-format trade CSVs (timestamp,price,amount; no header),
runs freqtrade's own import_kraken_trades_from_csv with the exchange object
stubbed (only `.markets` is read, so no network), reads the stored trades back
with freqtrade's data handler, and compares counts and volume with the input.
Rules: PREREGISTERED.md (F1). The sub-millisecond variant (c) is exploratory,
added after pre-registration, and reported separately.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np

from freqtrade.data.converter import trade_converter_kraken as tck
from freqtrade.data.history import get_datahandler
from freqtrade.enums import TradingMode

N = 1000
SEED = 20261105


def make_trades(variant: str, rng):
    """Return list of (timestamp_seconds, price, amount) with known shared-timestamp groups."""
    base = 1_700_000_000.0
    rows = []
    t = base
    shared = 0
    while len(rows) < N:
        t += rng.integers(1, 5)  # strictly increasing distinct times between groups
        if variant == "b_fractional":
            ts = round(t + rng.random(), 6)  # microsecond resolution, like Kraken's API
        else:
            ts = float(int(t))  # whole seconds
        group = int(rng.choice([1, 1, 1, 2, 3, 4]))  # one taker filling 1-4 resting orders
        group = min(group, N - len(rows))
        price = 30000 + rng.normal(0, 50)
        for g in range(group):
            amt = round(float(rng.uniform(0.001, 0.5)), 8)
            if variant == "c_submillisecond" and g > 0:
                # distinct timestamps less than 1 ms apart (exploratory)
                rows.append((round(ts + g * 0.0003, 6), round(price + g * 0.1, 1), amt))
            else:
                rows.append((ts, round(price + g * 0.1, 1), amt))
        if group > 1:
            shared += group - 1
    return rows, shared


def run_variant(variant: str):
    rng = np.random.default_rng(SEED)
    rows, extra_same_time = make_trades(variant, rng)
    tmp = Path(tempfile.mkdtemp(prefix=f"s20_{variant}_"))
    csvdir = tmp / "trades_csv" / "Kraken_full_history"
    csvdir.mkdir(parents=True)
    with open(csvdir / "XBTUSD.csv", "w") as f:
        for ts, p, a in rows:
            f.write(f"{ts},{p},{a}\n")

    class StubExchange:
        markets = {"BTC/USD": {"symbol": "BTC/USD", "altname": "XBTUSD"}}

    config = {"exchange": {"name": "kraken"}, "datadir": tmp, "pairs": None}
    with mock.patch.object(tck.ExchangeResolver, "load_exchange", return_value=StubExchange()):
        tck.import_kraken_trades_from_csv(config, convert_to="feather")

    handler = get_datahandler(tmp, data_format="feather")
    stored = handler.trades_load("BTC/USD", TradingMode.SPOT)
    vol_in = float(sum(a for _, _, a in rows))
    vol_out = float(stored["amount"].sum())
    return {
        "variant": variant,
        "trades_in": len(rows),
        "trades_sharing_a_timestamp_with_an_earlier_trade": extra_same_time,
        "trades_out": int(len(stored)),
        "trades_lost": len(rows) - int(len(stored)),
        "volume_in": vol_in,
        "volume_out": vol_out,
        "volume_lost_pct": 100 * (vol_in - vol_out) / vol_in,
        "pass": len(stored) == len(rows) and abs(vol_out - vol_in) <= 1e-9 * vol_in,
    }


def main():
    out = sys.argv[1]
    res = [run_variant(v) for v in ("a_whole_seconds", "b_fractional", "c_submillisecond")]
    verdict = {"F1": all(r["pass"] for r in res[:2])}  # (c) is exploratory, not in the rule
    with open(out, "w") as f:
        json.dump({"results": res, "verdict": verdict}, f, indent=2)
    for r in res:
        print(r)
    print(verdict)


if __name__ == "__main__":
    main()
