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
    git=_git,
    api=_api,
) -> Facts:
    """Collect every fact the decision needs, and nothing else.

    Only branches in *this* repository are looked at: a pull request whose head
    is in a fork is dropped, so a fork can never present itself as a build.
    """
    base = ladder.build_branch
    branches = {
        line.split("\t")[-1].removeprefix("refs/heads/")
        for line in git(repo_dir, "ls-remote", "--heads", "origin").split("\n")
        if line.strip()
    }
    locks = _locks(git, repo_dir, branches)
    prs = _pull_requests(api, repo, base)
    status_on_base = _status_files(git, repo_dir, base)

    known = set(ladder.ids)
    builds: dict[str, Build] = {}
    gates: dict[str, Gate] = {}
    for entry in ladder:
        if entry.gate:
            gates[entry.id] = _gate(entry, git, repo_dir, base, branches, locks, prs)
        else:
            builds[entry.id] = _build(
                entry, ladder, git, repo_dir, base, branches, locks, prs, status_on_base
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
    out: dict[str, tuple[datetime | None, str]] = {}
    for name in branches:
        if not name.startswith("lock/"):
            continue
        body = git(repo_dir, "log", "-1", "--format=%cI%n%B", f"refs/remotes/origin/{name}")
        lines = body.split("\n")
        out[name.removeprefix("lock/").upper()] = (
            _when(lines[0] if lines else ""),
            " ".join(lines[1:]),
        )
    return out


def _pull_requests(api, repo: str, base: str) -> dict[str, dict]:
    """Head branch -> its pull request, forks dropped, newest kept."""
    out: dict[str, dict] = {}
    for state in ("open", "closed"):
        for pr in api(f"pulls?state={state}&base={base}&per_page=100", repo=repo) or []:
            head = pr.get("head") or {}
            if ((head.get("repo") or {}).get("full_name") or "") != repo:
                continue  # a fork: only branches in this repository count
            name = head.get("ref") or ""
            if name not in out:
                out[name] = pr
    return out


def _pr_state(pr: dict | None) -> tuple[str | None, str | None]:
    if not pr:
        return None, None
    if pr.get("merged_at"):
        return "merged", None
    if pr.get("state") == "closed":
        return "closed_unmerged", None
    reviews = pr.get("_reviews") or []
    approved = any(r.get("state") == "APPROVED" for r in reviews)
    if approved:
        return "open", "approved"
    return "open", "waiting_on_founder" if pr.get("_needs_owner_review") else None


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


def _build(entry, ladder, git, repo_dir, base, branches, locks, prs, status_on_base) -> Build:
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
    return Build(
        state=payload.get("state"),
        ticks=int(payload.get("ticks") or 0),
        head=payload.get("head"),
        branch=exists,
        rounds=rounds,
        lock_at=lock_at,
        lock_action=lock_message.strip() or None,
        checks=None,
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
        on_main=bool(git(repo_dir, "ls-tree", "--name-only", "origin/main", report)),
        on_base=bool(git(repo_dir, "ls-tree", "--name-only", f"origin/{base}", report)),
        branch=branch in branches,
        lock_at=lock_at,
        writeup_pr=writeup,
        move_pr=move,
    )


def _halt_issues(api, repo: str, label: str) -> list[dict]:
    issues = api(f"issues?state=all&labels={label}&per_page=100", repo=repo) or []
    out = []
    for issue in issues:
        number = issue.get("number")
        timeline = api(f"issues/{number}/timeline?per_page=100", repo=repo) or []
        out.append({**issue, "timeline": timeline})
    return out


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
