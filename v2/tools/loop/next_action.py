"""What happens next -- decided by an ordinary script, not by an AI.

``decide`` is a pure function of (ladder, facts, now). It does no I/O at all,
which is asserted by a test that imports it with ``subprocess`` and ``socket``
patched to raise. That purity is the point of the design: the AI sessions only
do the work this script names, so "what is the loop doing?" is a question with
one checkable answer.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import ladder as ladder_mod
from facts import Facts

ACTIONS = (
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
)

DEFAULT_LADDER = "docs/v2/build/LADDER.yaml"


class LoopError(RuntimeError):
    """The repository is in a state the loop must not act on. Error exit."""


@dataclass(frozen=True)
class Action:
    kind: str
    id: str | None = None
    model: str | None = None
    branch: str | None = None
    reason: str = ""
    waiting_on_founder: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {**dataclasses.asdict(self), "waiting_on_founder": list(self.waiting_on_founder)}


def decide(ladder: ladder_mod.Ladder, facts: Facts, now: datetime) -> Action:
    """The first thing the loop should do, and why, in one line of plain words."""
    if facts.halted:
        return Action(
            "NONE",
            reason=(
                f"an emergency stop is in force: an issue labelled {ladder.halt_label} "
                "that the repository's owner has not ended. Nothing runs until he does."
            ),
        )
    if facts.base_checks == "red":
        return Action(
            "HALT",
            reason=(
                f"the checks are red on {ladder.build_branch} itself, so something "
                "merged that should not have. Everything stops until that is fixed."
            ),
        )

    waiting: list[str] = []
    in_flight: list = []
    actionable: Action | None = None

    for entry in ladder:
        if _is_done(entry, facts):
            continue
        if not all(_is_done_id(need, ladder, facts) for need in entry.needs):
            continue

        if entry.gate:
            action = _for_gate(entry, ladder, facts, now)
        elif entry.needs_the_founder:
            # Never started, resumed, reviewed, merged or counted as active by
            # the loop, however stale its lock (red-team second pass, finding 9).
            action = Action(
                "WAIT_FOUNDER", entry.id, reason=f"{entry.id} needs you present; the loop never runs it."
            )
        elif _in_flight(entry, facts):
            in_flight.append(entry)
            continue
        else:
            action = _for_parked_or_start(entry, ladder, facts, now)

        if action.kind == "WAIT_FOUNDER":
            waiting.append(entry.id)
        elif actionable is None:
            actionable = action

    loop_builds = ", ".join(e.id for e in in_flight)
    if len(in_flight) > 1:
        raise LoopError(
            f"one active loop build at a time, and {loop_builds} are all active. "
            "The loop finishes one build before starting another, so this is a "
            "state it must not act on."
        )

    if in_flight:
        return _with_waiting(_for_build(in_flight[0], ladder, facts, now), waiting)
    if actionable is not None:
        return _with_waiting(actionable, waiting)
    if waiting:
        first = waiting[0]
        return _with_waiting(
            Action("WAIT_FOUNDER", first, reason=_waiting_reason(first, ladder, facts, now)),
            waiting,
        )
    return Action("NONE", reason="nothing on the ladder is runnable and nothing waits on you.")


# --------------------------------------------------------------------------


def _with_waiting(action: Action, waiting: list[str]) -> Action:
    return dataclasses.replace(action, waiting_on_founder=tuple(waiting))


def _is_done(entry, facts: Facts) -> bool:
    """A build is done when its status file says ``merged`` on the build branch.
    A gate is done when its report is on ``main``."""
    return facts.gate(entry.id).on_main if entry.gate else facts.build(entry.id).done


def _is_done_id(entry_id: str, ladder, facts: Facts) -> bool:
    entry = ladder.get(entry_id)
    return False if entry is None else _is_done(entry, facts)


def _fresh(at: datetime | None, ladder, now: datetime) -> bool:
    return at is not None and (now - at).total_seconds() < ladder.claim_hours * 3600


def _in_flight(entry, facts: Facts) -> bool:
    build = facts.build(entry.id)
    return bool(build.branch) and not build.parked and build.state != "halted"


def _for_parked_or_start(entry, ladder, facts: Facts, now: datetime) -> Action:
    build = facts.build(entry.id)
    if build.state == "halted":
        return Action(
            "WAIT_FOUNDER", entry.id, reason=_waiting_reason(entry.id, ladder, facts, now)
        )
    if build.parked:
        return Action(
            "WAIT_FOUNDER", entry.id, reason=_waiting_reason(entry.id, ladder, facts, now)
        )
    if entry.is_card:
        return Action(
            "WAIT_FOUNDER",
            entry.id,
            reason=f"{entry.id} has only a card: its spec isn't written yet, so it cannot start.",
        )
    return Action(
        "START_BUILD",
        entry.id,
        entry.model,
        ladder.branch_for(entry.id),
        f"{entry.id} is next: everything it needs is done and nothing else is in flight.",
    )


def _waiting_reason(entry_id: str, ladder, facts: Facts, now: datetime) -> str:
    entry = ladder.get(entry_id)
    if entry is not None and entry.gate:
        # `now`, never the wall clock: `decide` is a pure function of its
        # arguments (Deliver 3), and reading the clock here was one new
        # WAIT_FOUNDER branch away from making it non-deterministic
        # (review B03-r1.md finding 2).
        return _for_gate(entry, ladder, facts, now).reason
    build = facts.build(entry_id)
    if build.state == "halted":
        return f"{entry_id} is halted and waiting for you to clear it; nothing goes around a halt."
    if build.parked:
        return f"{entry_id} is finished and its pull request is waiting only on your review."
    if entry is not None and entry.is_card:
        return f"{entry_id} has only a card: its spec isn't written yet, so it cannot start."
    return f"{entry_id} needs you present; the loop never runs it."


def _for_build(entry, ladder, facts: Facts, now: datetime) -> Action:
    """The build already under way. While one is active, the loop works on it."""
    build = facts.build(entry.id)
    state = build.state
    here = (entry.id, entry.model, ladder.branch_for(entry.id))

    if state in ("building", None):
        if _fresh(build.lock_at, ladder, now):
            return Action("NONE", *here, reason=f"{entry.id} is being built right now; its lock is fresh.")
        allowed = entry.ticks or 0
        if build.ticks >= allowed:
            return Action(
                "HALT",
                *here,
                reason=(
                    f"{entry.id} has used its {allowed} build ticks and is not finished, "
                    "which is an overrun: the estimate was wrong, so it stops rather than "
                    "running on."
                ),
            )
        return Action(
            "RESUME_BUILD",
            *here,
            reason=f"{entry.id}'s lock went stale part-built, so the next session carries on from its last commit.",
        )

    if state == "needs_review":
        if _fresh(build.lock_at, ladder, now):
            return Action("NONE", *here, reason=f"{entry.id} is being reviewed right now; the review lock is fresh.")
        return Action(
            "REVIEW",
            *here,
            reason=f"{entry.id} is built and waiting for a separate session to review it.",
        )

    if state == "changes_requested":
        if build.rounds >= ladder.max_review_rounds:
            return Action(
                "HALT",
                *here,
                reason=(
                    f"{entry.id} has failed review {build.rounds} times, so the spec or the "
                    "approach is wrong rather than the typing."
                ),
            )
        return Action(
            "FIX", *here, reason=f"{entry.id}'s review asked for changes; the builder fixes them once."
        )

    if state in ("passed", "merged"):
        if build.pr == "closed_unmerged":
            return Action(
                "HALT",
                *here,
                reason=f"{entry.id} is finished but its pull request was closed without merging.",
            )
        if build.checks == "red":
            return Action(
                "HALT", *here, reason=f"{entry.id} passed review but its checks are red."
            )
        if build.checks == "green":
            return Action(
                "MERGE",
                *here,
                reason=f"{entry.id} is reviewed and green, so it merges into {ladder.build_branch}.",
            )
        return Action(
            "NONE", *here, reason=f"{entry.id} is reviewed and its checks are still running."
        )

    return Action("NONE", *here, reason=f"{entry.id} is in state {state!r}; nothing to do.")


def _for_gate(entry, ladder, facts: Facts, now: datetime) -> Action:
    gate = facts.gate(entry.id)
    if not entry.needs:
        return Action(
            "WAIT_FOUNDER",
            entry.id,
            reason=f"{entry.id} has nothing before it to audit: approving it is yours alone.",
        )
    if gate.on_base:
        if gate.move_pr == "open":
            return Action(
                "WAIT_FOUNDER",
                entry.id,
                reason=f"{entry.id}'s report is written and the move of main is open for you to approve.",
            )
        if gate.move_pr == "closed_unmerged":
            return Action(
                "WAIT_FOUNDER",
                entry.id,
                reason=f"you refused {entry.id}'s move of main; it is not re-opened automatically.",
            )
        return Action(
            "OPEN_GATE_MOVE",
            entry.id,
            branch=ladder.build_branch,
            reason=f"{entry.id}'s report is on {ladder.build_branch}; the move of main is next.",
        )
    if gate.writeup_pr == "open":
        return Action(
            "WAIT_FOUNDER",
            entry.id,
            reason=f"{entry.id}'s write-up is open for you to read and approve.",
        )
    if gate.writeup_pr == "closed_unmerged":
        return Action(
            "WAIT_FOUNDER",
            entry.id,
            reason=(
                f"you sent {entry.id}'s write-up back. Say what to change in a live session; "
                "that session deletes the gate branch and the audit starts again."
            ),
        )
    branch = f"gate/{entry.id.lower()}"
    if gate.branch and _fresh(gate.lock_at, ladder, now):
        return Action("NONE", entry.id, branch=branch, reason=f"{entry.id}'s audit is running right now.")
    return Action(
        "RUN_GATE_AUDIT",
        entry.id,
        "opus",
        branch,
        f"everything {entry.id} needs is done, so its audit is next.",
    )


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the loop's next action as JSON.")
    parser.add_argument("--ladder", default=DEFAULT_LADDER)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--github-repo", default="vedantgautam1/chronos")
    parser.add_argument("--owner", default="vedantgautam1")
    args = parser.parse_args(argv)

    import facts as facts_mod

    repo_dir = Path(args.repo)
    ladder = ladder_mod.load(args.ladder, spec_root=Path(args.ladder).parent)
    gathered = facts_mod.gather(ladder, repo_dir, args.github_repo, args.owner)
    action = decide(ladder, gathered, datetime.now(UTC))
    payload = action.as_dict()
    if gathered.unknown:
        payload["notes"] = [
            (
                "ignored for this decision: status files for "
                f"{', '.join(gathered.unknown)}, which are not on {args.ladder}"
            )
        ]
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

# A9 attack probe, 23 Nov 2026
