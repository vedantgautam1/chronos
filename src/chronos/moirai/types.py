"""types.py — the gauntlet's core records: TestOutcome and GauntletVerdict (spec §2).

Two frozen dataclasses plus their canonical serialization. The serialization
mechanism is the SAME one already pinned across the project: `_canonical` (sorted
keys, no whitespace, Decimals as strings, datetimes as ISO, Enums as `.value`).
Rather than write a third copy, this module imports `_canonical` from
`chronos.moirai.config`, which itself is byte-pinned to `chronos.run._canonical`
by `tests/moirai/test_config.py`. So all three stay identical by construction.

This module imports only the standard library and `config._canonical` — no engine,
data, or ccxt imports — so the read-only verify path and the judge stay light.

--- The determinism contract (I10) --------------------------------------------

I10: identical (judged result's five coordinates, `gauntlet_config_hash`,
`moirai_code_version`, gauntlet seed) → byte-identical serialized verdict.

`serialize_verdict()` is the full, faithful record. `verdict_determinism_view()`
is the byte-compare form for probe G1: it strips the fields that legitimately
vary between two otherwise-identical judgments, mirroring exactly how the engine's
`determinism_view()` strips `run_id`/`trial_index`. The strip-set is THREE fields
and no more (see `_DETERMINISM_STRIP` below); getting it right is the single most
important decision in this phase — strip too much and G1 proves nothing, strip too
little and G1 flakes on wall-clock noise.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from chronos.moirai.config import _canonical

import json

# --- Verdict statuses (spec §3.2) ----------------------------------------------
# String constants, not an enum, to keep serialization trivially canonical and to
# avoid any numeric literal the G2 gate-literal grep would (correctly) flag.
PASS = "PASS"
FAIL = "FAIL"
NON_PROMOTABLE = "NON_PROMOTABLE"
INSUFFICIENT_BREADTH = "INSUFFICIENT_BREADTH"
ERRORED = "ERRORED"

# --- Authority stamp (spec §5.2 activation guard) ------------------------------
# Until a GauntletConfig has a resolving calibration report, every verdict it
# writes is a smoke test, not a judgment (Phase 2's is_calibrated == False).
NO_AUTHORITY = "NO_AUTHORITY"
AUTHORITATIVE = "AUTHORITATIVE"

# --- Terminal-status signalling (design decision, see module docstring & HANDOFF)
# How a Moira tells the runner "this is NON_PROMOTABLE / INSUFFICIENT_BREADTH, not
# a plain FAIL": it stamps this reserved key into its outcome's `evidence`. Chosen
# over a new field on TestOutcome because (a) it keeps TestOutcome exactly at the
# spec's shape, (b) the signal rides in `evidence`, which is already the audited,
# serialized channel, and (c) Phase 4a's stage 4.0 sets one dict key rather than
# threading a new type through every Moira. The runner reads this key from every
# EXECUTED outcome; absent/None means "no terminal signal — ordinary pass/fail."
TERMINAL_STATUS_KEY = "terminal_status"


@dataclass(frozen=True)
class TestOutcome:
    """One Moira's verdict on one stage (spec §2).

    `passed`   — did this gate pass. For an un-executed (short-circuited) stage
                 this is False, but `executed` is False too: the record says
                 plainly the downstream verdict is *unknown*, not passed.
    `score`    — the test's headline number (p-value, DSR, percentile…).
    `evidence` — everything needed to audit the score offline, plus (optionally)
                 the reserved `terminal_status` key (see TERMINAL_STATUS_KEY).
    `executed` — False iff short-circuited before reaching this stage.
    `runtime_s`— wall-clock seconds; stripped in the determinism view (I10).
    """

    moira_id: str
    passed: bool
    score: float
    evidence: Mapping[str, Any] = field(default_factory=dict)
    executed: bool = True
    runtime_s: float = 0.0


@dataclass(frozen=True)
class GauntletVerdict:
    """The gauntlet's judgment of one verdict-grade run (spec §2).

    Carries every reproducibility coordinate I10 requires. `outcomes` holds one
    TestOutcome per stage in `pipeline_order` — executed stages with
    `executed=True`, short-circuited stages with `executed=False`.
    """

    verdict_id: str
    judged_run_id: str
    hypothesis_id: str
    status: str  # PASS | FAIL | NON_PROMOTABLE | INSUFFICIENT_BREADTH | ERRORED
    cause_of_death: str | None  # first failing moira_id (short-circuit);
    #                             ordered list joined (full-eval mode); error text (ERRORED)
    outcomes: tuple[TestOutcome, ...]

    # Reproducibility coordinates (I10):
    gauntlet_config_hash: str
    moirai_code_version: str
    engine_core_version: str  # copied from the judged BacktestResult
    data_snapshot_hash: str  # copied from the judged BacktestResult
    gauntlet_seed: int
    search_n: int
    effective_n: float | None
    evaluation_window: tuple[str, str]  # ISO strings; window V and stats measured on
    judged_at: str  # ISO wall-clock; stripped in the determinism view

    authority: str = NO_AUTHORITY  # AUTHORITATIVE once calibrated (Phase 6)


def _outcome_payload(o: TestOutcome) -> dict:
    """Canonical dict for one outcome (used by both serializers)."""
    return {
        "moira_id": o.moira_id,
        "passed": o.passed,
        "score": o.score,
        "evidence": _canonical(o.evidence),
        "executed": o.executed,
        "runtime_s": o.runtime_s,
    }


def _verdict_payload(v: GauntletVerdict) -> dict:
    return {
        "verdict_id": v.verdict_id,
        "judged_run_id": v.judged_run_id,
        "hypothesis_id": v.hypothesis_id,
        "status": v.status,
        "cause_of_death": v.cause_of_death,
        "outcomes": [_outcome_payload(o) for o in v.outcomes],
        "gauntlet_config_hash": v.gauntlet_config_hash,
        "moirai_code_version": v.moirai_code_version,
        "engine_core_version": v.engine_core_version,
        "data_snapshot_hash": v.data_snapshot_hash,
        "gauntlet_seed": v.gauntlet_seed,
        "search_n": v.search_n,
        "effective_n": v.effective_n,
        "evaluation_window": list(v.evaluation_window),
        "judged_at": v.judged_at,
        "authority": v.authority,
    }


def serialize_verdict(v: GauntletVerdict) -> str:
    """Canonical, deterministic serialization of a GauntletVerdict.

    Same mechanism as `serialize_result()`: sorted keys, no whitespace, Decimals
    as strings, datetimes as ISO. This is the faithful record written to the
    store; it contains the wall-clock and bookkeeping fields (I11 wants the full
    truth on the record). Byte-comparison happens through the determinism view."""
    return json.dumps(_verdict_payload(v), sort_keys=True, separators=(",", ":"))


# The three fields that legitimately vary between two identical judgments and are
# therefore stripped before byte-comparison (I10). This mirrors the engine's
# determinism_view stripping run_id/trial_index:
#   - verdict_id     : monotonic store bookkeeping (like trial_index)
#   - judged_at      : wall-clock timestamp (serialize_result carries none, by design)
#   - runtime_s      : per-outcome wall-clock-derived timing
# EVERYTHING ELSE — status, cause_of_death, every outcome's passed/score/evidence,
# all coordinates, search_n, effective_n, evaluation_window, authority — is compared.
_DETERMINISM_STRIP = ("verdict_id", "judged_at")


def verdict_determinism_view(v: GauntletVerdict) -> str:
    """The byte-compare form for probe G1 (I10).

    Strips the three bookkeeping/wall-clock fields (verdict_id, judged_at, and
    each outcome's runtime_s) and byte-compares the rest. Two judgments sharing
    the judged result's five coordinates, the config hash, the moirai code
    version and the gauntlet seed must produce byte-identical output here."""
    payload = _verdict_payload(v)
    for key in _DETERMINISM_STRIP:
        payload.pop(key, None)
    for outcome in payload["outcomes"]:
        outcome.pop("runtime_s", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
