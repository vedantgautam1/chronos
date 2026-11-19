"""B03 step 1 -- the spec's decision table, exactly as written, as a test.

Every row of "Known answers and checks" in ``specs/B03-loop-core.md`` is a case
here, named by its row number. The table runs on the FROZEN fixtures
``ladder_a.yaml`` and ``ladder_b.yaml``, never the live ladder, so a routine
change to the real ladder cannot turn this build's tests red (red-team second
pass, finding 11).

``now`` is fixed. ``claim_hours`` is 3 in both fixtures, so a lock is fresh for
three hours.

Rows 30, 30b, 30c and 31 turn on *who* ended a stop, which is a fact about an
issue's timeline rather than a decision: ``decide()`` sees one boolean. Those
rows are asserted twice -- here, that a stop in force yields ``NONE`` and that
a stop the owner ended does not, and in ``test_facts.py`` against
``halt_in_force`` itself, where the owner-only rule lives.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from conftest import FIXTURES

import ladder as ladder_mod
import next_action
from facts import Build, Facts, Gate
from next_action import LoopError, decide

NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
FRESH_20MIN = NOW - timedelta(minutes=20)
FRESH_1H = NOW - timedelta(hours=1)
STALE_4H = NOW - timedelta(hours=4)
STALE_3DAYS = NOW - timedelta(days=3)

PHASE0 = ("B01", "B01A", "B02", "B03", "B04", "B05")
PHASE1 = tuple(f"B{n:02d}" for n in range(6, 23))


@pytest.fixture(scope="module")
def ladder_a():
    return ladder_mod.load(FIXTURES / "ladder_a.yaml")


@pytest.fixture(scope="module")
def ladder_b():
    return ladder_mod.load(FIXTURES / "ladder_b.yaml")


def done(*ids: str) -> dict[str, Build]:
    """Builds whose status file says ``merged`` on the build branch."""
    return {i: Build(done=True) for i in ids}


def gates(*ids: str, **extra: Gate) -> dict[str, Gate]:
    """``ids`` are gates whose report is on ``main``; ``extra`` is spelled out."""
    out = {i: Gate(on_main=True, on_base=True) for i in ids}
    out.update(extra)
    return out


def facts(builds=None, gate=None, **kw) -> Facts:
    return Facts(builds=builds or {}, gates=gate or {}, **kw)


def through(last: str, extra=None) -> dict[str, Build]:
    """Every phase-1 build up to and including ``last``, merged."""
    ids = PHASE1[: PHASE1.index(last) + 1]
    out = {**done(*PHASE0), **done(*ids)}
    out.update(extra or {})
    return out


# ---------------------------------------------------------------- rows 1-8b
# Gates. A gate is done when its report is on `main`.


def test_row_1_no_g0_report_on_main(ladder_a):
    action = decide(ladder_a, facts(), NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "G0")


def test_row_2_g0_done_nothing_merged(ladder_a):
    action = decide(ladder_a, facts(gate=gates("G0")), NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "B01")


def test_row_3_phase0_merged_no_g1_report_no_branch(ladder_a):
    action = decide(ladder_a, facts(done(*PHASE0), gates("G0")), NOW)
    assert (action.kind, action.id) == ("RUN_GATE_AUDIT", "G1")


def test_row_4_gate_branch_exists_no_pr_lock_stale(ladder_a):
    g = gates("G0", G1=Gate(branch=True, lock_at=STALE_4H))
    action = decide(ladder_a, facts(done(*PHASE0), g), NOW)
    assert (action.kind, action.id) == ("RUN_GATE_AUDIT", "G1")


def test_row_5_writeup_pull_request_open(ladder_a):
    g = gates("G0", G1=Gate(branch=True, writeup_pr="open"))
    action = decide(ladder_a, facts(done(*PHASE0), g), NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "G1")


def test_row_6_writeup_closed_without_merging_branch_still_there(ladder_a):
    g = gates("G0", G1=Gate(branch=True, writeup_pr="closed_unmerged"))
    action = decide(ladder_a, facts(done(*PHASE0), g), NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "G1")


def test_row_7_report_on_base_not_main_no_move_pull_request(ladder_a):
    g = gates("G0", G1=Gate(on_base=True))
    action = decide(ladder_a, facts(done(*PHASE0), g), NOW)
    assert (action.kind, action.id) == ("OPEN_GATE_MOVE", "G1")


def test_row_8_move_pull_request_open(ladder_a):
    g = gates("G0", G1=Gate(on_base=True, move_pr="open"))
    action = decide(ladder_a, facts(done(*PHASE0), g), NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "G1")


def test_row_8b_move_closed_without_merging_is_not_reopened(ladder_a):
    g = gates("G0", G1=Gate(on_base=True, move_pr="closed_unmerged"))
    action = decide(ladder_a, facts(done(*PHASE0), g), NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "G1")


# ----------------------------------------------------------------- rows 9-28c
# Builds.


def test_row_9_g1_done_starts_b06(ladder_a):
    action = decide(ladder_a, facts(done(*PHASE0), gates("G0", "G1")), NOW)
    assert action.kind == "START_BUILD"
    assert action.id == "B06"
    assert action.model == "opus"
    assert action.branch == "claude/b06"


def b06(**kw) -> dict[str, Build]:
    return {**done(*PHASE0), "B06": Build(branch=True, **kw)}


def test_row_10_building_lock_fresh(ladder_a):
    f = facts(b06(state="building", ticks=1, lock_at=FRESH_1H), gates("G0", "G1"))
    assert decide(ladder_a, f, NOW).kind == "NONE"


def test_row_11_building_lock_stale_within_budget_resumes(ladder_a):
    f = facts(b06(state="building", ticks=1, lock_at=STALE_4H), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("RESUME_BUILD", "B06")


def test_row_12_building_lock_stale_at_tick_budget_halts(ladder_a):
    f = facts(b06(state="building", ticks=3, lock_at=STALE_4H), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("HALT", "B06")
    assert "overrun" in action.reason.lower()


def test_row_13_needs_review_no_lock(ladder_a):
    f = facts(b06(state="needs_review"), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("REVIEW", "B06")


def test_row_14_needs_review_fresh_review_lock(ladder_a):
    f = facts(
        b06(state="needs_review", lock_at=FRESH_20MIN, lock_action="review"),
        gates("G0", "G1"),
    )
    assert decide(ladder_a, f, NOW).kind == "NONE"


def test_row_15_needs_review_stale_review_lock_is_taken_over(ladder_a):
    f = facts(
        b06(state="needs_review", lock_at=STALE_4H, lock_action="review"),
        gates("G0", "G1"),
    )
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("REVIEW", "B06")


def test_row_16_changes_requested_one_review_file(ladder_a):
    f = facts(b06(state="changes_requested", rounds=1), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("FIX", "B06")


def test_row_17_changes_requested_two_review_files_halts(ladder_a):
    f = facts(b06(state="changes_requested", rounds=2), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("HALT", "B06")
    assert "review" in action.reason.lower()


def test_row_18_passed_checks_green_merges(ladder_a):
    f = facts(b06(state="passed", rounds=1, checks="green"), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("MERGE", "B06")


def test_row_19_passed_checks_pending(ladder_a):
    f = facts(b06(state="passed", rounds=1, checks="pending"), gates("G0", "G1"))
    assert decide(ladder_a, f, NOW).kind == "NONE"


def test_row_20_passed_checks_red_halts(ladder_a):
    f = facts(b06(state="passed", rounds=1, checks="red"), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("HALT", "B06")


def test_row_21_merged_on_branch_pull_request_still_open_finishes_the_merge(ladder_a):
    f = facts(
        b06(state="merged", rounds=1, checks="green", pr="open"),
        gates("G0", "G1"),
    )
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("MERGE", "B06")


def test_row_22_merged_on_branch_pull_request_closed_unmerged_halts(ladder_a):
    f = facts(
        b06(state="merged", rounds=1, checks="green", pr="closed_unmerged"),
        gates("G0", "G1"),
    )
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("HALT", "B06")


def test_row_23_b06_merged_starts_b07(ladder_a):
    f = facts(through("B06"), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("START_BUILD", "B07")


def test_row_24_halted_build_blocks_only_what_needs_it(ladder_a):
    f = facts(b06(state="halted"), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("START_BUILD", "B09")


def test_row_25_halted_is_parked_while_another_build_is_active(ladder_a):
    builds = {
        **b06(state="halted"),
        "B09": Build(branch=True, state="building", ticks=1, lock_at=FRESH_1H),
    }
    assert decide(ladder_a, facts(builds, gates("G0", "G1")), NOW).kind == "NONE"


def test_row_26_halted_and_nothing_else_runnable_waits_on_the_founder(ladder_a):
    # Everything phase 1 is merged except the four builds that need B06.
    others = [i for i in PHASE1 if i not in ("B06", "B07", "B08", "B18", "B20")]
    builds = {**done(*PHASE0), **done(*others), **b06(state="halted")}
    action = decide(ladder_a, facts(builds, gates("G0", "G1")), NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "B06")


def test_row_27_two_building_loop_builds_is_an_error_exit(ladder_a):
    builds = {
        **b06(state="building", ticks=1, lock_at=FRESH_1H),
        "B09": Build(branch=True, state="building", ticks=1, lock_at=FRESH_1H),
    }
    with pytest.raises(LoopError, match="one active loop build at a time"):
        decide(ladder_a, facts(builds, gates("G0", "G1")), NOW)


def parked_b20() -> Build:
    """Review finished, checks green, waiting only on the founder's review."""
    return Build(
        branch=True,
        state="merged",
        rounds=1,
        checks="green",
        pr="open",
        pr_review="waiting_on_founder",
    )


