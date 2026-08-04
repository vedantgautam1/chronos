"""harness.py — the calibration quarantine (spec §7.2; probe G5).

Calibration runs synthetic candidates through the REAL engine (real costs, fills, caps —
Mode E) but must NEVER touch the production record store: a synthetic run may not advance
the production trial counter, appear in `compute_search_n()`, or land in production's
`runs.jsonl`. The structural guarantee:

  - The harness constructor takes a store path and **raises `ProductionStoreError` if it
    resolves to the production records directory (or an ancestor of it).** `RecordStore`
    keys its `runs.jsonl` AND `trial_counter.txt` off its root, so a DISTINCT root (the
    default `records/calibration/`, a separate store inside the gitignored records tree)
    is fully isolated; only sharing the production root could pollute it. That equality is
    exactly what is refused.
  - Synthetic frames reach `run_experiment()` only through the sanctioned door: they are
    served by a synthetic `exchange=` (so Oceanus itself validates and stores them — I7,
    no back-door `store` import), into the harness's own isolated `data_root=`
    (`<store>/data/run<i>/`, one per run so frames never collide) — synthetic candles never
    land in the production bar directory.

Probe G5 asserts both halves: the constructor refuses the production path, and a full
synthetic ladder leaves the production `trial_counter.txt` and every `compute_search_n()`
output byte-identical.

Provenance: every synthetic run the harness records carries `data_provenance:
synthetic:<generator version>` (a `calibration_run` record in the isolated store). The
engine's `BacktestResult.warnings` is the door's frozen output and is not mutated here; the
provenance rides on the calibration record, which is the layer calibration reports consume.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.calibration.generator import provenance
from chronos.oceanus.model import Timeframe
from chronos.run import DEFAULT_RECORDS_DIR, Hypothesis, RunConfig, RunKind, run_experiment

DEFAULT_CALIBRATION_ROOT = DEFAULT_RECORDS_DIR / "calibration"
_SYNTH_SYMBOL = "SYNTH/USDT"


class ProductionStoreError(RuntimeError):
    """Raised when a CalibrationHarness is pointed at the production record store. The
    calibration store MUST be a distinct root (spec §7.2, probe G5)."""


class _SyntheticExchange:
    """A minimal ccxt-shaped stand-in that serves ONE synthetic frame's candles, so
    Oceanus's own fetch/validate/store path handles the data (I7). `fetch_time` sits
    past the last bar, so every served bar is final (never a forming bar)."""

    def __init__(self, frame: pd.DataFrame, timeframe: Timeframe):
        dur_ms = int(timeframe.duration.total_seconds() * 1000)
        self._candles = [
            [int(t.timestamp() * 1000), float(o), float(h), float(l), float(c), float(v)]
            for t, o, h, l, c, v in zip(
                frame["open_time"], frame["open"], frame["high"],
                frame["low"], frame["close"], frame["volume"])
        ]
        self._now_ms = (self._candles[-1][0] + 2 * dur_ms) if self._candles else 0

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params=None):
        page = [c for c in self._candles if since is None or c[0] >= since]
        return page[:limit] if limit else page

    def fetch_time(self):
        return self._now_ms


@dataclass(frozen=True)
class CalibrationRun:
    """One synthetic run's outcome, plus the provenance stamp."""

    run_id: str
    result: object  # BacktestResult
    data_provenance: str


class CalibrationHarness:
    """Runs synthetic candidates into an isolated store. Refuses the production store."""

    def __init__(self, store_path: Path | str | None = None):
        store_path = Path(store_path) if store_path is not None else DEFAULT_CALIBRATION_ROOT
        resolved = store_path.resolve()
        prod = DEFAULT_RECORDS_DIR.resolve()
        if resolved == prod or resolved in prod.parents:
            raise ProductionStoreError(
                f"calibration store {resolved} is the production records directory "
                f"({prod}) or an ancestor of it — synthetic runs must never share "
                f"production's runs.jsonl/trial_counter.txt (spec §7.2, probe G5). "
                f"Use a distinct root, e.g. {DEFAULT_CALIBRATION_ROOT}."
            )
        self.store_path = resolved
        self.store = RecordStore(resolved)
        self.data_root = resolved / "data"  # synthetic parquet stays here, isolated
        self._counter = 0

    def run_synthetic(
        self,
        strategy,
        frame: pd.DataFrame,
        hypothesis: Hypothesis,
        kind: RunKind,
        *,
        symbol: str = _SYNTH_SYMBOL,
        timeframe: Timeframe = Timeframe.H1,
        strategy_params: dict | None = None,
    ) -> CalibrationRun:
        """Run `strategy` on a synthetic `frame` through the real engine, entirely inside
        the isolated calibration store/data root. Each call uses its own data subdir so
        successive frames never collide. Stamps synthetic provenance."""
        synth = _SyntheticExchange(frame, timeframe)
        run_data_root = self.data_root / f"run{self._counter}"
        self._counter += 1
        start = frame["open_time"].iloc[0].to_pydatetime()
        end = (frame["open_time"].iloc[-1] + timeframe.duration).to_pydatetime()
        config = RunConfig(symbol=symbol, timeframe=timeframe, start=start, end=end,
                           strategy_params=strategy_params or {})
        record = run_experiment(strategy, config, hypothesis, kind=kind,
                                store=self.store, data_root=run_data_root, exchange=synth)
        prov = provenance()
        self.store.append({
            "type": "calibration_run", "run_id": record.run_id,
            "kind": kind.value, "data_provenance": prov,
            "hypothesis_id": hypothesis.id,
        })
        return CalibrationRun(run_id=record.run_id, result=record.result, data_provenance=prov)
