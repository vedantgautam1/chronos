"""Evaluating a CODEOWNERS file the way GitHub does.

Three semantics, read fresh from GitHub's docs at build time (18 Nov 2026) and
not from memory -- designing GitHub behaviour from memory is how the first
version of this build went wrong:

1. The **last** matching pattern wins. Not the most specific one. Almost every
   wrong prediction about a CODEOWNERS file comes from assuming otherwise.
2. A pattern with **no owners** removes ownership for that path. It still
   matches, so it still wins as the last matching rule -- it just requests
   nobody. That is a third state, and collapsing it into "no rule matched"
   would silently hand the path back to whatever broader rule came before.
3. Patterns are gitignore-style **minus three features**: no ``!`` negation, no
   ``[a-z]`` character ranges, no escaped ``#``. Matching is case-sensitive.

Owners for one pattern must all be on one line; if the same pattern appears on
two lines, only the last line's owners count -- which falls out of rule 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    pattern: str
    owners: tuple[str, ...]
    regex: re.Pattern[str]

    def matches(self, path: str) -> bool:
        return self.regex.fullmatch(path) is not None


class CodeOwners:
    def __init__(self, text: str) -> None:
        self.rules: list[Rule] = []
        for raw in text.split("\n"):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            pattern, *owners = line.split()
            self.rules.append(Rule(pattern, tuple(owners), _compile(pattern)))

    def owners_of(self, path: str) -> list[str] | None:
        """The owners of ``path``: a list (empty means matched but un-owned), or
        ``None`` when no rule matched it at all."""
        for rule in reversed(self.rules):
            if rule.matches(path):
                return list(rule.owners)
        return None


def _compile(pattern: str) -> re.Pattern[str]:
    directory_only = pattern.endswith("/")
    core = pattern.rstrip("/")
    # gitignore: a pattern with a slash anywhere but the end is anchored at the
    # root; one without is matched against the basename at any depth.
    anchored = core.startswith("/") or "/" in core.strip("/")
    core = core.lstrip("/")

    body = _translate(core)
    prefix = "" if anchored else "(?:.*/)?"
    suffix = "/.*" if directory_only else "(?:/.*)?"
    return re.compile(prefix + body + suffix)


def _translate(pattern: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "".join(out)
