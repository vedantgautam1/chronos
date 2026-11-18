"""The guards themselves. Each is a function taking a Context and returning
findings.

**What these are.** Tripwires: they catch a session that makes a mistake or
takes a shortcut. They are not proof against a session that sets out to
deceive, and nothing here should ever be described as a wall. What stands
behind them is GitHub's own rules on ``main`` and on founder-owned files (from
B05), and the audit at every gate. ``specs/B02-guards.md`` has the table of what
each guard does not stop and what does.
"""

from __future__ import annotations

import json
import re

from gitrepo import Context, Finding, GuardError, Note, matches

# The five v2 documents a gate write-up may update.
V2_DOCS = (
    "docs/v2/CHRONOS_V2.md",
    "docs/v2/BUILD_NOTES.md",
    "docs/v2/COMPONENTS.md",
    "docs/v2/CODEBASE.md",
    "docs/v2/CHANGELOG.md",
)

# v1 is frozen (V2-D10). These paths must be identical to branch v1-final.
V1_PATHS = ("src", "tests", "pyproject.toml", "uv.lock")

GATE_REPORT = re.compile(r"^docs/v2/build/gates/G(\d+)-report\.md$")

# Never writable from a build or lane branch, whatever a spec says.
ABSOLUTE = (
    "docs/v2/CHRONOS_V2.md",
    "docs/v2/build/specs/**",
    "docs/v2/build/LADDER.yaml",
    "docs/v2/build/BLUEPRINT.md",
    "docs/v2/build/BUILD_CARDS.md",
    "docs/v2/build/gates/**",
)

# The founder's, unless the build's own spec at the base commit lists the path.
# Written as "everything of this kind", not as a list of individual files: that
# is how the earlier drafts kept missing one (red-team finding g).
FOUNDER_OWNED = (
    "CLAUDE.md",
    "**/CLAUDE.md",
    "CLAUDE.local.md",
    "**/CLAUDE.local.md",
    "AGENTS.md",
    "**/AGENTS.md",
    ".claude/**",
    "**/.claude/**",
    ".github/**",
    "CODEOWNERS",
    "**/CODEOWNERS",
    "v2/tools/guards/**",
    "v2/tools/loop/**",
    "v2/config/protected/**",
    "v2/pyproject.toml",
    "v2/uv.lock",
    "v2/src/chronos2/fixtures/touchstones/**",
    "docs/v2/build/HANDBOOK.md",
    "docs/v2/build/specs/README.md",
)

# Existing files here are frozen outright: several builds share these folders,
# so "stay inside your listed files" alone did not stop a later build from
# loosening an earlier build's assertion in place.
FROZEN_DIRS = ("v2/tests", "v2/tools/v1_oracle", "v2/migrations")

PROTECTED_VALUES_DIR = "v2/config/protected"


# --------------------------------------------------------------------------
# v1_frozen
# --------------------------------------------------------------------------


def v1_frozen(ctx: Context) -> list[Finding]:
    """The diff against ``v1-final`` on v1's paths must be empty."""
    ref = None
    for candidate in ("origin/v1-final", "v1-final"):
        if ctx._git_ok("rev-parse", "--verify", candidate):
            ref = candidate
            break
    if ref is None:
        raise GuardError(
            "neither origin/v1-final nor v1-final can be resolved, so the v1 "
            "freeze cannot be checked. This is a halt, not a pass."
        )

    out = ctx.git("diff", "--name-only", ref, ctx.head_sha, "--", *V1_PATHS)
    changed = sorted({line.strip() for line in out.split("\n") if line.strip()})
    return [
        Finding(
            "v1_frozen",
            f"{path} differs from {ref}. v1 is frozen (V2-D10): port into v2, "
            "never extend v1.",
        )
        for path in changed
    ]


# --------------------------------------------------------------------------
# branch_kind
# --------------------------------------------------------------------------


def _outside(paths: tuple[str, ...], allowed: tuple[str, ...]) -> list[str]:
    return [p for p in paths if not any(matches(a, p) for a in allowed)]