def test_row_28_parked_on_the_founder_does_not_block_the_next_build(ladder_a):
    builds = through("B19", {"B20": parked_b20()})
    action = decide(ladder_a, facts(builds, gates("G0", "G1")), NOW)
    assert (action.kind, action.id) == ("START_BUILD", "B21")
    assert "B20" in action.waiting_on_founder


def test_row_28b_once_the_founder_has_approved_it_merges(ladder_a):
    b20 = Build(
        branch=True,
        state="merged",
        rounds=1,
        checks="green",
        pr="open",
        pr_review="approved",
    )
    builds = through("B19", {"B20": b20})
    action = decide(ladder_a, facts(builds, gates("G0", "G1")), NOW)
    assert (action.kind, action.id) == ("MERGE", "B20")


def test_row_28c_parked_and_nothing_else_runnable_waits_on_the_founder(ladder_a):
    builds = through("B19", {"B20": parked_b20(), **done("B21", "B22")})
    action = decide(ladder_a, facts(builds, gates("G0", "G1")), NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "B20")


# ---------------------------------------------------------------- rows 29-32
# The emergency stop, and the global halt.


def test_row_29_an_open_halt_issue_stops_everything(ladder_a):
    f = facts(through("B06"), gates("G0", "G1"), halted=True)
    assert decide(ladder_a, f, NOW).kind == "NONE"


