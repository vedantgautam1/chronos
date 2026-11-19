"""B03 step 5 -- the facts layer and the status report.

Decision-table rows that are really *facts* rules live here, because this is
where they are implemented:

* rows 30, 30b, 30c and 31 -- who may end an emergency stop. ``decide`` sees
  one boolean; ``halt_in_force`` is what computes it, from each issue's
  **timeline** rather than its current labels;
* row 37b -- a status file that is not valid against the schema is an error
  exit, not a shrug;
* row 37 -- a status file for an id not on this ladder is ignored, and named
  in the status report's notes;
* row 39 -- a pull request whose head is in a fork is dropped, so a fork can
  never present itself as a build.
"""

from __future__ import annotations

from datetime import UTC, datetime

import ladder as ladder_mod
import pytest
import status_report
from conftest import FIXTURES
from facts import (
    Build,
    Facts,
    FactsError,
    Gate,
    _checks,
    _pr_state,
    _pull_requests,
    halt_in_force,
    validate_status,
)

NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
OWNER = "vedantgautam1"
BOT = "chronos-automation"


def issue(*events: tuple[str, str]) -> dict:
    return {"timeline": [{"event": kind, "actor": {"login": who}} for kind, who in events]}


# --------------------------------------------------- rows 30-31: who may stop


def test_row_29_a_labelled_issue_is_a_stop():
    assert halt_in_force([issue(("labeled", OWNER))], OWNER) is True


def test_a_stop_may_be_started_by_anyone():
    assert halt_in_force([issue(("labeled", BOT))], OWNER) is True


def test_row_30_closed_by_the_automation_is_still_in_force():
    assert halt_in_force([issue(("labeled", OWNER), ("closed", BOT))], OWNER) is True


def test_row_30b_unlabelled_by_the_automation_is_still_in_force():
    assert halt_in_force([issue(("labeled", OWNER), ("unlabeled", BOT))], OWNER) is True


def test_row_30c_label_deleted_from_the_repository_is_still_in_force():
    """The label is gone, so the issue carries none now; the timeline still
    shows it was applied and never ended by the owner."""
    assert halt_in_force([issue(("labeled", OWNER))], OWNER) is True


def test_row_31_closed_by_the_owner_ends_it():
    assert halt_in_force([issue(("labeled", BOT), ("closed", OWNER))], OWNER) is False


def test_row_31_unlabelled_by_the_owner_ends_it():
    assert halt_in_force([issue(("labeled", BOT), ("unlabeled", OWNER))], OWNER) is False


def test_a_stop_relabelled_after_the_owner_ended_it_is_in_force_again():
    events = issue(("labeled", BOT), ("closed", OWNER), ("labeled", BOT))
    assert halt_in_force([events], OWNER) is True


def test_no_issues_means_no_stop():
    assert halt_in_force([], OWNER) is False


def test_one_stop_among_several_issues_is_enough():
    ended = issue(("labeled", BOT), ("closed", OWNER))
    live = issue(("labeled", BOT))
    assert halt_in_force([ended, live], OWNER) is True


def test_the_owner_check_ignores_letter_case():
    assert halt_in_force([issue(("labeled", BOT), ("closed", OWNER.upper()))], OWNER) is False


# ------------------------------------------------- row 37b: the status schema

GOOD = {
    "build": "B06",
    "state": "building",
    "ticks": 1,
    "head": None,
    "halt_reason": None,
    "halt_options": None,
}


def test_a_valid_status_file_passes():
    assert validate_status(dict(GOOD))["build"] == "B06"


@pytest.mark.parametrize("key", sorted(GOOD))
def test_row_37b_a_missing_key_is_an_error(key):
    payload = {k: v for k, v in GOOD.items() if k != key}
    with pytest.raises(FactsError, match="missing"):
        validate_status(payload)


def test_row_37b_an_unknown_state_is_an_error():
    with pytest.raises(FactsError, match="allowed are"):
        validate_status({**GOOD, "state": "nearly"})


def test_row_37b_an_extra_key_is_an_error():
    with pytest.raises(FactsError, match="unexpected key"):
        validate_status({**GOOD, "sneaky": True})


def test_row_37b_a_non_integer_tick_count_is_an_error():
    with pytest.raises(FactsError, match="non-integer ticks"):
        validate_status({**GOOD, "ticks": "two"})


def test_a_boolean_is_not_an_integer_tick_count():
    with pytest.raises(FactsError, match="non-integer ticks"):
        validate_status({**GOOD, "ticks": True})


def test_row_37b_a_negative_tick_count_is_an_error():
    with pytest.raises(FactsError, match="negative ticks"):
        validate_status({**GOOD, "ticks": -1})


