"""Phase 2 — fetch OHLCV history from the exchange via ccxt.

The exchange hands out history in limited chunks (Binance: max 1000 bars
per request), so fetch_bars() PAGINATES: it asks for a chunk, advances
its "since" pointer past the last bar received, and repeats until the
requested range is covered. Think of photocopying a book that the
library only lends out 1000 pages at a time.

Exchange choice (recorded in HANDOFF.md): Binance — deepest free history
for liquid pairs, 1000 bars/page, best ccxt support. Swappable: anything
with a ccxt-compatible fetch_ohlcv works via the `exchange` argument.

Verified against installed ccxt 4.5.64:
  fetch_ohlcv(symbol, timeframe, since, limit, params) -> list of
  [timestamp_ms, open, high, low, close, volume]; `since` is in
  milliseconds UTC; rate limiting is enabled by default in ccxt v4.
"""

import time
from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd

from chronos.oceanus.model import BAR_COLUMNS, Timeframe

# How many bars to ask for per request (Binance allows up to 1000).
PAGE_LIMIT = 1000

# Transient network problems worth retrying; anything else fails loudly.
RETRYABLE = (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout)
MAX_RETRIES = 5


def make_exchange() -> ccxt.Exchange:
    """Create the exchange client Oceanus fetches from."""
    return ccxt.binance()  # public data only; no API key needed


def fetch_bars(
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    exchange: ccxt.Exchange | None = None,
) -> pd.DataFrame:
    """Fetch all bars whose open_time is in [start, end) — start included,
    end excluded, so adjacent ranges never overlap.

    Returns a DataFrame with BAR_COLUMNS, sorted by open_time, no
    duplicates, timestamps tz-aware UTC. The still-forming bar (if the
    range reaches the present) is marked is_final=False.
    """
    _require_utc(start, "start")
    _require_utc(end, "end")
    if start >= end:
        raise ValueError(f"start ({start}) must be before end ({end})")
    if exchange is None:
        exchange = make_exchange()

    tf_ms = int(timeframe.duration.total_seconds() * 1000)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    rows: list[list] = []
    since = start_ms
    while since < end_ms:
        batch = _fetch_page_with_retry(exchange, symbol, timeframe.value, since)
        if not batch:
            break  # no data at/after `since` (e.g. before the pair existed)
        rows.extend(batch)
        last_ts = batch[-1][0]
        if last_ts < since:
            break  # exchange made no forward progress; avoid looping forever
        since = last_ts + tf_ms  # next page starts after the last bar we got

    frame = pd.DataFrame(rows, columns=["ts_ms", "open", "high", "low", "close", "volume"])

    # Keep only the requested [start, end) window — the exchange may have
    # returned a little extra on either side.
    frame = frame[(frame["ts_ms"] >= start_ms) & (frame["ts_ms"] < end_ms)]

    # Sort and drop duplicate timestamps (idempotency: same range in,
    # same rows out, no matter how the pages happened to overlap).
    frame = frame.sort_values("ts_ms").drop_duplicates(subset="ts_ms", keep="first")

    frame["open_time"] = pd.to_datetime(frame["ts_ms"], unit="ms", utc=True)

    # A bar is final only if its whole window has passed: a 12:00 hourly
    # bar isn't final until 13:00 UTC. The bar still forming right now
    # must never be treated as complete. "Now" comes from the EXCHANGE's
    # own clock, not this machine's — a laptop with a wrong clock could
    # otherwise mislabel the newest bars and leak the future.
    now_ms = _reference_now_ms(exchange)
    frame["is_final"] = (frame["ts_ms"] + tf_ms) <= now_ms

    return frame[BAR_COLUMNS].reset_index(drop=True)


def _fetch_page_with_retry(
    exchange: ccxt.Exchange, symbol: str, timeframe: str, since_ms: int
) -> list[list]:
    """One page of OHLCV, retrying transient network errors with backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            return exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=PAGE_LIMIT)
        except RETRYABLE as error:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2**attempt  # 1s, 2s, 4s, 8s
            print(f"  transient error ({error!r}), retrying in {wait}s...")
            time.sleep(wait)
    raise AssertionError("unreachable")


def _reference_now_ms(exchange: ccxt.Exchange) -> int:
    """Current UTC time in milliseconds, taken from the exchange's own
    clock so our is_final decision doesn't depend on this machine's clock.

    If the exchange can't report its time (e.g. offline, or a test double
    without the method), fall back to the local clock and say so out loud
    rather than failing — a degraded but honest mode.
    """
    try:
        return int(exchange.fetch_time())
    except Exception as error:  # AttributeError, network errors, etc.
        print(f"  [ingest] exchange time unavailable ({error!r}); using local clock")
        return int(datetime.now(timezone.utc).timestamp() * 1000)


def _require_utc(moment: datetime, name: str) -> None:
    if moment.tzinfo is None:
        raise ValueError(f"{name} is naive (no timezone): {moment}")
    if moment.utcoffset() != timedelta(0):
        raise ValueError(f"{name} is not UTC: {moment}")