@pytest.mark.parametrize("row", ["30", "30b", "30c"])
def test_rows_30_a_stop_the_automation_tried_to_end_is_still_in_force(ladder_a, row):
    # `halt_in_force` is what decides this; see test_facts.py for row 30's
    # three endings. Whatever the ending, a stop still in force means NONE.
    f = facts(through("B06"), gates("G0", "G1"), halted=True)
    assert decide(ladder_a, f, NOW).kind == "NONE"


def test_row_31_a_stop_the_owner_ended_lets_the_loop_act_normally(ladder_a):
    f = facts(through("B06"), gates("G0", "G1"), halted=False)
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("START_BUILD", "B07")


def test_row_32_checks_red_on_the_build_branch_itself_halts_globally(ladder_a):
    f = facts(through("B06"), gates("G0", "G1"), base_checks="red")
    action = decide(ladder_a, f, NOW)
    assert action.kind == "HALT"
    assert action.id is None
    assert "v2-build" in action.reason


# ---------------------------------------------------------------- rows 33-39


def test_row_33_phase1_merged_runs_the_g2_audit(ladder_a):
    f = facts(through("B22"), gates("G0", "G1"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("RUN_GATE_AUDIT", "G2")


def test_row_34_a_card_build_waits_for_its_spec_to_be_written(ladder_a):
    f = facts(through("B22"), gates("G0", "G1", "G2"))
    action = decide(ladder_a, f, NOW)
    assert (action.kind, action.id) == ("WAIT_FOUNDER", "B23")
    assert "spec" in action.reason.lower()
    assert "B42" in action.waiting_on_founder


def test_row_35_ladder_b_gives_b23_a_spec_so_b24_can_start(ladder_b):
    builds = through("B22", done("B23"))
    action = decide(ladder_b, facts(builds, gates("G0", "G1", "G2")), NOW)
    assert (action.kind, action.id) == ("START_BUILD", "B24")
    assert "B26" in action.waiting_on_founder
    assert "B42" in action.waiting_on_founder


def test_row_36_a_founder_build_is_never_resumed_however_stale_its_lock(ladder_b):
    builds = through(
        "B22",
        {
            **done("B23", "B24", "B25", "B26", "B27", "B28", "B29"),
            "B30": Build(branch=True, state="building", ticks=1, lock_at=STALE_3DAYS),
        },
    )
    action = decide(ladder_b, facts(builds, gates("G0", "G1", "G2")), NOW)
    assert action.kind == "WAIT_FOUNDER"
    for build_id in ("B30", "B42", "B43"):
        assert build_id in action.waiting_on_founder
    assert action.kind != "RESUME_BUILD"


def test_row_37_a_status_file_for_an_id_not_on_this_ladder_is_ignored(ladder_a):
    """Same decision as without it; the status report names it in its notes."""
    plain = facts(through("B06"), gates("G0", "G1"))
    with_stranger = facts(
        {**through("B06"), "B97": Build(branch=True, state="building", lock_at=FRESH_1H)},
        gates("G0", "G1"),
        unknown=("B97",),
    )
    expected = decide(ladder_a, plain, NOW)
    got = decide(ladder_a, with_stranger, NOW)
    assert (got.kind, got.id) == (expected.kind, expected.id) == ("START_BUILD", "B07")


def test_row_38_a_build_needing_two_things_waits_for_both(ladder_a):
    # B14 needs B11 and B13. B11 merged, B13 not.
    builds = through("B11")
    action = decide(ladder_a, facts(builds, gates("G0", "G1")), NOW)
    assert action.id != "B14"
    assert (action.kind, action.id) == ("START_BUILD", "B12")


def test_row_39_a_pull_request_from_a_fork_is_ignored(ladder_a):
    """The facts layer drops forks, so the decision is the one with no such
    pull request. Asserted at the facts layer too (test_facts.py)."""
    plain = facts(through("B06"), gates("G0", "G1"))
    assert decide(ladder_a, plain, NOW).id == "B07"


def test_decide_does_no_io():
    """Row: ``decide()`` imports nothing that does I/O."""
    import socket
    import subprocess

    def boom(*a, **k):  # pragma: no cover - raising is the point
        raise AssertionError("decide() must not do I/O")

    patched = []
    for module, name in ((subprocess, "run"), (subprocess, "Popen"), (socket, "socket")):
        patched.append((module, name, getattr(module, name)))
        setattr(module, name, boom)
    try:
        ladder = ladder_mod.load(FIXTURES / "ladder_a.yaml")
        action = decide(ladder, facts(gate=gates("G0")), NOW)
        assert action.kind == "WAIT_FOUNDER"
    finally:
        for module, name, original in patched:
            setattr(module, name, original)


def test_every_action_name_in_the_spec_exists():
    assert set(next_action.ACTIONS) == {
        "START_BUILD",
        "RESUME_BUILD",
        "REVIEW",
        "FIX",
        "MERGE",
        "RUN_GATE_AUDIT",
        "OPEN_GATE_MOVE",
        "WAIT_FOUNDER",
        "HALT",
        "NONE",
    }


def test_every_action_carries_a_one_line_plain_language_reason(ladder_a):
    action = decide(ladder_a, facts(done(*PHASE0), gates("G0", "G1")), NOW)
    assert action.reason
    assert "\n" not in action.reason
