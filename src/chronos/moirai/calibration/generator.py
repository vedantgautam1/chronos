"""generator.py — the synthetic-candle generator (spec §7.2, M-c; the fixture door).

Produces Oceanus-VALID H1 OHLCV frames carrying a KNOWN injected effect: the annualized
Sharpe of the frame's log returns equals a target `S`. This is the raw material of
calibration — feed the gauntlet data whose true edge we set, and measure what fraction it
passes (the power curve; at S=0, the false-positive rate).

Construction (spec §7.2):
  - Geometric price path: log returns drawn i.i.d. Normal(μ, σ_bar²), close =
    base · exp(cumsum(log returns)). Volatility σ = `ann_vol` (default 0.60, the measured
    project figure `calib.ann_vol`), per bar σ_bar = σ / √(bars per year).
  - Drift μ set so the ANNUALIZED Sharpe of log returns equals the target S:
    annualized Sharpe = (μ / σ_bar)·√(bpy), so μ = σ_bar · S / √(bpy) = ann_vol · S / bpy.
  - OHLC by a seeded intra-bar bridge: open = previous close; high/low extend beyond
    max/min(open, close) by half-normal wicks scaled to σ_bar. Guarantees Oceanus
    validity — low ≤ open,close ≤ high, all prices positive, no OHLC violation.
  - Volume from the EMPIRICAL BTC/USDT H1 distribution: log-volume ~ Normal(m, s) with
    (m, s) MEASURED from the real 78,440 positive-volume bars (see below).

Versioning & provenance: `GENERATOR_VERSION` enters every calibration report and stamps
`data_provenance: synthetic:<version>` (via `provenance()`) onto every synthetic run the
harness records — so a synthetic result can never be mistaken for a real one, and a
generator change invalidates the calibration report (§7.6).

Determinism (I10-adjacent): every draw comes from one seeded `np.random.default_rng(seed)`.
Same seed, same frame — byte-for-byte.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from chronos.oceanus.model import BAR_COLUMNS, Timeframe

GENERATOR_VERSION = "v1"

HOURS_PER_YEAR = 8760.0
DEFAULT_ANN_VOL = 0.60  # calib.ann_vol — the measured project volatility figure

# Empirical BTC/USDT H1 volume ≈ lognormal. MEASURED 2026-08-04 from the 78,440
# positive-volume bars of the canonical window (2017-08-17 → 2026-08-03, Oceanus snapshot
# 7c0b19aa…551c2; see SESSION_FINDINGS 2026-08-04). Committed as versioned constants so
# the generator is self-contained (it never reads data/ at runtime — I7) and reproducible.
_LOG_VOLUME_MEAN = 7.188979
_LOG_VOLUME_STD = 1.169015

_BASE_PRICE = 10_000.0  # arbitrary positive start; scale-invariant for returns/Sharpe
_DEFAULT_START = datetime(2020, 1, 1, tzinfo=timezone.utc)


def provenance() -> str:
    """The stamp marking data as synthetic and pinning the generator version."""
    return f"synthetic:{GENERATOR_VERSION}"


def generate_frame(
    *,
    target_sharpe: float,
    n_bars: int,
    seed: int,
    ann_vol: float = DEFAULT_ANN_VOL,
    start: datetime | None = None,
    timeframe: Timeframe = Timeframe.H1,
) -> pd.DataFrame:
    """An Oceanus-valid OHLCV frame of `n_bars` whose log-return annualized Sharpe is
    `target_sharpe` in expectation, at volatility `ann_vol`. Deterministic in `seed`."""
    if n_bars < 2:
        raise ValueError(f"n_bars must be >= 2, got {n_bars}")
    if ann_vol <= 0:
        raise ValueError(f"ann_vol must be > 0, got {ann_vol}")
    start = start or _DEFAULT_START
    rng = np.random.default_rng(seed)

    bpy = HOURS_PER_YEAR  # H1 bars per year
    sigma_bar = ann_vol / np.sqrt(bpy)
    mu = ann_vol * target_sharpe / bpy  # = sigma_bar · S / √bpy → ann Sharpe == S

    log_ret = rng.normal(mu, sigma_bar, n_bars)
    close = _BASE_PRICE * np.exp(np.cumsum(log_ret))
    open_ = np.empty(n_bars)
    open_[0] = _BASE_PRICE
    open_[1:] = close[:-1]

    top = np.maximum(open_, close)
    bot = np.minimum(open_, close)
    up_wick = np.abs(rng.normal(0.0, sigma_bar, n_bars))
    dn_wick = np.abs(rng.normal(0.0, sigma_bar, n_bars))
    high = top * (1.0 + up_wick)
    low = bot * (1.0 - dn_wick)  # dn_wick ~ σ_bar ≪ 1, so low stays strictly positive

    volume = rng.lognormal(_LOG_VOLUME_MEAN, _LOG_VOLUME_STD, n_bars)
    times = pd.date_range(start=start, periods=n_bars,
                          freq=pd.Timedelta(timeframe.duration))  # vectorized, tz-aware UTC

    frame = pd.DataFrame(
        {
            "open_time": times,
            "open": open_, "high": high, "low": low, "close": close,
            "volume": volume, "is_final": True,
        },
        columns=BAR_COLUMNS,
    )
    return frame


def realized_annualized_sharpe(frame: pd.DataFrame) -> float:
    """The annualized Sharpe of a frame's realized log returns — the quantity the
    generator sets to `target_sharpe`. Used by the known-answer self-test."""
    close = frame["close"].astype(float).to_numpy()
    log_ret = np.diff(np.log(close))
    sd = log_ret.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(log_ret.mean() / sd * np.sqrt(HOURS_PER_YEAR))
