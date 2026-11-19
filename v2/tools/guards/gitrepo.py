"""Reading a pull request as data: commits, paths, file contents, spec headers.

Nothing here imports or executes anything from the pull request. Every fact
comes out of ``git`` as text. That is deliberate: the guards judge a branch
whose code they must never run.

Conventions (CLAUDE.md): tz-aware UTC everywhere, so no local-time reads happen
in this module at all -- it reads no dates.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

BUILD_BRANCH = re.compile(r"^claude/b\d{2}[a-z]?$")


class GuardError(Exception):
    """Something the guards need could not be read. Never swallowed: a guard
    that cannot do its job must say so, not pass quietly."""


@dataclass(frozen=True)
class Finding:
    """A reason the pull request fails."""

    guard: str
    message: str

    def __str__(self) -> str:
        return f"{self.guard}: {self.message}"


@dataclass(frozen=True)
class Note:
    """Something the founder or the reviewer is shown, which is not a failure."""

    guard: str
    message: str

    def __str__(self) -> str:
        return f"{self.guard}: {self.message}"


@dataclass(frozen=True)
class Change:
    status: str  # A, M, D, or R
    path: str
    old_path: str | None = None

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.path,) if self.old_path is None else (self.old_path, self.path)


@dataclass(frozen=True)
class SpecHeader:
    build_id: str
    touches: tuple[str, ...]
    may_modify_tests: tuple[str, ...]
    adds_dependencies: tuple[str, ...]
    who: str = ""
    path: str = ""


@dataclass
class Context:
    """One pull request, as the guards see it."""

    repo: Path
    base_sha: str
    head_sha: str
    head_ref: str
    base_ref: str
    is_fork: bool = False
    _cache: dict = field(default_factory=dict, repr=False)

    # --- git ---------------------------------------------------------------

    def git(self, *args: str) -> str:
        done = subprocess.run(
            ("git", "-C", str(self.repo)) + args,
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode != 0:
            raise GuardError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
        return done.stdout

    def _git_ok(self, *args: str) -> bool:
        done = subprocess.run(
            ("git", "-C", str(self.repo)) + args,
            capture_output=True,
            text=True,
            check=False,
        )
        return done.returncode == 0

    @cached_property
    def diff_base(self) -> str:
        """Where the branch left the base line. Using the merge base rather
        than the base tip means an unrelated upstream commit is never read as
        this pull request's work."""
        try:
            return self.git("merge-base", self.base_sha, self.head_sha).strip()
        except GuardError:
            return self.base_sha

    @cached_property
    def changes(self) -> tuple[Change, ...]:
        out = self.git(
            "diff", "--name-status", "-M", "-z", self.diff_base, self.head_sha
        )
        fields = [f for f in out.split("\0") if f != ""]
        changes: list[Change] = []
        i = 0
        while i < len(fields):
            status = fields[i]
            if status.startswith("R"):
                changes.append(Change("R", fields[i + 2], fields[i + 1]))
                i += 3
            else:
                changes.append(Change(status[0], fields[i + 1]))
                i += 2
        return tuple(changes)

    @cached_property
    def changed_paths(self) -> tuple[str, ...]:
        seen: list[str] = []
        for change in self.changes:
            for path in change.paths:
                if path not in seen:
                    seen.append(path)
        return tuple(seen)

    @cached_property
    def commits(self) -> tuple[str, ...]:
        """The branch's own commits, oldest first.

        ``--first-parent`` keeps this to the branch's own line: a commit that
        arrived because the branch merged another branch in belongs to that
        branch, and is judged on its own pull request.
        """
        out = self.git(
            "rev-list", "--first-parent", "--reverse", f"{self.diff_base}..{self.head_sha}"
        )
        return tuple(line for line in out.split() if line)

    def message(self, sha: str) -> str:
        return self.git("log", "-1", "--format=%B", sha)

    def trailer(self, sha: str, key: str) -> str | None:
        """Read a git trailer. ``%(trailers)`` is git's own parser, so a line
        that merely looks like a trailer in the middle of a message is not one.
        """
        out = self.git(
            "log", "-1", f"--format=%(trailers:key={key},valueonly,separator=%x0A)", sha
        )
        values = [line.strip() for line in out.split("\n") if line.strip()]
        return values[-1] if values else None

    def paths_in(self, sha: str) -> tuple[str, ...]:
        """Paths one commit changed -- its own work, not its parents'.

        An ordinary commit is diffed against its parent, and a root commit
        against the empty tree.

        A **merge** commit is diffed with ``--cc``, the combined diff: the
        files whose merged content differs from *every* parent. A file taken
        verbatim from one side is not among them, so merging the base branch in
        -- which every build does once the base moves while it is in review --
        no longer charges the branch with what the base did meanwhile. What
        does remain is anything the merge itself decided: a file resolved by
        hand, a file git auto-merged from both sides, and above all a file
        planted in the merge commit that exists in neither parent. A merge is
        not a hiding place.

        ``commits`` makes the same judgement one level up, with
        ``--first-parent``: the commits a merge brings in belong to the branch
        they came from and are judged on its own pull request. This is that
        rule finished -- without it the exclusion stopped at the merge commit
        itself, which sits on the first-parent line.
        """
        parents = self.git("rev-list", "--parents", "-n", "1", sha).split()[1:]
        if len(parents) > 1:
            out = self.git("diff-tree", "--cc", "-r", "--name-only", "--no-commit-id", sha)
        elif parents:
            out = self.git("diff", "--name-only", "-M", f"{sha}^", sha)
        else:
            out = self.git("show", "--name-only", "--format=", sha)
        return tuple(line.strip() for line in out.split("\n") if line.strip())

    def file_at(self, sha: str, path: str) -> str | None:
        if not self._git_ok("cat-file", "-e", f"{sha}:{path}"):
            return None
        return self.git("show", f"{sha}:{path}")

    def tree_at(self, sha: str, prefix: str) -> dict[str, str]:
        """``{path: blob id}`` for every file under ``prefix`` at ``sha``."""
        out = self.git("ls-tree", "-r", "-z", "--format=%(objectname) %(path)", sha, prefix)
        tree: dict[str, str] = {}
        for entry in out.split("\0"):
            if not entry.strip():
                continue
            blob, _, path = entry.partition(" ")
            tree[path] = blob
        return tree

    def exists_at(self, sha: str, path: str) -> bool:
        return self._git_ok("cat-file", "-e", f"{sha}:{path}")

    # --- the branch's kind and its spec ------------------------------------

    @cached_property
    def build_id(self) -> str | None:
        """``B06`` for ``claude/b06``. ``None`` when this is not a build
        branch."""
        if not BUILD_BRANCH.match(self.head_ref):
            return None
        return self.head_ref.split("/", 1)[1].upper()

    @cached_property
    def base_spec(self) -> SpecHeader | None:
        """The build's spec **as it is on the base commit**.

        This is the single most important line in the guards: a branch that
        edits its own spec to widen ``touches`` changes nothing here.
        """
        if self.build_id is None:
            return None
        if "base_spec" in self._cache:
            return self._cache["base_spec"]
        prefix = f"docs/v2/build/specs/{self.build_id}-"
        matches = [
            path
            for path in self.tree_at(self.base_sha, "docs/v2/build/specs")
            if path.startswith(prefix) and path.endswith(".md")
        ]
        if len(matches) != 1:
            raise GuardError(
                f"expected exactly one spec at the base commit for {self.build_id}, "
                f"found {len(matches)}: {matches}. A build with no spec on the base "
                "branch is a halt, not a pass."
            )
        header = parse_spec_header(self.file_at(self.base_sha, matches[0]) or "", matches[0])
        self._cache["base_spec"] = header
        return header


