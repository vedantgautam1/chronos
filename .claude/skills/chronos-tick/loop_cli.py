#!/usr/bin/env python3
"""The mechanical half of the loop's four commands.

`/chronos-tick`, `/chronos-status`, `/chronos-halt` and `/chronos-resume` share
this one module. It does the deterministic parts — run `next_action.py`, read
its answer, compare models, take and release the lock, open an emergency stop
— and it does **not** do the one part that cannot be code: dispatching a
subagent, which is a Task-tool call the session makes. So each `SKILL.md` runs
this, reads the dispatch line it prints, and makes that call itself.

**Why a helper exists at all.** Five of B04's known answers are behavioural
("`/tick` on the wrong model makes no commit", "opens exactly one
`chronos-halt` issue", "`--ladder X` is passed through"). A `SKILL.md` is
prose, so there would be nothing to assert and nothing for a reviewer to
break. Putting the mechanical parts here makes those five real tests.

**This module never commits and never merges.** It writes exactly one kind of
object: the lock commit, through the injected backend. Everything that changes
the repository is done by the dispatched agent, under its own role trailer.

Every outside edge is an injected argument — `next_action`, `status_report`,
`refs`, `issues` — the way `facts.py` puts `git` and `gh api` behind one
replaceable function each. That is what lets the tests drive it with no
network.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LOOP_DIR = REPO_ROOT / "v2" / "tools" / "loop"
V2_DIR = REPO_ROOT / "v2"
if str(LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(LOOP_DIR))

# Imported after the sys.path insert above, which is the point of it.
from lock import Lock, LockError
from next_action import ACTIONS

HALT_LABEL = "chronos-halt"

# Which agent takes which action. `FIX` is three characters, so a careless
# grep for the action names misses it; the set below is checked against
# next_action's own ACTIONS at import so this map cannot drift from the loop.
BUILDER_KINDS = ("START_BUILD", "RESUME_BUILD", "FIX")
AGENT_FOR_KIND = {
    "REVIEW": "chronos-reviewer",
    "MERGE": "chronos-reviewer",
    "RUN_GATE_AUDIT": "chronos-auditor",
}
NO_DISPATCH = ("WAIT_FOUNDER", "HALT", "NONE", "OPEN_GATE_MOVE")

_covered = set(BUILDER_KINDS) | set(AGENT_FOR_KIND) | set(NO_DISPATCH)
if _covered != set(ACTIONS):  # pragma: no cover - import-time guard
    raise AssertionError(
        "the dispatch map and next_action.ACTIONS disagree: "
        f"only here {sorted(_covered - set(ACTIONS))}, "
        f"only there {sorted(set(ACTIONS) - _covered)}"
    )

MISMATCH = (
    "This build wants {wants}; you are on {on}. Nothing was claimed and "
    "nothing was committed.\nSwitch with /model {wants}, then run "
    "/chronos-tick again."
)
CLAIMED = (
    "claimed, nothing to do. Another session holds the lock on {id}, so this "
    "one stops without pushing."
)
UNREADABLE_LOCK = (
    "claimed, nothing to do. The lock on {id} exists but its age cannot be "
    "read, so it is left alone rather than treated as free -- a lock the loop "
    "cannot judge is the one case where guessing lets two sessions run at "
    "once. This one needs a person to look at it."
)
# The second line is the spec's own wording, quoted in Deliver 3, kept
# verbatim and in its own lower case rather than reflowed into a sentence.
RESUME_REFUSED = (
    "An emergency stop is in force: issue #{n} carries the {label} label.\n"
    "I will not lift it -- close the issue yourself on GitHub; only your "
    "account releases the stop."
)
NO_STOP = "There is no emergency stop in force."


# ----------------------------------------------------------------- the edges


def _run(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    # Fixed argv, never a shell string.
    done = subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True, check=False
    )
    return done.returncode, done.stdout, done.stderr


def real_next_action(passthrough: list[str]) -> tuple[int, str, str]:
    """`next_action.py` as a subprocess, so its exit code is observable.

    Run from `v2/` and **never** with `python -I`: the loop's modules are
    siblings in one folder, and `-I` strips the script's own directory from
    `sys.path`, so `next_action.py`'s `import ladder` fails at once.
    """
    return _run(
        ["uv", "run", "python", "tools/loop/next_action.py", *passthrough], V2_DIR
    )


def real_status_report(passthrough: list[str]) -> tuple[int, str, str]:
    return _run(
        ["uv", "run", "python", "tools/loop/status_report.py", *passthrough], V2_DIR
    )


class GitHubIssues:
    """The emergency stop, over `gh api`. Read-only except for opening one."""

    def __init__(self, repo: str, owner: str, runner=None) -> None:
        self.repo = repo
        self.owner = owner
        self._run = runner or self._gh

    def _gh(self, *args: str, body: dict | None = None) -> tuple[int, str]:
        argv = ["gh", "api", *args]
        if body is not None:
            argv += ["--input", "-"]
        # Fixed argv, never a shell string.
        done = subprocess.run(
            argv,
            input=json.dumps(body) if body is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
        return done.returncode, done.stdout

    def halt_issue(self) -> int | None:
        """The number of an open stop, or None.

        Deliberately the cheap current-label query and nothing more. The
        authoritative read is `facts.halt_in_force`, which goes through each
        issue's timeline because a label can be removed or deleted; this is
        only here so `/chronos-resume` can name an issue in its refusal. It
        fails **closed**: an unreadable answer reports a stop rather than
        none.
        """
        code, out = self._run(
            f"repos/{self.repo}/issues?state=open&labels={HALT_LABEL}&per_page=100"
        )
        if code != 0:
            return -1
        try:
            issues = json.loads(out or "[]")
        except json.JSONDecodeError:
            return -1
        for issue in issues:
            if isinstance(issue, dict) and "pull_request" not in issue:
                return int(issue.get("number", -1))
        return None

    def open_halt_issue(self, body: str) -> int:
        code, out = self._run(
            "-X",
            "POST",
            f"repos/{self.repo}/issues",
            body={
                "title": "chronos-halt: the loop stopped itself",
                "body": body,
                "labels": [HALT_LABEL],
            },
        )
        if code != 0:
            raise RuntimeError(f"could not open a {HALT_LABEL} issue: {out}")
        return int(json.loads(out)["number"])

    # No close_issue, by design: nothing here may end a stop. Red-team second
    # pass, finding 13 -- the automation could close its own emergency stop.


# -------------------------------------------------------------- the commands


def _agent_for(kind: str, model: str | None) -> str | None:
    if kind in BUILDER_KINDS:
        return f"chronos-builder-{model}" if model else None
    return AGENT_FOR_KIND.get(kind)


def _passthrough(args: argparse.Namespace) -> list[str]:
    out: list[str] = []
    if args.ladder:
        out += ["--ladder", args.ladder]
    if args.repo:
        out += ["--repo", args.repo]
    return out


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ladder")
    parser.add_argument("--repo")
    parser.add_argument("--github-repo", default="vedantgautam1/chronos")
    parser.add_argument("--owner", default="vedantgautam1")


def claim(
    argv: list[str],
    *,
    next_action=real_next_action,
    refs=None,
    issues=None,
    now: datetime | None = None,
    session: str | None = None,
) -> tuple[int, str]:
    """Run the loop, check the model, take the lock, say what to dispatch."""
    parser = argparse.ArgumentParser(prog="chronos-tick")
    _common(parser)
    parser.add_argument("--session-model")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args(argv)
    now = now or datetime.now(UTC)
    session = session or args.session_id or f"tick-{now.isoformat()}"
    said: list[str] = []

    code, stdout, stderr = next_action(_passthrough(args))
    if code != 0:
        detail = (stderr or stdout or "").strip() or f"exit {code}, no output"
        standing = issues.halt_issue()
        if standing not in (None, -1):
            said.append(
                f"next_action.py failed and a {HALT_LABEL} issue (#{standing}) is "
                "already open, so no second one was opened."
            )
            return 2, "\n".join(said)
        number = issues.open_halt_issue(
            f"`next_action.py` exited {code}. The loop stopped itself and did "
            f"nothing else.\n\n```\n{detail}\n```"
        )
        said.append(
            f"next_action.py failed, so the loop opened {HALT_LABEL} issue "
            f"#{number} with the error text and stopped. Nothing was claimed "
            "and nothing was committed."
        )
        said.append(detail)
        return 2, "\n".join(said)

    try:
        action = json.loads(stdout)
    except json.JSONDecodeError:
        return 2, f"next_action.py printed something that is not JSON:\n{stdout}"

    kind, build = action.get("kind"), action.get("id")
    said.append(f"{kind} {build or ''}".strip())
    said.append(action.get("reason", ""))
    for waiting in action.get("waiting_on_founder") or []:
        said.append(f"Waiting on you: {waiting}")

    if kind in NO_DISPATCH:
        return 0, "\n".join(s for s in said if s)

    wants, on = action.get("model"), args.session_model
    if wants and on and wants != on:
        said.append(MISMATCH.format(wants=wants, on=on))
        return 3, "\n".join(s for s in said if s)
    if wants and not on:
        said.append(
            f"This build wants {wants}. No --session-model was given, so the "
            "model could not be checked; confirm it yourself before you "
            "dispatch."
        )

    agent = _agent_for(kind, wants)
    if agent is None:
        said.append(f"No agent is defined for {kind} with model {wants!r}.")
        return 2, "\n".join(s for s in said if s)

    lock = Lock(refs=refs, build_id=build, session=session)
    if not lock.acquire(kind.lower(), now):
        try:
            stale = lock.is_stale(now)
        except LockError:
            said.append(UNREADABLE_LOCK.format(id=build))
            return 0, "\n".join(s for s in said if s)
        if not stale or not lock.take_over(kind.lower(), now):
            said.append(CLAIMED.format(id=build))
            return 0, "\n".join(s for s in said if s)
        said.append(f"The lock on {build} was stale, so this session took it over.")

    said.append(
        f"Lock taken. Now dispatch, with the Task tool and nothing else:\n"
        f"  subagent_type: {agent}\n"
        f"  prompt: Do {kind} for {build}. Read your spec from v2-build. "
        f"Follow specs/README.md.\n"
        f"Then run: /chronos-tick finish --build {build}"
    )
    return 0, "\n".join(s for s in said if s)


def finish(
    argv: list[str],
    *,
    status_report=real_status_report,
    refs=None,
    session: str | None = None,
) -> tuple[int, str]:
    """Release the lock and say where things stand."""
    parser = argparse.ArgumentParser(prog="chronos-tick finish")
    _common(parser)
    parser.add_argument("--build", required=True)
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args(argv)
    said: list[str] = []

    lock = Lock(refs=refs, build_id=args.build, session=session or args.session_id or "")
    try:
        lock.release()
        said.append(f"Lock on {args.build} released.")
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        said.append(
            f"The lock on {args.build} could not be released ({exc}). It will "
            "time out on its own; say so rather than assuming it is gone."
        )

    code, stdout, stderr = status_report(_passthrough(args))
    said.append(stdout.strip() if code == 0 else f"status_report failed: {stderr}")
    return 0, "\n".join(s for s in said if s)


def halt(argv: list[str], *, issues=None) -> tuple[int, str]:
    """Open an emergency stop. Only the founder's account can lift it."""
    parser = argparse.ArgumentParser(prog="chronos-halt")
    _common(parser)
    parser.add_argument("--reason", default="Asked for by the founder.")
    args = parser.parse_args(argv)

    standing = issues.halt_issue()
    if standing == -1:
        return 2, (
            "Could not read whether a stop is already in force, so no issue "
            "was opened. Check GitHub yourself."
        )
    if standing is not None:
        return 0, (
            f"An emergency stop is already in force: issue #{standing}. "
            "Nothing more to do."
        )
    number = issues.open_halt_issue(
        f"{args.reason}\n\nEvery session, scheduled or by hand, refuses to act "
        "while this issue is open. Only the repository owner closing it "
        "releases the stop."
    )
    return 0, (
        f"Emergency stop in force: issue #{number} carries the {HALT_LABEL} "
        "label. Every session now refuses to act. Close that issue yourself "
        "when you want the loop back."
    )


