"""B03 round 2 -- the collector that feeds the emergency stop.

Round 1's row tests handed the issues straight to ``halt_in_force``, so all 278
passed while ``_halt_issues`` could not supply it: the collector asked GitHub
for issues **currently carrying** the halt label, so removing the label -- or
deleting it from the repository -- made the issue invisible and the stop
evaporated (review ``B03-r1.md`` finding 1). Rows 30b and 30c say it must not.

Every test here goes through ``_halt_issues``, and two go through ``gather``,
because that is the seam the defect lived in. The review's closing note names
it exactly: nothing in round 1 asserted that ``gather`` produces the facts the
rows describe, which is why three collector defects in this one build were all
invisible to the suite.

The fake GitHub below paginates the way the REST API does, because a
single-page read is the second half of the same defect: this repository's
issue-events feed already spans 15 pages at ``per_page=5``, and an issue's
timeline grows with every comment.
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path

import facts as facts_mod
import ladder as ladder_mod
import pytest
from conftest import FIXTURES
from facts import _halt_issues, gather, halt_in_force

OWNER = "vedantgautam1"
BOT = "chronos-automation"
LABEL = "chronos-halt"
OTHER_LABEL = "bug"
REPO = "vedantgautam1/chronos"


# --------------------------------------------------------------- a fake GitHub


class FakeGitHub:
    """Faithful in the two ways that matter: ``labels=`` filters on an issue's
    *current* labels, and every collection endpoint paginates.

    ``page_size`` is how many items this fake serves per page, so a test can
    put an event on page two by setting it to 1. Requests are recorded, so a
    test can assert which pages were actually read.
    """

    def __init__(self, issues=(), events=(), timelines=None, page_size=100):
        self.issues = list(issues)  # each with number, state and *current* labels
        self.events = list(events)  # the repository-wide issue-events feed
        self.timelines = dict(timelines or {})
        self.page_size = page_size
        self.asked: list[str] = []

    def __call__(self, path, *, repo):
        self.asked.append(path)
        route, _, query = path.partition("?")
        params = urllib.parse.parse_qs(query)
        page = int(params.get("page", ["1"])[0])
        per_page = min(int(params.get("per_page", ["100"])[0]), self.page_size)

        if route == "issues":
            wanted = params.get("labels", [None])[0]
            state = params.get("state", ["open"])[0]
            rows = [
                issue
                for issue in self.issues
                if (state == "all" or issue.get("state", "open") == state)
                and (wanted is None or wanted in issue.get("labels", []))
            ]
        elif route == "issues/events":
            rows = self.events
        elif route.startswith("issues/") and route.endswith("/timeline"):
            rows = self.timelines.get(int(route.split("/")[1]), [])
        else:
            rows = []

        start = (page - 1) * per_page
        return list(rows[start : start + per_page])


def labelled_event(number: int, label: str = LABEL, who: str = BOT) -> dict:
    """One ``labeled`` entry of the repository-wide issue-events feed."""
    return {
        "event": "labeled",
        "label": {"name": label},
        "issue": {"number": number},
        "actor": {"login": who},
    }


def tl(kind: str, who: str, label: str = LABEL) -> dict:
    """One timeline event. Label events carry the label; others do not."""
    event = {"event": kind, "actor": {"login": who}}
    if kind in ("labeled", "unlabeled"):
        event["label"] = {"name": label}
    return event


def row_30b_github(page_size: int = 100) -> FakeGitHub:
    """The automation removed the label from the issue, so no issue carries it
    now; the events feed and the timeline both still record that it was put on.
    """
    return FakeGitHub(
        issues=[{"number": 5, "state": "closed", "labels": []}],
        events=[labelled_event(5)],
        timelines={5: [tl("labeled", OWNER), tl("unlabeled", BOT)]},
        page_size=page_size,
    )


@pytest.fixture(scope="module")
def ladder_a():
    return ladder_mod.load(FIXTURES / "ladder_a.yaml")


def fake_git(repo_dir, *args):
    """Just enough ``git`` for ``gather``: one branch, no locks, no statuses."""
    if args[:1] == ("ls-remote",):
        return "4798115e9442\trefs/heads/v2-build"
    if args[:1] == ("rev-parse",):
        return "4798115e9442"
    return ""


# ------------------------------------------- rows 30b and 30c, at the collector


def test_row_30b_a_label_the_automation_removed_is_still_gathered():
    """Row 30b, measured where it failed. The label is off the issue, so the
    ``labels=`` query cannot see it; the stop must survive anyway."""
    api = row_30b_github()
    gathered = _halt_issues(api, REPO, LABEL)
    assert [issue["number"] for issue in gathered] == [5]
    assert halt_in_force(gathered, OWNER) is True


def test_row_30c_a_label_deleted_from_the_repository_is_still_gathered():
    """Row 30c. The label no longer exists at all, so no issue can carry it;
    the ``labeled`` event in the feed still names it."""
    api = FakeGitHub(
        issues=[{"number": 7, "state": "open", "labels": []}],
        events=[labelled_event(7, who=OWNER)],
        timelines={7: [tl("labeled", OWNER)]},
    )
    gathered = _halt_issues(api, REPO, LABEL)
    assert [issue["number"] for issue in gathered] == [7]
    assert halt_in_force(gathered, OWNER) is True


# ------------------------------------- rows 30 and 31 must keep working (both)


def test_row_30_closed_by_the_automation_is_still_a_stop_through_the_collector():
    api = FakeGitHub(
        issues=[{"number": 3, "state": "closed", "labels": [LABEL]}],
        events=[labelled_event(3)],
        timelines={3: [tl("labeled", BOT), tl("closed", BOT)]},
    )
    assert halt_in_force(_halt_issues(api, REPO, LABEL), OWNER) is True


def test_row_31_the_owner_ending_a_stop_still_ends_it_through_the_collector():
    """The half that stops this becoming an unliftable stop: the issue is
    gathered **and** correctly read as no longer in force."""
    api = FakeGitHub(
        issues=[{"number": 4, "state": "closed", "labels": []}],
        events=[labelled_event(4)],
        timelines={4: [tl("labeled", BOT), tl("unlabeled", OWNER)]},
    )
    gathered = _halt_issues(api, REPO, LABEL)
    assert [issue["number"] for issue in gathered] == [4]
    assert halt_in_force(gathered, OWNER) is False


def test_row_31_the_owner_closing_the_issue_still_ends_it_through_the_collector():
    api = FakeGitHub(
        issues=[{"number": 6, "state": "closed", "labels": [LABEL]}],
        events=[labelled_event(6)],
        timelines={6: [tl("labeled", BOT), tl("closed", OWNER)]},
    )
    assert halt_in_force(_halt_issues(api, REPO, LABEL), OWNER) is False


# ------------------------------------------------------------------ pagination


def test_a_labelled_event_on_the_second_page_is_still_found():
    """The hand-over's named weakness in the proposed patch. A one-page read of
    the events feed degrades back toward the bug as the repository fills up."""
    api = FakeGitHub(
        issues=[{"number": 9, "state": "open", "labels": []}],
        events=[
            {"event": "closed", "issue": {"number": 1}, "actor": {"login": BOT}},
            labelled_event(9),
        ],
        timelines={9: [tl("labeled", BOT)]},
        page_size=1,
    )
    gathered = _halt_issues(api, REPO, LABEL)
    assert [issue["number"] for issue in gathered] == [9]
    assert halt_in_force(gathered, OWNER) is True
    assert any("issues/events" in path and "page=2" in path for path in api.asked)


def test_the_timeline_is_read_past_its_first_page():
    """A stop begun after a hundred comments is still a stop: the ``labeled``
    event sits on a later page of the timeline, and the timeline paginates --
    issue 32 of this repository already spans four pages at ``per_page=5``."""
    api = FakeGitHub(
        issues=[{"number": 11, "state": "open", "labels": [LABEL]}],
        events=[labelled_event(11)],
        timelines={11: [tl("commented", BOT), tl("labeled", OWNER)]},
        page_size=1,
    )
    assert halt_in_force(_halt_issues(api, REPO, LABEL), OWNER) is True


def test_an_owner_ending_a_stop_on_a_later_timeline_page_still_ends_it():
    """The same pagination, in the direction that must not strand a stop."""
    api = FakeGitHub(
        issues=[{"number": 12, "state": "open", "labels": [LABEL]}],
        events=[labelled_event(12)],
        timelines={
            12: [tl("labeled", BOT), tl("commented", BOT), tl("unlabeled", OWNER)]
        },
        page_size=1,
    )
    assert halt_in_force(_halt_issues(api, REPO, LABEL), OWNER) is False


def test_a_feed_too_long_to_read_is_an_error_not_a_short_read():
    """Fail closed. A truncated halt feed reads as "no stop", which is the one
    answer that must never be guessed, so an unreadable feed is an error exit.
    """

    def endless(path, *, repo):
        if not path.startswith("issues/events"):
            return []
        per_page = int(
            urllib.parse.parse_qs(path.partition("?")[2]).get("per_page", ["100"])[0]
        )
        return [labelled_event(1)] * per_page

    with pytest.raises(facts_mod.FactsError, match="more than"):
        _halt_issues(endless, REPO, LABEL)


# ------------------------------------------------- which label, and which state


def test_an_owner_removing_a_different_label_does_not_end_the_stop():
    """The rule is about *this* label. An issue may carry several, and
    ``halt_in_force`` reads any ``unlabeled`` event as being about the stop, so
    the owner tidying an unrelated label would otherwise lift an emergency
    stop he never touched."""
    api = FakeGitHub(
        issues=[{"number": 13, "state": "open", "labels": [LABEL]}],
        events=[labelled_event(13)],
        timelines={
            13: [
                tl("labeled", BOT),
                tl("labeled", OWNER, label=OTHER_LABEL),
                tl("unlabeled", OWNER, label=OTHER_LABEL),
            ]
        },
    )
    assert halt_in_force(_halt_issues(api, REPO, LABEL), OWNER) is True


def test_another_label_alone_is_not_a_stop():
    """The positive control for the filter: an issue labelled only ``bug`` must
    not read as an emergency stop."""
    api = FakeGitHub(
        issues=[{"number": 14, "state": "open", "labels": [OTHER_LABEL]}],
        events=[labelled_event(14, label=OTHER_LABEL)],
        timelines={14: [tl("labeled", OWNER, label=OTHER_LABEL)]},
    )
    assert halt_in_force(_halt_issues(api, REPO, LABEL), OWNER) is False


def test_a_label_event_whose_name_cannot_be_read_keeps_the_stop():
    """Fail closed on a payload surprise. If GitHub ever stops naming the label
    the way it documents, an unreadable label event must leave a stop standing
    rather than quietly cancelling it."""
    api = FakeGitHub(
        issues=[],
        events=[{"event": "labeled", "issue": {"number": 15}, "actor": {"login": BOT}}],
        timelines={15: [{"event": "labeled", "actor": {"login": BOT}}]},
    )
    assert halt_in_force(_halt_issues(api, REPO, LABEL), OWNER) is True


def test_the_candidate_set_is_not_bounded_by_issue_state():
    """Rows 30b and 30c say nothing about whether the issue is open or closed,
    so ``state=open`` would miss cases."""
    api = row_30b_github()
    _halt_issues(api, REPO, LABEL)
    issue_queries = [path for path in api.asked if path.startswith("issues?")]
    assert issue_queries
    assert all("state=all" in path for path in issue_queries)


def test_an_issue_whose_events_have_aged_out_is_still_gathered():
    """Why both halves of the union are kept: an issue that still carries the
    label is gathered even with nothing about it in the events feed."""
    api = FakeGitHub(
        issues=[{"number": 21, "state": "open", "labels": [LABEL]}],
        events=[],
        timelines={21: [tl("labeled", BOT)]},
    )
    gathered = _halt_issues(api, REPO, LABEL)
    assert [issue["number"] for issue in gathered] == [21]
    assert halt_in_force(gathered, OWNER) is True


def test_an_issue_in_both_halves_of_the_union_is_gathered_once():
    api = FakeGitHub(
        issues=[{"number": 22, "state": "open", "labels": [LABEL]}],
        events=[labelled_event(22), labelled_event(22)],
        timelines={22: [tl("labeled", BOT)]},
    )
    assert [issue["number"] for issue in _halt_issues(api, REPO, LABEL)] == [22]


# ------------------------------------------------- the whole way, through gather


def test_gather_reports_a_stop_the_automation_tried_to_lift(ladder_a):
    """The end-to-end assertion round 1 had nowhere: ``gather`` itself, not a
    pure helper handed its facts, must conclude that the stop is in force."""
    facts = gather(ladder_a, Path("."), REPO, OWNER, git=fake_git, api=row_30b_github())
    assert facts.halted is True


def test_gather_reports_no_stop_once_the_owner_has_ended_it(ladder_a):
    api = FakeGitHub(
        issues=[{"number": 4, "state": "closed", "labels": []}],
        events=[labelled_event(4)],
        timelines={4: [tl("labeled", BOT), tl("unlabeled", OWNER)]},
    )
    facts = gather(ladder_a, Path("."), REPO, OWNER, git=fake_git, api=api)
    assert facts.halted is False


def test_gather_reports_no_stop_when_nothing_was_ever_labelled(ladder_a):
    api = FakeGitHub(issues=[{"number": 1, "state": "open", "labels": []}])
    facts = gather(ladder_a, Path("."), REPO, OWNER, git=fake_git, api=api)
    assert facts.halted is False