def branch_kind(ctx: Context) -> list[Finding]:
    """Classify the branch by head and base, and hold each kind to its paths."""
    found: list[Finding] = []
    if ctx.is_fork:
        return [
            Finding(
                "branch_kind",
                "the head branch is in a fork. Only branches in this repository "
                "count; a pull request from a fork always fails.",
            )
        ]

    head, base = ctx.head_ref, ctx.base_ref
    paths = ctx.changed_paths

    if ctx.build_id is not None and base == "v2-build":
        return found  # a build. scope, roles and protected judge its paths.

    if head.startswith("claude/") and base == "v2-build":
        return [
            Finding(
                "branch_kind",
                f"{head!r} is not a build branch name. A build branch is exactly "
                "claude/<id> in lower case (claude/b06, claude/b01a); a one-digit "
                "id or a suffix is not. For work that is not a build, use "
                "doc/..., spec/..., lane/... or gate/gN.",
            )
        ]

    if head.startswith("lane/") and base == "v2-build":
        allowed = ("scratch/**", "docs/drafts/**")
    elif head.startswith("spec/") and base == "v2-build":
        allowed = ("docs/v2/build/**",)
    elif head.startswith("doc/") and base in ("v2-build", "main"):
        outside = [
            p
            for p in paths
            if not (
                (matches("docs/**", p) and not matches("docs/v2/build/specs/**", p))
                or p == "CLAUDE.md"
            )
        ]
        return _report("documents", head, outside)
    elif re.match(r"^gate/g\d+$", head) and base == "v2-build":
        allowed = (
            "docs/v2/build/gates/**",
            "docs/v2/build/sabotage/**",
            "docs/v2/build/LEDGER.md",
        ) + V2_DOCS
    elif head == "v2-build" and base == "main":
        added = {c.path for c in ctx.changes if c.status in ("A", "M", "R")}
        reports = sorted(p for p in added if GATE_REPORT.match(p))
        fresh = [p for p in reports if not ctx.exists_at(ctx.base_sha, p)]
        if not fresh:
            return [
                Finding(
                    "branch_kind",
                    "a gate move must bring the next gate report with it: the diff "
                    "has no new docs/v2/build/gates/G<n>-report.md. A gate counts as "
                    "done when its report is on main.",
                )
            ]
        return found
    else:
        return [
            Finding(
                "branch_kind",
                f"{head!r} into {base!r} is not a branch kind this repository has. "
                "The kinds are: claude/<id> into v2-build (build), lane/... , "
                "spec/... , doc/... , gate/gN into v2-build, and v2-build into main "
                "(gate move).",
            )
        ]

    return _report(head.split("/", 1)[0], head, _outside(paths, allowed))


def _report(kind: str, head: str, outside: list[str]) -> list[Finding]:
    return [
        Finding(
            "branch_kind",
            f"{head!r} is a {kind} branch, which may not change {path}.",
        )
        for path in sorted(outside)
    ]


# --------------------------------------------------------------------------
# scope
# --------------------------------------------------------------------------


def _builder_extra(build_id: str) -> tuple[str, ...]:
    lower = build_id.lower()
    return (
        f"docs/v2/build/reports/{build_id}.md",
        f"docs/v2/build/reports/{lower}.md",
        f"docs/v2/build/status/{build_id}.json",
        f"docs/v2/build/status/{lower}.json",
        "docs/v2/CHANGELOG.md",
    )


def _reviewer_allowed(build_id: str) -> tuple[str, ...]:
    lower = build_id.lower()
    return (
        f"docs/v2/build/reviews/{build_id}-r*.md",
        f"docs/v2/build/reviews/{lower}-r*.md",
        f"docs/v2/build/status/{build_id}.json",
        f"docs/v2/build/status/{lower}.json",
        "docs/v2/build/LEDGER.md",
    )


def scope(ctx: Context) -> list[Finding]:
    """Every changed path is allowed for the role of the commit that changed it,
    with ``touches`` read from the spec **at the base commit**."""
    if ctx.build_id is None:
        return []
    spec = ctx.base_spec
    assert spec is not None

    builder_allowed = tuple(spec.touches) + _builder_extra(ctx.build_id)
    reviewer_allowed = _reviewer_allowed(ctx.build_id)

    found: list[Finding] = []
    for sha in ctx.commits:
        role = (ctx.trailer(sha, "Chronos-Role") or "").strip().lower()
        allowed = reviewer_allowed if role == "reviewer" else builder_allowed
        for path in ctx.paths_in(sha):
            if any(matches(pattern, path) for pattern in allowed):
                continue
            found.append(
                Finding(
                    "scope",
                    f"{sha[:8]} ({role or 'no role'}) changed {path}, which is not "
                    f"allowed for that role. {ctx.build_id}'s touches, read from the "
                    f"spec at the base commit ({spec.path}), are: "
                    f"{', '.join(spec.touches)}. Needing another file means the spec "
                    "is wrong: halt.",
                )
            )
    return found


# --------------------------------------------------------------------------
# roles
# --------------------------------------------------------------------------

BUILDER_STATES = ("building", "needs_review", "halted")
REVIEWER_STATES = ("changes_requested", "passed", "merged", "halted")
CODE_COMMIT = re.compile(r"code commit reviewed[^0-9a-f]{0,20}([0-9a-f]{7,40})", re.IGNORECASE)