def resume(argv: list[str], *, issues=None) -> tuple[int, str]:
    """Turn the loop back on -- but never by lifting a stop.

    Red-team second pass, finding 13: the automation could close its own
    emergency stop. So this command reads the stop and refuses; there is no
    code path here that closes an issue.
    """
    parser = argparse.ArgumentParser(prog="chronos-resume")
    _common(parser)
    args = parser.parse_args(argv)
    del args  # parsed so a bad flag is an error, not silently ignored

    standing = issues.halt_issue()
    if standing == -1:
        return 2, (
            "Could not read whether a stop is in force. Treating that as a "
            "stop: nothing is resumed. Check GitHub yourself."
        )
    if standing is not None:
        return 3, RESUME_REFUSED.format(n=standing, label=HALT_LABEL)
    return 0, (
        f"{NO_STOP} Switch the scheduled task on in the Claude app to let the "
        "loop carry on; that switch is yours and nothing here can touch it."
    )


def status(argv: list[str], *, status_report=real_status_report) -> tuple[int, str]:
    parser = argparse.ArgumentParser(prog="chronos-status")
    _common(parser)
    args = parser.parse_args(argv)
    code, stdout, stderr = status_report(_passthrough(args))
    if code != 0:
        return 2, f"status_report failed: {stderr or stdout}"
    return 0, stdout.strip()


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin wrapper
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: loop_cli.py {claim|finish|halt|resume|status} [...]")
        return 2
    command, rest = argv[0], argv[1:]
    parser = argparse.ArgumentParser(add_help=False)
    _common(parser)
    known, _ = parser.parse_known_args(rest)
    issues = GitHubIssues(known.github_repo, known.owner)

    if command in ("claim", "finish"):
        from lock import GitHubRefs

        refs = GitHubRefs(known.github_repo)
        if command == "claim":
            code, out = claim(rest, refs=refs, issues=issues)
        else:
            code, out = finish(rest, refs=refs)
    elif command == "halt":
        code, out = halt(rest, issues=issues)
    elif command == "resume":
        code, out = resume(rest, issues=issues)
    elif command == "status":
        code, out = status(rest)
    else:
        print(f"unknown command {command!r}")
        return 2
    print(out)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
