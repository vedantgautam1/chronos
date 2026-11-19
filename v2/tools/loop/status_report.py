"""The same facts as three plain sentences, for the founder.

Deliver 5. The shape the spec asks for:

    B09 is in review, round 1. Next after that: B10. Waiting on you: B20's
    pull request.

Nothing here decides anything; it reads ``decide`` and says what it said. The
founder is non-technical, so these sentences carry no hashes, no state names
and no jargon.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import ladder as ladder_mod
from facts import Facts
from next_action import DEFAULT_LADDER, LoopError, decide

DOING = {
    "START_BUILD": "{id} is about to start",
    "RESUME_BUILD": "{id} is part-built and will be carried on",
    "REVIEW": "{id} is waiting to be reviewed",
    "FIX": "{id} is being fixed after its review",
    "MERGE": "{id} is reviewed and about to be merged",
    "RUN_GATE_AUDIT": "{id}'s audit is about to run",
    "OPEN_GATE_MOVE": "{id} is ready to move main",
    "HALT": "everything is stopped",
    "NONE": "nothing is running",
    "WAIT_FOUNDER": "nothing is running",
}


def sentences(ladder, facts: Facts, now: datetime | None = None) -> list[str]:
    """Three sentences, plus a notes line when something was ignored."""
    now = now or datetime.now(UTC)
    try:
        action = decide(ladder, facts, now)
    except LoopError as exc:
        return [f"The loop cannot act, and will not guess: {exc}"]

    out = [_doing(action, facts) + "."]
    after = _next_after(action, ladder, facts)
    out.append(f"Next after that: {after}." if after else "Nothing follows it yet.")
    out.append(_waiting(action))
    if facts.unknown:
        out.append(
            "Ignored, because they are not on this ladder: status files for "
            f"{', '.join(facts.unknown)}."
        )
    return out


def _doing(action, facts: Facts) -> str:
    text = DOING.get(action.kind, "nothing is running").format(id=action.id)
    if action.kind in ("REVIEW", "FIX"):
        rounds = facts.build(action.id).rounds
        if rounds:
            text += f", round {rounds}"
    if action.kind == "HALT":
        text += f" ({action.reason.rstrip('.')})"
    return text


def _next_after(action, ladder, facts: Facts) -> str | None:
    """The first entry that becomes runnable once this one is done."""
    if action.id is None:
        return None
    done = {e.id for e in ladder if _done(e, facts)} | {action.id}
    seen_current = False
    for entry in ladder:
        if entry.id == action.id:
            seen_current = True
            continue
        if not seen_current or entry.id in done or _done(entry, facts):
            continue
        if all(need in done for need in entry.needs):
            return entry.id
    return None


def _done(entry, facts: Facts) -> bool:
    return facts.gate(entry.id).on_main if entry.gate else facts.build(entry.id).done


def _waiting(action) -> str:
    if not action.waiting_on_founder:
        return "Nothing is waiting on you."
    return f"Waiting on you: {', '.join(action.waiting_on_founder)}."


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin wrapper
    parser = argparse.ArgumentParser(description="Say where things stand, in plain words.")
    parser.add_argument("--ladder", default=DEFAULT_LADDER)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--github-repo", default="vedantgautam1/chronos")
    parser.add_argument("--owner", default="vedantgautam1")
    args = parser.parse_args(argv)

    import facts as facts_mod

    ladder = ladder_mod.load(args.ladder, spec_root=Path(args.ladder).parent)
    gathered = facts_mod.gather(ladder, Path(args.repo), args.github_repo, args.owner)
    print(" ".join(sentences(ladder, gathered, datetime.now(UTC))))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
