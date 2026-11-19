"""Read and validate a ladder file.

The ladder is the loop's only statement of what work exists and in what order.
Everything else in this folder reads it; nothing else writes it. A ladder that
does not validate is a halt, never a pass: the loop would otherwise decide what
to do next from a file it had not understood.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

TICKS_FOR_SIZE = {"S": 2, "M": 3}  # BLUEPRINT 2.7; there is no L
MODELS = ("opus", "sonnet")  # BLUEPRINT 2.8; never fable, never a local model
WHO = ("loop", "founder")
CARD = "card"


class LadderError(ValueError):
    """The ladder file is not usable. Halt, do not guess."""


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    gate: bool
    needs: tuple[str, ...]
    size: str | None = None
    model: str | None = None
    who: str | None = None
    spec: str | None = None
    ticks: int | None = None

    @property
    def is_card(self) -> bool:
        """True when only a card exists, so the build cannot start yet."""
        return self.spec == CARD

    @property
    def needs_the_founder(self) -> bool:
        return self.who == "founder"


@dataclass(frozen=True)
class Ladder:
    build_branch: str
    branch_prefix: str
    claim_hours: int
    max_review_rounds: int
    halt_label: str
    entries: tuple[Entry, ...]
    version: str | None = None

    def __iter__(self):
        return iter(self.entries)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(e.id for e in self.entries)

    def get(self, entry_id: str) -> Entry | None:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def branch_for(self, entry_id: str) -> str:
        """Exactly ``claude/<id>`` in lower case, nothing else."""
        return f"{self.branch_prefix}{entry_id.lower()}"


def load(path: str | Path, spec_root: str | Path | None = None) -> Ladder:
    """Load ``path`` and validate it.

    ``spec_root``, when given, is the folder each non-card ``spec`` path is
    resolved against, and every one of them must exist. The frozen test
    fixtures are loaded without it: they are copies kept for the decision
    table, and pointing them at the live spec folder would couple this build's
    tests to files other builds create and rename. The live ``LADDER.yaml`` is
    loaded *with* it, by the one test that reads it.
    """
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise LadderError(f"no ladder file at {path}") from exc
    except yaml.YAMLError as exc:
        raise LadderError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("ladder"), list):
        raise LadderError(f"{path} has no 'ladder:' list")

    entries: list[Entry] = []
    seen: set[str] = set()
    for row in raw["ladder"]:
        entries.append(_entry(row, seen, spec_root))
        seen.add(entries[-1].id)

    for key in ("build_branch", "branch_prefix", "claim_hours", "max_review_rounds", "halt_label"):
        if raw.get(key) in (None, ""):
            raise LadderError(f"{path} is missing '{key}'")

    return Ladder(
        build_branch=raw["build_branch"],
        branch_prefix=raw["branch_prefix"],
        claim_hours=int(raw["claim_hours"]),
        max_review_rounds=int(raw["max_review_rounds"]),
        halt_label=raw["halt_label"],
        entries=tuple(entries),
        version=str(raw.get("version")) if raw.get("version") is not None else None,
    )


def _entry(row: object, seen: set[str], spec_root: str | Path | None) -> Entry:
    if not isinstance(row, dict) or not row.get("id"):
        raise LadderError(f"a ladder row has no id: {row!r}")
    entry_id = str(row["id"])
    if entry_id in seen:
        raise LadderError(f"duplicate id {entry_id}")

    needs = tuple(str(n) for n in row.get("needs") or ())
    for need in needs:
        if need not in seen:
            raise LadderError(
                f"{entry_id} needs {need}, which does not appear earlier in the file. "
                "Order in the ladder is the order of work, so a prerequisite must "
                "come first."
            )

    gate = bool(row.get("gate"))
    if gate:
        if row.get("spec") is not None:
            raise LadderError(f"{entry_id} is a gate and must have no spec")
        return Entry(entry_id, str(row.get("title", "")), True, needs)

    size, model, who = row.get("size"), row.get("model"), row.get("who")
    if size not in TICKS_FOR_SIZE:
        raise LadderError(
            f"{entry_id} has size {size!r}; allowed sizes are "
            f"{', '.join(TICKS_FOR_SIZE)} (BLUEPRINT 2.7; there is no L)"
        )
    if model not in MODELS:
        raise LadderError(f"{entry_id} has model {model!r}; allowed are {', '.join(MODELS)}")
    if who not in WHO:
        raise LadderError(f"{entry_id} has who {who!r}; allowed are {', '.join(WHO)}")

    ticks = row.get("ticks")
    if ticks != TICKS_FOR_SIZE[size]:
        raise LadderError(
            f"{entry_id} is size {size} and so must allow {TICKS_FOR_SIZE[size]} ticks, "
            f"not {ticks!r}"
        )

    spec = row.get("spec")
    if spec is None:
        raise LadderError(
            f"{entry_id} has neither a spec file nor 'card'. A build the loop cannot "
            "read a spec for cannot start."
        )
    spec = str(spec)
    if spec != CARD and spec_root is not None and not (Path(spec_root) / spec).is_file():
        raise LadderError(f"{entry_id}'s spec {spec} does not exist under {spec_root}")

    return Entry(entry_id, str(row.get("title", "")), False, needs, size, model, who, spec, ticks)
