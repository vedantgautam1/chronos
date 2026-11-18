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

import re

from gitrepo import Context, Finding, GuardError, matches

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
