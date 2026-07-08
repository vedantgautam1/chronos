"""See Oceanus working: pull real data through the ONE door and eyeball it.

Run:  uv run python scripts/see_data.py

This fetches real Bitcoin daily bars via get_bars() (the only data door),
prints a plain summary and the validation report, then draws a candlestick
chart with volume and saves it as a PNG you can open. It reads NOTHING
directly — no ccxt, no Parquet files — exactly like every future part of
Chronos will have to.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw straight to a file; no popup window needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from chronos.oceanus.access import get_bars
from chronos.oceanus.model import Timeframe
from chronos.oceanus.validate import validate

DAYS = 120


def main() -> None:
    end = datetime.now(timezone.utc) + timedelta(days=1)  # include today on purpose
    start = end - timedelta(days=DAYS)

    print(f"Asking the one door for {DAYS} days of BTC/USDT daily bars...\n")
    bars = get_bars("BTC/USDT", Timeframe.D1, start, end)

    # --- the plain-English summary ---
    first, last = bars.iloc[0], bars.iloc[-1]
    print(f"  got {len(bars)} completed daily bars")
    print(f"  from {first['open_time']:%Y-%m-%d} to {last['open_time']:%Y-%m-%d}")
    print(f"  first close: ${first['close']:,.0f}   last close: ${last['close']:,.0f}")
    print(f"  today's still-forming bar is absent (the door never serves it)\n")

    print(validate(bars, Timeframe.D1))  # should be clean

    # --- the picture ---
    out = Path(__file__).resolve().parents[1] / "oceanus_preview.png"
    _draw_candles(bars, out)
    print(f"\nChart saved to {out}")
    print("Open it with:  open " + str(out))


def _draw_candles(bars, out_path: Path) -> None:
    fig, (price_ax, vol_ax) = plt.subplots(
        2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    for row in bars.itertuples(index=False):
        day = mdates.date2num(row.open_time)
        rising = row.close >= row.open
        color = "#26a269" if rising else "#c01c28"  # green up, red down
        # thin line = the day's high-to-low range
        price_ax.plot([day, day], [row.low, row.high], color=color, linewidth=0.8)
        # fat bar = open-to-close body
        price_ax.plot([day, day], [row.open, row.close], color=color, linewidth=4)
        vol_ax.bar(day, row.volume, color=color, width=0.7)

    price_ax.set_title("BTC/USDT daily — fetched through Oceanus get_bars()")
    price_ax.set_ylabel("price (USDT)")
    price_ax.grid(True, alpha=0.2)
    vol_ax.set_ylabel("volume")
    vol_ax.grid(True, alpha=0.2)
    vol_ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=110)


if __name__ == "__main__":
    main()
