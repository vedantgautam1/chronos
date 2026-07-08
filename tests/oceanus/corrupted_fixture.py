"""A deliberately corrupted table of bars, used by Phases 4, 5, and 7.

Starts from 24 perfectly good hourly bars, then plants one of each
problem class. Each plant is listed in PLANTED so tests can assert that
validation catches every single one.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from chronos.oceanus.model import BAR_COLUMNS

START = datetime(2026, 1, 1, tzinfo=timezone.utc)

# What we plant -> the Issue.kind that validate() must report it as.
PLANTED = {
    "gap": "hour 5 deleted (bars jump from 04:00 to 06:00)",
    "duplicate": "hour 8 appears twice",
    "out_of_order": "hours 14 and 15 swapped",
    "ohlc": "hour 10 has high < low",
    "impossible_value": "hour 12 has negative volume",
    "naive_timestamp": "hour 20 lost its timezone",
    "outlier": "hour 18 close jumps 50% vs hour 17",
}


def make_corrupted_frame() -> pd.DataFrame:
    rows = []
    for i in range(24):
        price = 100.0 + i
        rows.append(
            {
                "open_time": pd.Timestamp(START + timedelta(hours=i)),
                "open": price,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price + 0.5,
                "volume": 10.0,
                "is_final": True,
            }
        )

    del rows[5]  # GAP: hour 5 is simply missing now

    dup = dict(rows[7])  # after the delete, index 7 is hour 8
    rows.insert(8, dup)  # DUPLICATE: hour 8 twice in a row

    hour = {r["open_time"].hour: idx for idx, r in enumerate(rows)}
    rows[hour[14]], rows[hour[15]] = rows[hour[15]], rows[hour[14]]  # OUT OF ORDER

    rows[hour[10]]["high"], rows[hour[10]]["low"] = rows[hour[10]]["low"], rows[hour[10]]["high"]  # OHLC: high < low
    rows[hour[12]]["volume"] = -5.0  # IMPOSSIBLE VALUE

    naive = rows[hour[20]]["open_time"].tz_localize(None)  # NAIVE TIMESTAMP
    rows[hour[20]]["open_time"] = naive

    big = rows[hour[18]]  # OUTLIER: 50% jump
    big["close"] = big["open"] * 1.5
    big["high"] = big["close"] + 1.0

    frame = pd.DataFrame(rows, columns=BAR_COLUMNS)
    # open_time now mixes aware and naive values, so it must be a plain
    # "object" column — exactly the kind of mess validation must survive.
    return frame
