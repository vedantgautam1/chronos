"""calibration/ — the synthetic-candle generator and the calibration harness (spec §7).

`generator.py` produces Oceanus-valid synthetic H1 OHLCV frames with a KNOWN injected
effect (annualized Sharpe = target S). `harness.py` is the structural quarantine: it
runs synthetic candidates through the real engine but into an ISOLATED calibration store,
never production — probe G5 pins that isolation.
"""

from chronos.moirai.calibration.generator import (
    GENERATOR_VERSION,
    generate_frame,
    provenance,
)
from chronos.moirai.calibration.harness import (
    CalibrationHarness,
    ProductionStoreError,
)

__all__ = [
    "GENERATOR_VERSION", "generate_frame", "provenance",
    "CalibrationHarness", "ProductionStoreError",
]
