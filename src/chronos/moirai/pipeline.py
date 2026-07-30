"""pipeline.py — the Moira protocol and the DAG runner (spec §3).

The machine that runs the gauntlet: it executes registered Moirai in the config's
`pipeline_order`, short-circuits on the first failure (unless `full_evaluation_mode`),
records one `gauntlet_outcome` per EXECUTED stage plus exactly one `gauntlet_verdict`
on EVERY exit path including crashes (I11, try/finally — exactly as
`run_experiment()` does), and returns the verdict.

In Phase 3 there are no real Moirai; two throwaway no-ops (`tests/moirai/_noop.py`)
exercise the DAG and are deleted in Phase 4a. The rigor is all here: the pipeline
logs and reproduces correctly before any real test exists to slot into it.

--- Status determination (spec §3.2) ------------------------------------------

A stage signals a terminal status by stamping `evidence[TERMINAL_STATUS_KEY]` (see
types.py). The runner, over the EXECUTED outcomes:
  - any NON_PROMOTABLE signal      → status NON_PROMOTABLE (terminal, zero downstream)
  - else any INSUFFICIENT_BREADTH  → status INSUFFICIENT_BREADTH
  - else any `passed == False`     → status FAIL
  - else (all executed passed)     → status PASS
A crash anywhere → status ERRORED (record persisted, then re-raised).

`cause_of_death`:
  - short-circuit mode: the single first non-passing moira_id
  - full-evaluation mode: the ordered, comma-joined list of all failing moira_ids
  - ERRORED: the error text
  - PASS: None
"""

import time
from typing import Mapping, Protocol, runtime_checkable

from chronos.hephaestus.types import BacktestResult
from chronos.moirai.config import moirai_code_version
from chronos.moirai.context import GauntletContext
from chronos.moirai.types import (
    AUTHORITATIVE,
    ERRORED,
    FAIL,
    INSUFFICIENT_BREADTH,
    NON_PROMOTABLE,
    NO_AUTHORITY,
    PASS,
    TERMINAL_STATUS_KEY,
    GauntletVerdict,
    TestOutcome,
)


class MoiraRegistryError(ValueError):
    """A moira_id appears in `pipeline_order` with no registered Moira. A
    config/registry mismatch — raised clearly, never silently skipped (spec §3.2)."""


@runtime_checkable
class Moira(Protocol):
    """One stage of the gauntlet. `moira_id` is stable and versioned with the
    config; `evaluate` inspects the judged result (and, for re-run stages, uses
    `ctx.run`) and returns its TestOutcome."""

    moira_id: str

    def evaluate(self, result: BacktestResult, ctx: GauntletContext) -> TestOutcome: ...


def _skipped_outcome(moira_id: str) -> TestOutcome:
    """The placeholder for a stage the short-circuit never reached. `executed` is
    False and `passed` is False — the record states plainly that the downstream
    verdict is UNKNOWN, not passed (spec §3.2, the 2026-07-18 ordering-artifact
    resolution)."""
    return TestOutcome(
        moira_id=moira_id,
        passed=False,
        score=0.0,
        evidence={"reason": "not executed — upstream short-circuit"},
        executed=False,
        runtime_s=0.0,
    )


def _terminal_signal(outcome: TestOutcome) -> str | None:
    """Read the reserved terminal-status key from an executed outcome's evidence."""
    evidence = outcome.evidence or {}
    return evidence.get(TERMINAL_STATUS_KEY)


def _determine_status(
    outcomes: tuple[TestOutcome, ...], *, full_evaluation_mode: bool
) -> tuple[str, str | None]:
    """Fold the executed outcomes into (status, cause_of_death) per spec §3.2."""
    executed = [o for o in outcomes if o.executed]

    for o in executed:
        if _terminal_signal(o) == NON_PROMOTABLE:
            return NON_PROMOTABLE, o.moira_id
    for o in executed:
        if _terminal_signal(o) == INSUFFICIENT_BREADTH:
            return INSUFFICIENT_BREADTH, o.moira_id

    failures = [o for o in executed if not o.passed]
    if not failures:
        return PASS, None
    if full_evaluation_mode:
        return FAIL, ",".join(o.moira_id for o in failures)
    return FAIL, failures[0].moira_id


def _outcome_record(verdict_id: str, judged_run_id: str, outcome: TestOutcome) -> dict:
    """One `gauntlet_outcome` store record for an executed stage (I11)."""
    from chronos.moirai.types import _outcome_payload

    return {
        "type": "gauntlet_outcome",
        "verdict_id": verdict_id,
        "judged_run_id": judged_run_id,
        **_outcome_payload(outcome),
    }


def _verdict_record(verdict: GauntletVerdict) -> dict:
    """One `gauntlet_verdict` store record (I11), built from the same canonical
    payload the serializers use so the stored bytes and the byte-compare form
    share one mechanism."""
    from chronos.moirai.types import _verdict_payload

    return {"type": "gauntlet_verdict", **_verdict_payload(verdict)}