def _status_state(ctx: Context, sha: str) -> str | None:
    if ctx.build_id is None:
        return None
    for name in (f"{ctx.build_id}.json", f"{ctx.build_id.lower()}.json"):
        raw = ctx.file_at(sha, f"docs/v2/build/status/{name}")
        if raw is None:
            continue
        try:
            return str(json.loads(raw).get("state", "")).strip().lower()
        except json.JSONDecodeError as exc:
            raise GuardError(f"docs/v2/build/status/{name} at {sha[:8]} is not valid JSON: {exc}")
    return None


def roles(ctx: Context) -> list[Finding]:
    """Every commit carries a role; each role writes only its own things; and a
    ``passed`` or ``merged`` status needs a review naming the current code.

    **A trailer is a label a session puts on its own commit.** This guard
    catches a session doing the wrong role's work by mistake. It cannot catch
    one that labels its commits falsely: builder and reviewer act with the same
    GitHub account, so the separation between them rests on the loop starting a
    fresh session per action, and on the gate audit checking that afterwards.
    """
    if ctx.build_id is None:
        return []

    found: list[Finding] = []
    last_builder: str | None = None

    for sha in ctx.commits:
        role = (ctx.trailer(sha, "Chronos-Role") or "").strip().lower()
        paths = ctx.paths_in(sha)
        if role not in ("builder", "reviewer"):
            found.append(
                Finding(
                    "roles",
                    f"{sha[:8]} carries no Chronos-Role trailer (found {role!r}). Every "
                    "commit on a build branch ends with Chronos-Role: builder or "
                    "Chronos-Role: reviewer.",
                )
            )
            continue

        state = _status_state(ctx, sha)
        if role == "builder":
            last_builder = sha
            for path in paths:
                if matches("docs/v2/build/reviews/**", path):
                    found.append(
                        Finding(
                            "roles",
                            f"{sha[:8]} is a builder commit and wrote the review file "
                            f"{path}. A builder never writes a review: the session that "
                            "wrote the code does not review it.",
                        )
                    )
                elif path == "docs/v2/build/LEDGER.md":
                    found.append(
                        Finding(
                            "roles",
                            f"{sha[:8]} is a builder commit and wrote LEDGER.md, which is "
                            "the reviewer's to write.",
                        )
                    )
            if state is not None and state not in BUILDER_STATES:
                found.append(
                    Finding(
                        "roles",
                        f"{sha[:8]} is a builder commit and set the status to {state!r}. A "
                        f"builder may set only {', '.join(BUILDER_STATES)}.",
                    )
                )
        else:
            for path in paths:
                allowed = (
                    "docs/v2/build/reviews/**",
                    "docs/v2/build/status/**",
                    "docs/v2/build/LEDGER.md",
                )
                if not any(matches(pattern, path) for pattern in allowed):
                    found.append(
                        Finding(
                            "roles",
                            f"{sha[:8]} is a reviewer commit and changed {path}. A reviewer "
                            "touches nothing but reviews/, status/ and LEDGER.md -- not code "
                            "or tests, not even for a one-character fix: a reviewer that "
                            "edits them is reviewing its own work.",
                        )
                    )
            if state is not None and state not in REVIEWER_STATES:
                found.append(
                    Finding(
                        "roles",
                        f"{sha[:8]} is a reviewer commit and set the status to {state!r}. A "
                        f"reviewer may set only {', '.join(REVIEWER_STATES)}.",
                    )
                )

    found += _review_backs_the_status(ctx, last_builder)
    return found


def _review_backs_the_status(ctx: Context, last_builder: str | None) -> list[Finding]:
    """``passed`` or ``merged`` requires a review file with verdict PASS whose
    "code commit reviewed" is the last builder commit."""
    state = _status_state(ctx, ctx.head_sha)
    if state not in ("passed", "merged"):
        return []

    assert ctx.build_id is not None
    reviews = {
        path: body
        for path in ctx.tree_at(ctx.head_sha, "docs/v2/build/reviews")
        if re.match(rf"^docs/v2/build/reviews/{ctx.build_id}-r\d+\.md$", path, re.IGNORECASE)
        and (body := ctx.file_at(ctx.head_sha, path)) is not None
    }
    if not reviews:
        return [
            Finding(
                "roles",
                f"the status is {state!r} but there is no review file for {ctx.build_id}. "
                "A passed or merged status needs a review naming the current code commit.",
            )
        ]

    latest = max(reviews, key=lambda p: int(re.search(r"-r(\d+)\.md$", p, re.IGNORECASE).group(1)))
    body = reviews[latest]
    if not re.search(r"\bPASS\b", body):
        return [
            Finding(
                "roles",
                f"the status is {state!r} but {latest} does not record a PASS verdict.",
            )
        ]

    named = CODE_COMMIT.search(body)
    if named is None:
        return [
            Finding(
                "roles",
                f"the status is {state!r} but {latest} does not say which code commit was "
                "reviewed.",
            )
        ]
    if last_builder is None:
        return [
            Finding(
                "roles",
                f"the status is {state!r} but the branch has no builder commit to review.",
            )
        ]
    if not last_builder.startswith(named.group(1)):
        return [
            Finding(
                "roles",
                f"the status is {state!r} but {latest} reviewed code commit "
                f"{named.group(1)[:8]}, and the last builder commit is {last_builder[:8]}. "
                "Code was pushed after the review, so the review does not cover what would "
                "be merged.",
            )
        ]
    return []