def test_every_live_status_file_validates():
    """The live status files are read with the same schema the loop uses."""
    import json

    from conftest import REPO_ROOT

    folder = REPO_ROOT / "docs" / "v2" / "build" / "status"
    found = sorted(folder.glob("*.json"))
    assert found, "no status files found"
    for path in found:
        validate_status(json.loads(path.read_text()), str(path))


# ------------------------------------------------------ row 39: forks dropped


def pr(ref: str, repo_full_name: str, number: int = 1) -> dict:
    return {
        "number": number,
        "state": "open",
        "head": {"ref": ref, "repo": {"full_name": repo_full_name}},
    }


def test_row_39_a_pull_request_from_a_fork_is_dropped():
    def api(path, *, repo):
        if path.startswith("pulls?state=open"):
            return [pr("claude/b06", "someone-else/chronos")]
        return []

    assert _pull_requests(api, "vedantgautam1/chronos", "v2-build") == {}


def test_a_pull_request_from_this_repository_is_kept():
    def api(path, *, repo):
        if path.startswith("pulls?state=open"):
            return [pr("claude/b06", "vedantgautam1/chronos")]
        return []

    found = _pull_requests(api, "vedantgautam1/chronos", "v2-build")
    assert set(found) == {"claude/b06"}


def test_a_fork_cannot_shadow_a_real_branch_of_the_same_name():
    def api(path, *, repo):
        if path.startswith("pulls?state=open"):
            return [
                pr("claude/b06", "someone-else/chronos", 9),
                pr("claude/b06", "vedantgautam1/chronos", 10),
            ]
        return []

    found = _pull_requests(api, "vedantgautam1/chronos", "v2-build")
    assert found["claude/b06"]["number"] == 10


# ------------------------------- waiting on the founder's review (rows 28-28c)


def open_pr(reviews=None, requested=(), owner=OWNER) -> dict:
    return {
        "number": 7,
        "state": "open",
        "head": {"ref": "claude/b20", "repo": {"full_name": "r"}},
        "requested_reviewers": [{"login": who} for who in requested],
        "_reviews": reviews or [],
        "_owner": owner,
    }


def review(who: str, state: str) -> dict:
    return {"user": {"login": who}, "state": state}


def test_row_28_requested_from_the_founder_and_not_yet_approved_is_waiting_on_him():
    assert _pr_state(open_pr(requested=[OWNER])) == ("open", "waiting_on_founder")


def test_row_28b_approved_by_the_founder_is_no_longer_waiting():
    pr = open_pr(reviews=[review(OWNER, "APPROVED")], requested=[])
    assert _pr_state(pr) == ("open", "approved")


def test_an_approval_by_anyone_else_is_not_the_founder_s_approval():
    pr = open_pr(reviews=[review(BOT, "APPROVED")], requested=[OWNER])
    assert _pr_state(pr) == ("open", "waiting_on_founder")


def test_changes_requested_by_the_founder_is_not_an_approval():
    pr = open_pr(reviews=[review(OWNER, "CHANGES_REQUESTED")], requested=[OWNER])
    assert _pr_state(pr) == ("open", "waiting_on_founder")


def test_an_approval_the_founder_later_replaced_does_not_count():
    """Only his latest verdict counts, so a withdrawn approval cannot park a
    build as mergeable."""
    pr = open_pr(
        reviews=[review(OWNER, "APPROVED"), review(OWNER, "CHANGES_REQUESTED")],
        requested=[OWNER],
    )
    assert _pr_state(pr) == ("open", "waiting_on_founder")


def test_a_comment_is_not_a_verdict_and_does_not_replace_one():
    pr = open_pr(
        reviews=[review(OWNER, "APPROVED"), review(OWNER, "COMMENTED")], requested=[]
    )
    assert _pr_state(pr) == ("open", "approved")


def test_a_pull_request_nobody_was_asked_to_review_waits_on_nobody():
    assert _pr_state(open_pr()) == ("open", None)


def test_a_merged_pull_request_has_no_review_state():
    assert _pr_state({"merged_at": "2026-11-19T00:00:00Z", "state": "closed"}) == ("merged", None)


def test_a_closed_unmerged_pull_request_has_no_review_state():
    assert _pr_state({"state": "closed", "merged_at": None}) == ("closed_unmerged", None)


