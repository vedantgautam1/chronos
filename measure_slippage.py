"""R6 measurement: estimate real BTC/USDT market-buy slippage from Binance
aggTrades, streamed directly out of each month's ZIP — never extracted to
disk (extracting these has crashed this machine before; each ZIP's CSV is
read via zipfile + pd.read_csv on the in-memory stream, then discarded).

For every hourly bar we simulate a market BUY of a fixed USDT notional:
walk the hour's taker-buy trades (is_buyer_maker == False — these are the
ones that hit the ask, which is what a market buy actually matches against)
in chronological order, accumulate notional until it reaches the target,
and take the volume-weighted average price of the trades consumed. Slippage
is that VWAP vs. the hour's first traded price, in bps. Run twice — 9,000
USDT and 90,000 USDT — to see how slippage scales with order size.

Run:  uv run python measure_slippage.py
"""

import gc
import re
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data" / "aggtrades"
ZIP_PATTERN = re.compile(r"BTCUSDT-aggTrades-(\d{4})-(\d{2})\.zip$")

# Column order per these Binance aggTrades dumps — verified against the
# actual files (2026-07-18): 8 fields, not the 7 in Binance's older public
# schema docs; the trailing field is an is_best_match flag we don't use.
# We only need four of the eight for this measurement; usecols skips
# parsing the rest, which matters here given the file sizes involved.
COLUMNS = [
    "agg_trade_id", "price", "quantity", "first_trade_id",
    "last_trade_id", "timestamp", "is_buyer_maker", "is_best_match",
]
USECOLS = [1, 2, 5, 6]  # price, quantity, timestamp, is_buyer_maker

# Verified against the actual files (2026-07-18): timestamp is unix
# MICROSECONDS, not milliseconds as Binance's public docs state for older
# dumps — 1767225600039409 us == 2026-01-01 00:00:00.039409 UTC, matching
# the filename exactly; interpreted as ms it lands in the year 57971.
MICROSECONDS_PER_HOUR = 3_600 * 1_000_000

ORDER_SIZES_USDT = {"9k": 9_000.0, "90k": 90_000.0}


def find_monthly_zips() -> list[tuple[int, int, Path]]:
    found = []
    for path in DATA_DIR.glob("BTCUSDT-aggTrades-*.zip"):
        match = ZIP_PATTERN.search(path.name)
        if not match:
            continue
        year, month = int(match.group(1)), int(match.group(2))
        found.append((year, month, path))
    found.sort(key=lambda t: (t[0], t[1]))
    return found


def load_month(path: Path) -> pd.DataFrame:
    """Stream the one CSV inside `path`'s ZIP straight into a DataFrame.
    Nothing touches disk beyond the ZIP itself."""
    with zipfile.ZipFile(path) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"{path.name}: expected exactly one CSV inside, found {csv_names}")
        with zf.open(csv_names[0]) as f:
            # Some Binance monthly dumps carry a header row, some don't —
            # sniff the first line rather than assume.
            first_line = f.readline()
            skiprows = 1 if first_line.lstrip().startswith(b"agg_trade_id") else 0
            f.seek(0)
            df = pd.read_csv(
                f, header=None, names=COLUMNS, usecols=USECOLS,
                skiprows=skiprows,
            )

    if df["is_buyer_maker"].dtype != bool:
        df["is_buyer_maker"] = (
            df["is_buyer_maker"].astype(str).str.strip().str.lower() == "true"
        )
    return df