def _next_verdict_id(store) -> str:
    """Monotonic verdict id derived from the store (bookkeeping, like the engine's
    trial_index). Counts existing `gauntlet_verdict` records; stripped in the
    determinism view so its value never affects byte-comparison."""
    n = sum(1 for r in store.read_all() if r.get("type") == "gauntlet_verdict")
    return f"{n + 1:06d}-verdict"


def run_gauntlet(
    result: BacktestResult,
    moirai: Mapping[str, Moira],
    ctx: GauntletContext,
    *,
    search_n: int,
    effective_n: float | None = None,
) -> GauntletVerdict:
    """Run the pipeline in `ctx.config.pipeline_order`, short-circuiting on the
    first failure unless `full_evaluation_mode`. Writes one `gauntlet_outcome`
    record per EXECUTED stage plus one `gauntlet_verdict` record on every exit
    path, including crashes (I11). Returns the verdict.

    A crash mid-pipeline persists every per-stage outcome gathered so far plus an
    `ERRORED` verdict carrying the error text, then re-raises — the caller sees
    the exception; the record survives (probe G4)."""
    order = tuple(ctx.config.pipeline_order)

    # A moira_id in the order with no registered Moira is a config/registry error
    # — raise clearly BEFORE any record is written (spec §3.2).
    missing = [mid for mid in order if mid not in moirai]
    if missing:
        raise MoiraRegistryError(
            f"pipeline_order names moira_ids with no registered Moira: {missing}"
        )

    verdict_id = _next_verdict_id(ctx.store)
    authority = AUTHORITATIVE if ctx.is_calibrated else NO_AUTHORITY
    coords = dict(
        gauntlet_config_hash=ctx.gauntlet_config_hash,
        moirai_code_version=moirai_code_version(),
        engine_core_version=result.core_version,
        data_snapshot_hash=result.data_snapshot_hash,
        gauntlet_seed=ctx.gauntlet_seed,
        search_n=search_n,
        effective_n=effective_n,
        evaluation_window=(
            result.date_range[0].isoformat(),
            result.date_range[1].isoformat(),
        ),
        authority=authority,
    )

    outcomes: list[TestOutcome] = []
    verdict: GauntletVerdict | None = None

    def _make_verdict(status: str, cause_of_death: str | None) -> GauntletVerdict:
        from datetime import datetime, timezone

        return GauntletVerdict(
            verdict_id=verdict_id,
            judged_run_id=result.run_id,
            hypothesis_id=result.hypothesis_id,
            status=status,
            cause_of_death=cause_of_death,
            outcomes=tuple(outcomes),
            judged_at=datetime.now(timezone.utc).isoformat(),
            **coords,
        )

    try:
        terminated = False
        for mid in order:
            if terminated:
                outcomes.append(_skipped_outcome(mid))
                continue

            moira = moirai[mid]
            t0 = time.perf_counter()
            outcome = moira.evaluate(result, ctx)  # may raise → ERRORED path
            if outcome.runtime_s == 0.0:
                # Stamp measured runtime if the Moira left it at the default.
                outcome = TestOutcome(
                    moira_id=outcome.moira_id,
                    passed=outcome.passed,
                    score=outcome.score,
                    evidence=outcome.evidence,
                    executed=outcome.executed,
                    runtime_s=time.perf_counter() - t0,
                )
            outcomes.append(outcome)
            ctx.store.append(_outcome_record(verdict_id, result.run_id, outcome))

            # Control flow: NON_PROMOTABLE is terminal regardless of mode; any
            # other non-pass short-circuits only when not in full-evaluation mode.
            if _terminal_signal(outcome) == NON_PROMOTABLE:
                terminated = True
            elif not outcome.passed and not ctx.config.full_evaluation_mode:
                terminated = True

        status, cause_of_death = _determine_status(
            tuple(outcomes), full_evaluation_mode=ctx.config.full_evaluation_mode
        )
        verdict = _make_verdict(status, cause_of_death)
        return verdict
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
        verdict = _make_verdict(ERRORED, error_text)
        raise  # the caller MUST see the crash — but the record persists (finally)
    finally:
        # I11: exactly one verdict record on every exit path. If verdict is still
        # None here, something raised inside _make_verdict itself; build a last-
        # resort ERRORED record so no judgment goes unlogged.
        if verdict is None:
            verdict = GauntletVerdict(
                verdict_id=verdict_id,
                judged_run_id=result.run_id,
                hypothesis_id=result.hypothesis_id,
                status=ERRORED,
                cause_of_death="verdict construction failed",
                outcomes=tuple(outcomes),
                judged_at="",
                **coords,
            )
        ctx.store.append(_verdict_record(verdict))