def test_reviews_are_fetched_for_open_pull_requests_only():
    """A closed pull request's review state cannot change the answer, so it is
    not asked about -- one fewer API call per closed build."""
    asked = []

    def api(path, *, repo):
        asked.append(path)
        if path.startswith("pulls?state=open"):
            return [
                {
                    "number": 7,
                    "state": "open",
                    "head": {"ref": "claude/b20", "repo": {"full_name": "r"}},
                }
            ]
        if path.startswith("pulls?state=closed"):
            return [
                {
                    "number": 3,
                    "state": "closed",
                    "merged_at": "2026-11-19T00:00:00Z",
                    "head": {"ref": "claude/b02", "repo": {"full_name": "r"}},
                }
            ]
        return []

    found = _pull_requests(api, "r", "v2-build", OWNER)
    assert found["claude/b20"]["_owner"] == OWNER
    assert "pulls/7/reviews?per_page=100" in asked
    assert not any("pulls/3/reviews" in path for path in asked)


# ------------------------------------------------------------- check results


def checks_api(runs):
    def api(path, *, repo):
        return {"check_runs": runs} if "check-runs" in path else []

    return api


def test_all_checks_completed_and_successful_is_green():
    runs = [{"status": "completed", "conclusion": "success"}] * 2
    assert _checks(checks_api(runs), "r", "abc") == "green"


def test_any_failure_is_red():
    runs = [
        {"status": "completed", "conclusion": "success"},
        {"status": "completed", "conclusion": "failure"},
    ]
    assert _checks(checks_api(runs), "r", "abc") == "red"


@pytest.mark.parametrize("conclusion", ["timed_out", "cancelled"])
def test_a_check_that_did_not_finish_cleanly_is_red(conclusion):
    runs = [{"status": "completed", "conclusion": conclusion}]
    assert _checks(checks_api(runs), "r", "abc") == "red"


def test_a_check_still_running_is_pending():
    runs = [
        {"status": "completed", "conclusion": "success"},
        {"status": "in_progress", "conclusion": None},
    ]
    assert _checks(checks_api(runs), "r", "abc") == "pending"


def test_no_checks_at_all_is_pending_not_green():
    """A branch nothing has run on must never read as green: that is the one
    answer that would merge an unchecked build."""
    assert _checks(checks_api([]), "r", "abc") == "pending"


def test_no_commit_to_ask_about_is_pending():
    assert _checks(checks_api([]), "r", "") == "pending"


# ----------------------------------------------------- the status report (5)


@pytest.fixture(scope="module")
def ladder_a():
    return ladder_mod.load(FIXTURES / "ladder_a.yaml")


PHASE0 = ("B01", "B01A", "B02", "B03", "B04", "B05")


def done(*ids):
    return {i: Build(done=True) for i in ids}


def test_the_report_is_three_plain_sentences(ladder_a):
    builds = {
        **done(*PHASE0),
        **done("B06", "B07", "B08"),
        "B09": Build(branch=True, state="needs_review", rounds=1),
    }
    gates = {i: Gate(on_main=True, on_base=True) for i in ("G0", "G1")}
    out = status_report.sentences(ladder_a, Facts(builds=builds, gates=gates), NOW)
    assert len(out) == 3
    assert out[0] == "B09 is waiting to be reviewed, round 1."
    assert out[1] == "Next after that: B10."
    assert out[2] == "Nothing is waiting on you."


def test_the_report_names_what_waits_on_the_founder(ladder_a):
    gates = {"G0": Gate(on_main=True, on_base=True)}
    out = status_report.sentences(ladder_a, Facts(gates=gates), NOW)
    assert "Waiting on you: B01" in out[2]


def test_row_37_an_unknown_status_file_is_named_in_the_notes(ladder_a):
    gates = {i: Gate(on_main=True, on_base=True) for i in ("G0", "G1")}
    facts = Facts(builds=done(*PHASE0), gates=gates, unknown=("B97", "B98"))
    out = status_report.sentences(ladder_a, facts, NOW)
    assert any("B97, B98" in line and "not on this ladder" in line for line in out)


def test_the_report_says_plainly_when_the_loop_cannot_act(ladder_a):
    builds = {
        **done(*PHASE0),
        "B06": Build(branch=True, state="building", lock_at=NOW),
        "B09": Build(branch=True, state="building", lock_at=NOW),
    }
    gates = {i: Gate(on_main=True, on_base=True) for i in ("G0", "G1")}
    out = status_report.sentences(ladder_a, Facts(builds=builds, gates=gates), NOW)
    assert "cannot act" in out[0]
    assert "one active loop build at a time" in out[0]


def test_the_report_carries_no_hashes_or_state_names(ladder_a):
    """It is for a non-technical reader: no jargon, no hashes."""
    builds = {**done(*PHASE0), "B06": Build(branch=True, state="needs_review", rounds=1)}
    gates = {i: Gate(on_main=True, on_base=True) for i in ("G0", "G1")}
    text = " ".join(status_report.sentences(ladder_a, Facts(builds=builds, gates=gates), NOW))
    for jargon in ("needs_review", "changes_requested", "START_BUILD", "sha", "claude/"):
        assert jargon not in text
