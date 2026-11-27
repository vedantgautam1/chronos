"""What the repository currently says -- and nothing else.

This module gathers facts. It makes no decisions: that is ``next_action.decide``,
which is pure so that "what is the loop doing?" has one checkable answer.

``git`` and ``gh api`` sit behind one small function each (``_git`` and ``_api``)
which the tests replace. REST only: no GraphQL.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lock import is_release_marker

MAIN_BRANCH = "main"  # a gate is done when its report is on main; the move targets it
STATES = ("building", "needs_review", "changes_requested", "passed", "merged", "halted")
STATUS_KEYS = ("build", "state", "ticks", "head", "halt_reason", "halt_options")
PARKED_STATES = ("passed", "merged")


class FactsError(RuntimeError):
    """A fact could not be established. Halt, never pass."""


@dataclass(frozen=True)
class Build:
    """One build, as the repository and GitHub describe it."""

    state: str | None = None  # None: no status file yet
    ticks: int = 0
    head: str | None = None
    branch: bool = False  # claude/<id> exists
    rounds: int = 0  # review files on the branch, counted by this script
    lock_at: datetime | None = None  # the holder's own last lock commit time
    lock_action: str | None = None
    checks: str | None = None  # green | pending | red
    pr: str | None = None  # open | merged | closed_unmerged
    pr_review: str | None = None  # None | waiting_on_founder | approved
    done: bool = False  # status file with state `merged` on the build branch

    @property
    def parked(self) -> bool:
        """Review finished, checks green, waiting only on the founder's review.

        Such a build blocks only the builds that need it. The reviewer has
        already pushed its last commit, because a push after the founder's
        approval cancels that approval (red-team third pass, finding a).
        """
        return (
            self.pr_review == "waiting_on_founder"
            and self.checks == "green"
            and self.state in PARKED_STATES
        )


@dataclass(frozen=True)
class Gate:
    """One gate. A gate is done when its report is on ``main``."""

    on_main: bool = False
    on_base: bool = False
    branch: bool = False  # gate/gN exists
    lock_at: datetime | None = None
    writeup_pr: str | None = None  # open | merged | closed_unmerged
    move_pr: str | None = None


@dataclass(frozen=True)
class Facts:
    builds: dict[str, Build] = field(default_factory=dict)
    gates: dict[str, Gate] = field(default_factory=dict)
    halted: bool = False  # a chronos-halt stop is in force
    base_checks: str = "green"  # on the build branch head itself
    unknown: tuple[str, ...] = ()  # status files for ids not on this ladder

    def build(self, build_id: str) -> Build:
        return self.builds.get(build_id, Build())

    def gate(self, gate_id: str) -> Gate:
        return self.gates.get(gate_id, Gate())


def validate_status(payload: object, path: str = "a status file") -> dict:
    """The status-file schema (Deliver 6). An invalid file is an error exit."""
    if not isinstance(payload, dict):
        raise FactsError(f"{path} is not a JSON object")
    missing = [k for k in STATUS_KEYS if k not in payload]
    if missing:
        raise FactsError(f"{path} is missing {', '.join(missing)}")
    extra = [k for k in payload if k not in STATUS_KEYS]
    if extra:
        raise FactsError(f"{path} has unexpected key(s) {', '.join(sorted(extra))}")
    if payload["state"] not in STATES:
        raise FactsError(
            f"{path} has state {payload['state']!r}; allowed are {', '.join(STATES)}"
        )
    if not isinstance(payload["ticks"], int) or isinstance(payload["ticks"], bool):
        raise FactsError(f"{path} has a non-integer ticks: {payload['ticks']!r}")
    if payload["ticks"] < 0:
        raise FactsError(f"{path} has a negative ticks: {payload['ticks']!r}")
    if not isinstance(payload["build"], str) or not payload["build"]:
        raise FactsError(f"{path} has no build id")
    return payload


def halt_in_force(issues: list[dict], owner: str) -> bool:
    """Is an emergency stop in force?

    Read from each issue's **timeline**, not its current labels, because the
    automation's own account can remove a label or delete it from the
    repository (red-team third pass, finding e). A stop begins when the halt
    label is put on an issue by anyone. It ends **only** when the repository's
    owner closes that issue or removes the label. Any other account closing it,
    unlabelling it, or deleting the label leaves the stop in force.

    This is a guard rail, not a wall: it is enforced by this script, which the
    automation's own sessions run. The switches nothing can override are the
    founder's -- turning the scheduled task off, and removing the automation's
    account from the repository.
    """
    for issue in issues:
        labelled = False
        ended_by_owner = False
        for event in issue.get("timeline", []):
            actor = ((event.get("actor") or {}).get("login") or "").lower()
            kind = event.get("event")
            by_owner = actor == owner.lower()
            if kind == "labeled":
                labelled = True
                ended_by_owner = False
            elif kind in ("unlabeled", "closed") and by_owner:
                ended_by_owner = True
        if labelled and not ended_by_owner:
            return True
    return False


# --------------------------------------------------------------------------
# The two functions that touch the outside world. Tests replace these.
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ("git", "-C", str(repo)) + args, capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def _api(path: str, *, repo: str) -> object:
    """``gh api`` -- REST only, never GraphQL."""
    done = subprocess.run(
        ("gh", "api", f"repos/{repo}/{path}"), capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise FactsError(f"gh api {path} failed: {done.stderr.strip()[:200]}")
    return json.loads(done.stdout or "null")


# GitHub serves at most 100 items a page on every collection endpoint, and one
# page is not enough for any of the three the emergency stop reads: this
# repository's issue-events feed already spans 15 pages at ``per_page=5``, and
# an issue's timeline grows with every comment (issue 32's spans 4). A
# collector that stops at page one quietly loses the oldest ``labeled`` event
# as the repository fills up, which is review B03-r1.md finding 1 again.
_PER_PAGE = 100
_MAX_PAGES = 100  # 10,000 items; past that, fail closed rather than truncate


def _pages(api, path: str, *, repo: str) -> list[dict]:
    """Every item of a paginated REST collection, not just the first page.

    Stops on an **empty** page, not on a page shorter than ``per_page``. The
    short-page rule is the obvious one and it is wrong here: it assumes the
    server returns exactly as many items as were asked for, and a server that
    returns 99 for a request of 100 would end the read silently one page early
    -- which is the same quiet truncation this helper exists to prevent. The
    terminator costs one extra call per feed and is confirmed against this
    repository, where page 2 of the issue-events feed returns ``[]``. Reading
    the ``Link`` header would be cheaper, but ``_api`` returns a parsed body
    and giving it headers would change the seam every test replaces.

    Fails **closed**. A feed that cannot be read to its end raises rather than
    returning the part it managed, because a short read of the halt feed reads
    as "no emergency stop" -- the one answer that must never be guessed. Same
    direction as ``lock.is_stale``, which raises rather than calling a lock it
    cannot judge free.
    """
    joiner = "&" if "?" in path else "?"
    out: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        batch = api(f"{path}{joiner}per_page={_PER_PAGE}&page={page}", repo=repo) or []
        if not isinstance(batch, list):
            raise FactsError(f"{path} page {page} is not a list of items")
        if not batch:
            return out
        out.extend(batch)
    raise FactsError(
        f"{path} has more than {_MAX_PAGES * _PER_PAGE} items, so it cannot be read "
        "to its end; refusing to read it in part, because a short read of the halt "
        "feed would read as no stop"
    )


def _when(text: str) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).astimezone(UTC)
    except ValueError:
        return None


def gather(
    ladder,
    repo_dir: Path,
    repo: str,
    owner: str,
    git=None,
    api=None,
) -> Facts:
    """Collect every fact the decision needs, and nothing else.

    Only branches in *this* repository are looked at: a pull request whose head
    is in a fork is dropped, so a fork can never present itself as a build.

    ``git`` and ``api`` are resolved here rather than as default arguments so
    that a caller -- a test, or the step 6 dry run -- can replace the module's
    ``_git``/``_api`` and have this function use the replacement.
    """
    git = git or _git
    api = api or _api
    base = ladder.build_branch
    branches = {
        line.split("\t")[-1].removeprefix("refs/heads/")
        for line in git(repo_dir, "ls-remote", "--heads", "origin").split("\n")
        if line.strip()
    }
    locks = _locks(git, repo_dir, branches)
    prs = _pull_requests(api, repo, base, owner)
    status_on_base = _status_files(git, repo_dir, base)

    known = set(ladder.ids)
    builds: dict[str, Build] = {}
    gates: dict[str, Gate] = {}
    for entry in ladder:
        if entry.gate:
            gates[entry.id] = _gate(entry, git, repo_dir, base, branches, locks, prs)
        else:
            builds[entry.id] = _build(
                entry, ladder, git, api, repo, repo_dir, branches, locks, prs, status_on_base
            )

    issues = _halt_issues(api, repo, ladder.halt_label)
    return Facts(
        builds=builds,
        gates=gates,
        halted=halt_in_force(issues, owner),
        base_checks=_checks(api, repo, git(repo_dir, "rev-parse", f"origin/{base}")),
        unknown=tuple(sorted(set(status_on_base) - known)),
    )


def _locks(git, repo_dir: Path, branches: set[str]) -> dict[str, tuple[datetime | None, str]]:
    """Every ``lock/<id>`` branch that is held, aged by its tip's commit time.

    A released lock (B05A) is a branch whose tip is a release marker: a cloud
    session cannot delete a branch, so release moves it onto a marker instead.
    Such a branch is **not** a lock. Everything else is read as before --
    including an unreadable tip, which stays a lock rather than becoming free.
    """
    out: dict[str, tuple[datetime | None, str]] = {}
    for name in branches:
        if not name.startswith("lock/"):
            continue
        body = git(repo_dir, "log", "-1", "--format=%cI%n%B", f"refs/remotes/origin/{name}")
        lines = body.split("\n")
        if is_release_marker("\n".join(lines[1:])):
            continue
        out[name.removeprefix("lock/").upper()] = (
            _when(lines[0] if lines else ""),
            " ".join(lines[1:]),
        )
    return out


def _pull_requests(api, repo: str, base: str, owner: str = "") -> dict[str, dict]:
    """Head branch -> its pull request, forks dropped, newest kept.

    An open pull request's reviews are fetched too, because "waiting on
    code-owner review" is a fact the decision needs (rows 28-28c) and it cannot
    be read off the pull request itself. Closed and merged ones are not asked
    about: their review state cannot change the answer.

    **Two bases, not one.** A gate takes two pull requests: the write-up
    (``gate/gN`` into the build branch) and then the move (the build branch
    into ``main``). ``_gate`` reads the move as the pull request whose *head*
    is the build branch -- and a branch cannot target itself, so querying
    ``base=v2-build`` alone can never return it. ``move_pr`` was therefore
    always ``None`` and rows 8 and 8b were unreachable through ``gather``:
    measured, an open move gave ``OPEN_GATE_MOVE`` where row 8 says
    ``WAIT_FOUNDER``, so the loop would open a second move over an open one and
    re-open a move the founder had refused. Same shape as finding 1 -- a
    correct rule wired to a collector that cannot feed it.

    ``state`` stays the outer loop so an open pull request still beats a closed
    one for the same head branch, whichever base each came in on.
    """
    out: dict[str, dict] = {}
    for state in ("open", "closed"):
        for target in (base, MAIN_BRANCH):
            for pr in api(f"pulls?state={state}&base={target}&per_page=100", repo=repo) or []:
                head = pr.get("head") or {}
                if ((head.get("repo") or {}).get("full_name") or "") != repo:
                    continue  # a fork: only branches in this repository count
                name = head.get("ref") or ""
                if name in out:
                    continue
                if state == "open" and not pr.get("merged_at"):
                    pr = {
                        **pr,
                        "_reviews": api(
                            f"pulls/{pr.get('number')}/reviews?per_page=100", repo=repo
                        )
                        or [],
                        "_owner": owner,
                    }
                out[name] = pr
    return out


def _pr_state(pr: dict | None) -> tuple[str | None, str | None]:
    """(pull-request state, review state).

    The review half answers one question: is this pull request waiting only on
    the founder? The founder is the sole code owner, so "waiting on him" means
    he is a requested reviewer and has not yet approved. Once he has approved
    the build is no longer parked and the loop merges it **without pushing
    again**, because a push after his approval cancels it (red-team third pass,
    finding a).
    """
    if not pr:
        return None, None
    if pr.get("merged_at"):
        return "merged", None
    if pr.get("state") == "closed":
        return "closed_unmerged", None

    owner = (pr.get("_owner") or "").lower()
    latest: dict[str, str] = {}
    for review in pr.get("_reviews") or []:
        state = review.get("state") or ""
        if state == "COMMENTED":
            continue  # a comment is not a verdict and never replaces one
        who = ((review.get("user") or {}).get("login") or "").lower()
        latest[who] = state
    if owner and latest.get(owner) == "APPROVED":
        return "open", "approved"

    requested = {
        (r.get("login") or "").lower() for r in pr.get("requested_reviewers") or []
    }
    if owner and owner in requested:
        return "open", "waiting_on_founder"
    return "open", None


def _status_files(git, repo_dir: Path, ref: str) -> dict[str, dict]:
    """Every ``status/<id>.json`` on ``ref``, validated against the schema."""
    listing = git(repo_dir, "ls-tree", "--name-only", f"origin/{ref}", "docs/v2/build/status/")
    out: dict[str, dict] = {}
    for path in [p for p in listing.split("\n") if p.endswith(".json")]:
        text = git(repo_dir, "show", f"origin/{ref}:{path}")
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise FactsError(f"{path} on {ref} is not valid JSON: {exc}") from exc
        out[validate_status(payload, path)["build"]] = payload
    return out


def _build(
    entry, ladder, git, api, repo, repo_dir, branches, locks, prs, status_on_base
) -> Build:
    branch = ladder.branch_for(entry.id)
    exists = branch in branches
    payload: dict = {}
    if exists:
        text = git(repo_dir, "show", f"origin/{branch}:docs/v2/build/status/{entry.id}.json")
        if text:
            try:
                payload = validate_status(json.loads(text), f"status/{entry.id}.json")
            except json.JSONDecodeError as exc:
                raise FactsError(f"status/{entry.id}.json is not valid JSON: {exc}") from exc
    lock_at, lock_message = locks.get(entry.id, (None, ""))
    pr, pr_review = _pr_state(prs.get(branch))
    reviews = git(
        repo_dir, "ls-tree", "--name-only", f"origin/{branch}", "docs/v2/build/reviews/"
    )
    rounds = len(
        [p for p in reviews.split("\n") if p and f"/{entry.id.lower()}-r" in p.lower()]
    )
    on_base = status_on_base.get(entry.id) or {}
    # The checks on the branch head itself, which rows 18-21 turn on. Only
    # asked for when the branch exists: there is nothing to ask about otherwise.
    head_sha = git(repo_dir, "rev-parse", f"origin/{branch}") if exists else ""
    return Build(
        state=payload.get("state"),
        ticks=int(payload.get("ticks") or 0),
        head=payload.get("head"),
        branch=exists,
        rounds=rounds,
        lock_at=lock_at,
        lock_action=lock_message.strip() or None,
        checks=_checks(api, repo, head_sha) if exists else None,
        pr=pr,
        pr_review=pr_review,
        done=on_base.get("state") == "merged",
    )


def _gate(entry, git, repo_dir, base, branches, locks, prs) -> Gate:
    report = f"docs/v2/build/gates/{entry.id}-report.md"
    branch = f"gate/{entry.id.lower()}"
    writeup, _ = _pr_state(prs.get(branch))
    move, _ = _pr_state(prs.get(base))
    lock_at, _ = locks.get(entry.id, (None, ""))
    # `ls-tree` prints the path when it exists and nothing when it does not.
    # `cat-file -e` would be the obvious call and is wrong here: it prints
    # nothing either way, so through `_git` -- which returns "" on failure --
    # a missing report would be indistinguishable from a present one.
    return Gate(
        on_main=bool(git(repo_dir, "ls-tree", "--name-only", f"origin/{MAIN_BRANCH}", report)),
        on_base=bool(git(repo_dir, "ls-tree", "--name-only", f"origin/{base}", report)),
        branch=branch in branches,
        lock_at=lock_at,
        writeup_pr=writeup,
        move_pr=move,
    )


def _halt_issues(api, repo: str, label: str) -> list[dict]:
    """Every issue the halt label was ever put on -- not every issue carrying it now.

    ``issues?labels=`` filters on an issue's **current** labels, so on its own
    it lets the automation's own account end a stop by taking the label off the
    issue, or by deleting the label from the repository: exactly what rows 30b
    and 30c forbid (review B03-r1.md finding 1). The repository's issue-events
    feed names every ``labeled`` event with its label, so the union of the two
    gives the candidate issues, and each candidate's timeline then decides.

    **Both halves are kept.** The events feed is the half that survives the
    label being removed or deleted. The ``labels=`` query is the half that
    survives an issue whose events have aged out of the feed, if GitHub's
    retention ever bites. Neither is bounded by issue state: rows 30b and 30c
    do not say whether the issue is open or closed.

    The timeline handed on is filtered to **this** label. An issue may carry
    several, and ``halt_in_force`` reads any ``labeled``/``unlabeled`` event as
    being about the stop, so without the filter the owner tidying an unrelated
    label would end an emergency stop he never touched.

    Every call is read to its last page, and a label name that cannot be read
    is treated as a match rather than skipped, so both failure directions leave
    a stop standing instead of silently cancelling it.
    """
    candidates: dict[int, dict] = {}
    for issue in _pages(api, f"issues?state=all&labels={label}", repo=repo):
        if issue.get("number") is not None:
            candidates[issue["number"]] = issue
    for event in _pages(api, "issues/events", repo=repo):
        if event.get("event") != "labeled" or not _is_label(event, label):
            continue
        number = (event.get("issue") or {}).get("number")
        if number is not None:
            candidates.setdefault(number, {"number": number})
    out = []
    for number in sorted(candidates):
        timeline = _pages(api, f"issues/{number}/timeline", repo=repo)
        out.append({**candidates[number], "timeline": _about(timeline, label)})
    return out


def _is_label(event: dict, label: str) -> bool:
    """Does this label event concern *this* label?

    An event whose label cannot be read counts as a match: fail closed, so a
    change in GitHub's payload leaves a stop standing rather than lifting it.
    """
    name = (event.get("label") or {}).get("name")
    return name is None or name == label


def _about(timeline: list[dict], label: str) -> list[dict]:
    """The timeline events that bear on *this* label's stop.

    A ``labeled`` or ``unlabeled`` event for a different label is dropped.
    Everything else passes through untouched -- ``closed`` above all, which
    ends a stop when the owner does it whatever the labels say.
    """
    return [
        event
        for event in timeline
        if event.get("event") not in ("labeled", "unlabeled") or _is_label(event, label)
    ]


def _checks(api, repo: str, sha: str) -> str:
    if not sha:
        return "pending"
    runs = (api(f"commits/{sha}/check-runs?per_page=100", repo=repo) or {}).get("check_runs") or []
    if not runs:
        return "pending"
    if any(r.get("conclusion") in ("failure", "timed_out", "cancelled") for r in runs):
        return "red"
    if any(r.get("status") != "completed" for r in runs):
        return "pending"
    return "green"