def parse_spec_header(text: str, path: str = "") -> SpecHeader:
    """Parse the fenced yaml block at the top of a spec.

    Deliberately not a yaml library: the guards must run even when the pull
    request has broken the environment, and these headers are a fixed, flat
    shape. Anything this parser does not understand raises, because a guard
    that silently reads ``touches`` as empty would pass everything.
    """
    match = re.search(r"^```ya?ml\s*\n(.*?)^```\s*$", text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise GuardError(f"{path or 'spec'}: no fenced yaml header found")

    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current: str | None = None
    for raw in match.group(1).split("\n"):
        line = raw.split("  #")[0].rstrip() if "  #" in raw else raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith(("  - ", "- ")):
            if current is None:
                raise GuardError(f"{path or 'spec'}: list item with no key: {raw!r}")
            lists[current].append(line.split("- ", 1)[1].strip())
            continue
        if re.match(r"^\S", line) is None:
            raise GuardError(f"{path or 'spec'}: cannot parse line {raw!r}")
        key, sep, value = line.partition(":")
        if not sep:
            raise GuardError(f"{path or 'spec'}: cannot parse line {raw!r}")
        key, value = key.strip(), value.strip()
        if value in ("", "|", ">"):
            current = key
            lists[key] = []
        elif value == "[]":
            current = None
            lists[key] = []
        elif value.startswith("[") and value.endswith("]"):
            current = None
            lists[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            current = None
            scalars[key] = value.strip("'\"")

    if "id" not in scalars:
        raise GuardError(f"{path or 'spec'}: header has no id")
    if "touches" not in lists:
        raise GuardError(f"{path or 'spec'}: header has no touches list")

    return SpecHeader(
        build_id=scalars["id"].upper(),
        touches=tuple(lists["touches"]),
        may_modify_tests=tuple(lists.get("may_modify_tests", [])),
        adds_dependencies=tuple(lists.get("adds_dependencies", [])),
        who=scalars.get("who", ""),
        path=path,
    )


def matches(pattern: str, path: str) -> bool:
    """Does a ``touches`` glob cover this path?

    ``**`` crosses directories, ``*`` does not, and a pattern ending in ``/``
    or naming a directory covers everything beneath it -- the way the specs are
    written (``v2/src/chronos2/stats/**``).
    """
    pattern = pattern.strip()
    if not pattern:
        return False
    if pattern.endswith("/"):
        pattern += "**"
    regex = _glob_to_regex(pattern)
    if re.fullmatch(regex, path):
        return True
    # A bare directory name covers its contents.
    return bool(re.fullmatch(_glob_to_regex(pattern.rstrip("/") + "/**"), path))


def _glob_to_regex(pattern: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif char == "*":
            out.append("[^/]*")
            i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    return "".join(out)
