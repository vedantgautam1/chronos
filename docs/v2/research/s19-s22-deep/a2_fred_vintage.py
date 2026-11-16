"""A2: can OpenBB return a FRED series as it was known on a past date?

Run in a venv with openbb-core + openbb-fred (repo commit), from outside the repo:
    python -I a2_fred_vintage.py results.json

No network: OpenBB's `fred_get` is replaced by a fake that answers like FRED's
observations endpoint, with ALFRED-style vintages:
  observation 2020-01-01: first released 2020-02-01 as 100.0, revised 2020-03-01 to 105.0
  observation 2020-04-01: first released 2020-05-01 as 110.0 (never revised)
FRED semantics emulated: without realtime_* parameters the value as of "today" is
returned; with realtime_start == realtime_end == D, the value as known on D; with a
range, one row per (date, vintage) inside the range, ordered by realtime_start.
"""
import asyncio
import json
import sys
from urllib.parse import parse_qs, urlparse

import openbb_fred.utils.rate_limiter as rl
from openbb_fred.models.series import FredSeriesFetcher

VINTAGES = [  # (date, realtime_start, realtime_end, value)
    ("2020-01-01", "2020-02-01", "2020-02-29", "100.0"),
    ("2020-01-01", "2020-03-01", "9999-12-31", "105.0"),
    ("2020-04-01", "2020-05-01", "9999-12-31", "110.0"),
]
SEEN_URLS = []


async def fake_fred_get(url, **kwargs):
    SEEN_URLS.append(url)
    u = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    if u.path.endswith("/series"):
        return {"seriess": [{"title": "Fake GDP", "units": "Bil", "frequency": "Q"}]}
    rs, re_ = q.get("realtime_start"), q.get("realtime_end")
    if rs is None and re_ is None:
        rs = re_ = "2026-11-05"  # FRED default: today
    rs = rs or "1776-07-04"
    re_ = re_ or "9999-12-31"
    obs = []
    for d, vs, ve, val in VINTAGES:
        if vs <= re_ and ve >= rs:  # vintage overlaps the requested real-time window
            obs.append({"realtime_start": max(vs, rs), "realtime_end": min(ve, re_), "date": d, "value": val})
    return {"observations": obs}


def fetch(params):
    rl.fred_get = fake_fred_get
    return asyncio.run(FredSeriesFetcher.fetch_data(params, {"fred_api_key": "dummy"}))


def values(result):
    rows = result.result if hasattr(result, "result") else result
    return {str(r.date): getattr(r, "FAKE") for r in rows}


def main():
    out = {}
    cases = {
        "default (no vintage asked)": {"symbol": "FAKE"},
        "documented fields only, as of 2020-02-15": {"symbol": "FAKE", "start_date": "2020-01-01", "end_date": "2020-12-31"},
        "undocumented extra params realtime_start=realtime_end=2020-02-15": {"symbol": "FAKE", "realtime_start": "2020-02-15", "realtime_end": "2020-02-15"},
        "undocumented extra params, a range 2020-02-01..2020-03-31": {"symbol": "FAKE", "realtime_start": "2020-02-01", "realtime_end": "2020-03-31"},
    }
    for name, params in cases.items():
        SEEN_URLS.clear()
        try:
            v = values(fetch(params))
        except Exception as e:  # report, don't hide
            v = f"error: {type(e).__name__}: {e}"
        obs_urls = [u.split("?", 1)[1].replace("api_key=dummy", "api_key=…") for u in SEEN_URLS if "observations" in u]
        out[name] = {"values": v, "request": obs_urls}
        print(name, "->", v, "| request:", obs_urls)
    # Rule: PASS if some supported parameter returns the as-of-2020-02-15 value (100.0) for 2020-01-01.
    documented = out["documented fields only, as of 2020-02-15"]["values"]
    undoc = out["undocumented extra params realtime_start=realtime_end=2020-02-15"]["values"]
    out["verdict"] = {
        "documented_route_returns_vintage": isinstance(documented, dict) and documented.get("2020-01-01") == 100.0,
        "undocumented_extra_params_return_vintage": isinstance(undoc, dict) and undoc.get("2020-01-01") == 100.0,
    }
    with open(sys.argv[1], "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(out["verdict"])


if __name__ == "__main__":
    main()
