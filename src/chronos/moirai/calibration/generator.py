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

from datetime import datetime, timedelta, timezone

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
# Short id of the Oceanus snapshot the volume constants were measured from, pinned into
# provenance so every synthetic run traces to the data its realism came from.
_VOLUME_SNAPSHOT = "7c0b19aa"

_BASE_PRICE = 10_000.0  # arbitrary positive start; scale-invariant for returns/Sharpe
_DEFAULT_START = datetime(2020, 1, 1, tzinfo=timezone.utc)


def provenance() -> str:
    """The stamp marking data as synthetic, pinning BOTH the generator version and the
    Oceanus snapshot the volume realism was measured from (e.g. `synthetic:v1@7c0b19aa`)
    — so a synthetic run traces to the data whose empirical volume it borrows."""
    return f"synthetic:{GENERATOR_VERSION}@{_VOLUME_SNAPSHOT}"


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
    return _assemble_frame(log_ret, rng, start=start, timeframe=timeframe, wick_scale=sigma_bar)


def _assemble_frame(log_ret, rng, *, start, timeframe, wick_scale) -> pd.DataFrame:
    """Turn a per-bar log-return array into an Oceanus-valid OHLCV frame: geometric close
    path, open = previous close, seeded intra-bar wick bridge (half-normal, scale
    `wick_scale`), empirical-lognormal volume, tz-aware UTC index. Shared by the single-drift
    and regime generators so all validity logic lives in one place. Draw order (wicks, then
    volume) is fixed so a given rng state yields a byte-identical frame."""
    n_bars = log_ret.size
    close = _BASE_PRICE * np.exp(np.cumsum(log_ret))
    open_ = np.empty(n_bars)
    open_[0] = _BASE_PRICE
    open_[1:] = close[:-1]

    top = np.maximum(open_, close)
    bot = np.minimum(open_, close)
    up_wick = np.abs(rng.normal(0.0, wick_scale, n_bars))
    dn_wick = np.abs(rng.normal(0.0, wick_scale, n_bars))
    high = top * (1.0 + up_wick)
    low = bot * (1.0 - dn_wick)  # dn_wick ~ σ_bar ≪ 1, so low stays strictly positive

    volume = rng.lognormal(_LOG_VOLUME_MEAN, _LOG_VOLUME_STD, n_bars)
    times = pd.date_range(start=start, periods=n_bars,
                          freq=pd.Timedelta(timeframe.duration))  # vectorized, tz-aware UTC

    return pd.DataFrame(
        {
            "open_time": times,
            "open": open_, "high": high, "low": low, "close": close,
            "volume": volume, "is_final": True,
        },
        columns=BAR_COLUMNS,
    )


def regime_drift_schedule(n_bars, half_life_bars, bull_mu, bear_mu, rng) -> np.ndarray:
    """Per-bar drift for a 2-state (bull/bear) Markov regime switch. Starts bull; each bar
    switches state with probability 1/`half_life_bars` (geometric dwell time, mean =
    `half_life_bars`), so regimes persist ~`half_life_bars` bars. Bull bars carry `bull_mu`,
    bear bars `bear_mu`. Deterministic in `rng`. Exposed for a known-answer test (both regimes
    occur; realized bull-bar mean drift > bear-bar mean drift)."""
    switches = rng.random(n_bars) < (1.0 / half_life_bars)
    drift = np.empty(n_bars)
    bull = True
    for i in range(n_bars):
        if i > 0 and switches[i]:
            bull = not bull
        drift[i] = bull_mu if bull else bear_mu
    return drift


def generate_regime_frame(
    *,
    bull_sharpe: float,
    bear_sharpe: float,
    half_life_days: float,
    n_bars: int,
    seed: int,
    ann_vol: float = DEFAULT_ANN_VOL,
    start: datetime | None = None,
    timeframe: Timeframe = Timeframe.H1,
) -> pd.DataFrame:
    """An Oceanus-valid frame whose drift SWITCHES between a bull regime (within-regime
    annualized Sharpe `bull_sharpe`) and a bear regime (`bear_sharpe`, typically negative),
    persistence ~`half_life_days`, at constant volatility `ann_vol`. Unlike `generate_frame`'s
    single drift (buy-and-hold-shaped), this carries exploitable TIMING: a trend-following MA
    can harvest bulls and sidestep bears, while random long-only entries and an always-long
    signal cannot — so stages 4.1 and 4.9 can distinguish a real timing edge from luck.
    Deterministic in `seed`."""
    if n_bars < 2:
        raise ValueError(f"n_bars must be >= 2, got {n_bars}")
    if ann_vol <= 0:
        raise ValueError(f"ann_vol must be > 0, got {ann_vol}")
    if half_life_days <= 0:
        raise ValueError(f"half_life_days must be > 0, got {half_life_days}")
    start = start or _DEFAULT_START
    rng = np.random.default_rng(seed)

    bpy = HOURS_PER_YEAR
    sigma_bar = ann_vol / np.sqrt(bpy)
    bull_mu = ann_vol * bull_sharpe / bpy
    bear_mu = ann_vol * bear_sharpe / bpy
    bars_per_day = int(round(timedelta(days=1) / timeframe.duration))
    half_life_bars = max(1.0, half_life_days * bars_per_day)

    drift = regime_drift_schedule(n_bars, half_life_bars, bull_mu, bear_mu, rng)
    log_ret = drift + rng.normal(0.0, sigma_bar, n_bars)
    return _assemble_frame(log_ret, rng, start=start, timeframe=timeframe, wick_scale=sigma_bar)


def realized_annualized_sharpe(frame: pd.DataFrame) -> float:
    """The annualized Sharpe of a frame's realized log returns — the quantity the
    generator sets to `target_sharpe`. Used by the known-answer self-test."""
    close = frame["close"].astype(float).to_numpy()
    log_ret = np.diff(np.log(close))
    sd = log_ret.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(log_ret.mean() / sd * np.sqrt(HOURS_PER_YEAR))
