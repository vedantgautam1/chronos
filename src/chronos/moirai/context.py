"""context.py — the GauntletContext and the `ctx.run` wrapper (spec §2, §5.4).

`GauntletContext` is the injected, never-global state a Moira sees: the one seeded
RNG (I10 — the ONLY randomness source in the gauntlet), the record store, the
active config and its hash, the gauntlet seed, and `ctx.run`.

`ctx.run` is a thin wrapper over `run_experiment()` that does three things the raw
function does not:

1. **Forces explicit `kind=`.** `kind` is keyword-only with no default, so a call
   site that omits it raises `TypeError`. This is discipline enforcement, not a
   convenience — every gauntlet run must state whether it is SEARCH or VERIFICATION.
2. **Stamps `gauntlet_config_hash` into the `RunConfig`** (I9, §5.4). This closes
   the anchor the engine deliberately left as `None`: every gauntlet-triggered
   engine record now carries the judge that commissioned it. Runs outside any
   gauntlet keep `None`, which now *means* "not commissioned by a judge."
3. **Refuses SEARCH after N is finalized.** When `_search_frozen` is True (set by
   stage 4.2 in Phase 4b), a `kind=SEARCH` call raises `SearchFrozenError` — a
   structural guard, not a comment, so no later stage can inflate N. Probe G6b
   (Phase 4b) relies on this mechanism, which lands now.

This module is runtime, not the light read-only path, so it imports the engine
door (`chronos.run`) freely.
"""

from dataclasses import dataclass, field, replace

import numpy as np

from chronos.mnemosyne.stub import RecordStore
from chronos.moirai.config import (
    GauntletConfig,
    config_hash,
    load_active_config,
)
from chronos.run import RunConfig, RunKind, run_experiment


class SearchFrozenError(RuntimeError):
    """Raised when a SEARCH-kind run is attempted after stage 4.2 finalized N.

    Structural enforcement of I6/§4.2: once `compute_search_n()` is frozen for the
    verdict, no stage may spend more search budget. See spec §4.2 and probe G6b."""


@dataclass
class GauntletContext:
    """Injected state for one gauntlet evaluation (spec §2).

    `rng` is seeded from `gauntlet_seed` and is the ONLY randomness source the
    gauntlet may use (I10; no global `random`/`np.random`). `is_calibrated` comes
    from Phase 2's activation guard and decides the verdict's authority stamp."""

    rng: np.random.Generator
    store: RecordStore
    config: GauntletConfig
    gauntlet_config_hash: str
    gauntlet_seed: int
    is_calibrated: bool = False
    # Internal state: flipped True after stage 4.2 freezes N (Phase 4b). See ctx.run.
    _search_frozen: bool = field(default=False)

    def run(self, *, kind: RunKind, config: RunConfig, strategy, hypothesis, **kwargs):
        """Thin wrapper over `run_experiment()` — forces explicit `kind=`, stamps
        the I9 anchor, and enforces the post-4.2 SEARCH freeze.

        `kind` is keyword-only with no default: omitting it raises `TypeError`."""
        if self._search_frozen and kind == RunKind.SEARCH:
            raise SearchFrozenError(
                "N is finalized after stage 4.2; no further SEARCH runs may inflate it."
            )
        stamped_config = replace(config, gauntlet_config_hash=self.gauntlet_config_hash)
        return run_experiment(
            strategy=strategy,
            config=stamped_config,
            hypothesis=hypothesis,
            kind=kind,
            store=self.store,
            **kwargs,
        )

    def freeze_search(self) -> None:
        """Finalize N: from here on `ctx.run(kind=SEARCH, ...)` raises. Called by
        stage 4.2 once the plateau neighbors have been run (Phase 4b)."""
        self._search_frozen = True


def make_context(
    store: RecordStore,
    configs_dir,
    gauntlet_seed: int,
) -> GauntletContext:
    """Build a GauntletContext from the ACTIVE gauntlet config (spec §5.2).

    Reads the ACTIVE pointer, loads the config, computes its hash, and carries the
    activation guard's `is_calibrated` through so the verdict's authority stamp is
    honest. The RNG is seeded from `gauntlet_seed` (I10)."""
    config, cfg_hash, is_calibrated = load_active_config(configs_dir)
    return GauntletContext(
        rng=np.random.default_rng(gauntlet_seed),
        store=store,
        config=config,
        gauntlet_config_hash=cfg_hash,
        gauntlet_seed=gauntlet_seed,
        is_calibrated=is_calibrated,
    )


def context_for_config(
    store: RecordStore,
    config: GauntletConfig,
    gauntlet_seed: int,
    *,
    is_calibrated: bool = False,
) -> GauntletContext:
    """Build a context around an explicit (e.g. in-test) GauntletConfig, computing
    its hash. Used where the ACTIVE-pointer path is not wanted (tests, the Phase 3
    no-op pipeline)."""
    return GauntletContext(
        rng=np.random.default_rng(gauntlet_seed),
        store=store,
        config=config,
        gauntlet_config_hash=config_hash(config),
        gauntlet_seed=gauntlet_seed,
        is_calibrated=is_calibrated,
    )