# --------------------------------------------------------------------------
# frozen_files
# --------------------------------------------------------------------------


def frozen_files(ctx: Context) -> list[Finding]:
    """A file that exists at the base under a frozen folder may not be changed,
    renamed or deleted. New files may be added.

    This is a comparison of file lists and contents, which is what stops a later
    build from quietly weakening an earlier build's assertion or emptying an
    earlier build's oracle script.
    """
    spec = ctx.base_spec
    allowed = set(spec.may_modify_tests) if spec else set()

    base: dict[str, str] = {}
    for folder in FROZEN_DIRS:
        base.update(ctx.tree_at(ctx.base_sha, folder))
    if not base:
        return []

    head: dict[str, str] = {}
    for folder in FROZEN_DIRS:
        head.update(ctx.tree_at(ctx.head_sha, folder))

    found: list[Finding] = []
    for path, blob in sorted(base.items()):
        if path in allowed:
            continue
        if path not in head:
            found.append(
                Finding(
                    "frozen_files",
                    f"{path} existed at the base commit and is gone (deleted or renamed). "
                    "Existing tests, oracle scripts and migrations are frozen; new files go "
                    "in new files.",
                )
            )
        elif head[path] != blob:
            found.append(
                Finding(
                    "frozen_files",
                    f"{path} existed at the base commit and its contents changed. An earlier "
                    "build's assertion is not this build's to edit; if the spec means to "
                    "allow it, it must list the file in may_modify_tests.",
                )
            )
    return found


# --------------------------------------------------------------------------
# protected
# --------------------------------------------------------------------------


def protected(ctx: Context) -> list[Finding]:
    """Founder-owned paths, and the handful nothing may touch."""
    is_build = ctx.build_id is not None
    is_lane = ctx.head_ref.startswith("lane/")
    if not (is_build or is_lane):
        return []

    listed = set(ctx.base_spec.touches) if is_build and ctx.base_spec else set()
    found: list[Finding] = []

    for path in ctx.changed_paths:
        if any(matches(pattern, path) for pattern in ABSOLUTE):
            found.append(
                Finding(
                    "protected",
                    f"{path} is never writable from a build or lane branch, whatever a spec "
                    "says. The master doc, the specs, the ladder, the blueprint, the cards "
                    "and gates/ are the founder's; a build that needs one halts and says so "
                    "in its report under 'For the gate'.",
                )
            )
            continue
        if not any(matches(pattern, path) for pattern in FOUNDER_OWNED):
            continue
        if is_lane:
            found.append(
                Finding(
                    "protected",
                    f"{path} is founder-owned and a lane branch never changes one.",
                )
            )
        elif not any(matches(pattern, path) for pattern in listed):
            found.append(
                Finding(
                    "protected",
                    f"{path} is founder-owned. A build changes one only if its spec at the "
                    f"base commit lists it in touches, and {ctx.build_id}'s does not "
                    f"(touches: {', '.join(sorted(listed)) or 'none'}).",
                )
            )
    return found


# --------------------------------------------------------------------------
# Notes: shown to the founder and the reviewer, never a failure
# --------------------------------------------------------------------------


def notes(ctx: Context) -> list[Note]:
    """Things a human must see. A note never fails the run."""
    out: list[Note] = []
    out += _protected_value_diff(ctx)
    return out


def _protected_value_diff(ctx: Context) -> list[Note]:
    """When ``v2/config/protected/`` changes, print the old and new values, so
    the founder sees the diff he is approving (CLAUDE.md hard rule 7)."""
    out: list[Note] = []
    for path in ctx.changed_paths:
        if not matches(f"{PROTECTED_VALUES_DIR}/**", path):
            continue
        before = ctx.file_at(ctx.base_sha, path)
        after = ctx.file_at(ctx.head_sha, path)
        out.append(
            Note(
                "protected",
                f"{path} is a protected value and this pull request changes it. "
                "CLAUDE.md hard rule 7: show the diff and wait for the founder's approval.\n"
                f"    --- before ({'absent at the base commit' if before is None else 'base'})\n"
                + _indent(before)
                + f"    +++ after ({'deleted' if after is None else 'this branch'})\n"
                + _indent(after),
            )
        )
    return out


def _indent(text: str | None) -> str:
    if text is None:
        return "        (no file)\n"
    return "".join(f"        {line}\n" for line in text.rstrip("\n").split("\n"))