def measure_month(df: pd.DataFrame) -> dict:
    """Return per-hour slippage (bps) for both order sizes, plus bar/
    insufficient-liquidity counts. Trusts Binance's dumps to already be
    chronological (agg_trade_id order == time order) — no re-sort."""
    df["hour"] = df["timestamp"] // MICROSECONDS_PER_HOUR

    slippage = {size: [] for size in ORDER_SIZES_USDT}
    insufficient = {size: 0 for size in ORDER_SIZES_USDT}
    n_bars = 0

    for _, group in df.groupby("hour", sort=True):
        n_bars += 1
        first_price = group["price"].iat[0]

        takers = group.loc[~group["is_buyer_maker"], ["price", "quantity"]]
        if takers.empty:
            for size in ORDER_SIZES_USDT:
                insufficient[size] += 1
            continue

        prices = takers["price"].to_numpy()
        quantities = takers["quantity"].to_numpy()
        cum_notional = np.cumsum(prices * quantities)

        for size, target in ORDER_SIZES_USDT.items():
            idx = int(np.searchsorted(cum_notional, target))
            if idx >= len(prices):
                insufficient[size] += 1
                continue
            consumed_qty = quantities[: idx + 1]
            consumed_notional = prices[: idx + 1] * consumed_qty
            vwap = consumed_notional.sum() / consumed_qty.sum()
            slippage[size].append((vwap - first_price) / first_price * 10_000)

    return {"n_bars": n_bars, "slippage": slippage, "insufficient": insufficient}


def summarize(arr: np.ndarray) -> dict:
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "p5": float(np.percentile(arr, 5)),
        "p95": float(np.percentile(arr, 95)),
        "std": float(np.std(arr, ddof=1)),
    }


def main() -> None:
    months = find_monthly_zips()
    if not months:
        raise SystemExit(f"No BTCUSDT-aggTrades-YYYY-MM.zip files found under {DATA_DIR}")

    all_slippage = {size: [] for size in ORDER_SIZES_USDT}
    total_insufficient = {size: 0 for size in ORDER_SIZES_USDT}
    total_bars = 0

    print(f"Found {len(months)} monthly ZIP(s) under {DATA_DIR}\n")

    for year, month, path in months:
        df = load_month(path)
        result = measure_month(df)

        total_bars += result["n_bars"]
        for size in ORDER_SIZES_USDT:
            all_slippage[size].extend(result["slippage"][size])
            total_insufficient[size] += result["insufficient"][size]

        label = datetime(year, month, 1).strftime("%b %Y")
        insuff_parts = ", ".join(
            f"{size} insufficient: {result['insufficient'][size]}" for size in ORDER_SIZES_USDT
        )
        print(f"{label}: {result['n_bars']} bars, {insuff_parts}")

        del df, result
        gc.collect()

    print()
    print(f"Total bars measured: {total_bars}")
    for size in ORDER_SIZES_USDT:
        print(f"  {size} order — insufficient liquidity: {total_insufficient[size]} bars")

    stats = {}
    for size in ORDER_SIZES_USDT:
        arr = np.array(all_slippage[size])
        stats[size] = summarize(arr)
        np.save(DATA_DIR / f"measured_slippage_{size}_bps.npy", arr)

    print()
    print(f"{'':10s}{'9k order':>16s}{'90k order':>16s}")
    for stat_name in ("mean", "median", "p5", "p95", "std"):
        row = f"{stat_name:10s}"
        for size in ORDER_SIZES_USDT:
            row += f"{stats[size][stat_name]:15.3f}bps"
        print(row)

    year0, month0, _ = months[0]
    year1, month1, _ = months[-1]
    date_range = (
        f"{datetime(year0, month0, 1):%b %Y}"
        if (year0, month0) == (year1, month1)
        else f"{datetime(year0, month0, 1):%b %Y} - {datetime(year1, month1, 1):%b %Y}"
    )

    print()
    print(
        f"R6 MEASURED: BTC/USDT spot, {date_range}, {total_bars} bars, "
        f"9k order: mean={stats['9k']['mean']:.2f}bps "
        f"median={stats['9k']['median']:.2f}bps p95={stats['9k']['p95']:.2f}bps. "
        f"90k order: mean={stats['90k']['mean']:.2f}bps "
        f"median={stats['90k']['median']:.2f}bps p95={stats['90k']['p95']:.2f}bps."
    )


if __name__ == "__main__":
    main()
