"""verify.py — read-time validity of a gauntlet verdict (§5.3).

"Visibly invalidated" (the phrase I9 left undefined) means: verdict records are
never edited or deleted (append-only), but every read path — `scripts/moirai_verify.py`
and any future viewer — recomputes validity at read time and renders stale verdicts
as `INVALIDATED(<reason>)`. This module is that computation, factored out as a pure
function so every reader shares one implementation.

Pure: takes the current coordinates as arguments (dependency injection), performs no
I/O, imports only the standard library, and never touches any record.
"""

# Reason codes from the §5.3 staleness table.
JUDGE_CHANGED = "judge_changed"
JUDGE_CODE_CHANGED = "judge_code_changed"
ENGINE_CHANGED = "engine_changed"


def verdict_validity(
    record: dict,
    *,
    active_config_hash: str,
    current_moirai_version: str,
    current_engine_version: str,
) -> tuple[bool, list[str]]:
    """Return (is_valid, reasons) for one `gauntlet_verdict` record against the
    current coordinates, per the §5.3 staleness table.

    Checks implemented at this phase:
      - gauntlet_config_hash  != active hash        -> judge_changed
      - moirai_code_version   != current moirai SHA -> judge_code_changed
      - engine_core_version   != current engine SHA -> engine_changed

    Deferred (documented, not silently skipped):
      - data_restated: requires an Oceanus snapshot comparison (snapshot infra
        not built for the skeleton). A `None` current_engine_version means the
        engine SHA could not be determined; the engine row is skipped rather
        than reported as a spurious change.

    A verdict with all implemented rows matching is `valid` at this phase; the
    deferred rows can only ever move a currently-valid verdict to INVALIDATED,
    never the reverse, so a `valid` result here is not overstated as final —
    callers render it alongside the note that data-restatement is unchecked.
    """
    reasons: list[str] = []

    if record.get("gauntlet_config_hash") != active_config_hash:
        reasons.append(JUDGE_CHANGED)

    if record.get("moirai_code_version") != current_moirai_version:
        reasons.append(JUDGE_CODE_CHANGED)

    if current_engine_version is not None and (
        record.get("engine_core_version") != current_engine_version
    ):
        reasons.append(ENGINE_CHANGED)

    return (not reasons), reasons
