"""B02 known answer: ``.github/CODEOWNERS`` resolves as intended.

The file is written as "everything is the founder's, except the folders builds
work in" (deliverable 3). Listing only the files to protect is how the earlier
drafts kept missing some -- the lock file, the loop's own code, a ``conftest.py``
beside the package -- so this test evaluates the real file's patterns in order
against the twelve sample paths the spec names.

GitHub's rules this relies on, read fresh at build time (18 Nov 2026):
the **last** matching pattern wins, and a pattern with **no owners** removes
ownership for that path. The copy that governs a pull request is the one on the
pull request's **base** branch, which is why this file has no force until it has
merged (and no force at all until B05 requires a code owner's review).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from codeowners import CodeOwners

REPO_ROOT = Path(__file__).resolve().parents[4]
CODEOWNERS_PATH = REPO_ROOT / ".github" / "CODEOWNERS"

FOUNDER = "@vedantgautam1"

# Exactly the spec's two lists.
OWNED = [
    ".github/workflows/v2.yml",
    "v2/uv.lock",
    "v2/conftest.py",
    "v2/tools/loop/next_action.py",
    "v2/src/sitecustomize.py",
    "v2/src/chronos2/stats/CLAUDE.md",
    "docs/v2/build/specs/B06-stats-core.md",
    "v2/config/protected/validation.yaml",
]

NOT_OWNED = [
    "v2/src/chronos2/stats/dsr.py",
    "v2/tests/stats/test_dsr.py",
    "docs/v2/build/reports/b06.md",
    "docs/v2/CHANGELOG.md",
]


@pytest.fixture
def owners() -> CodeOwners:
    return CodeOwners(CODEOWNERS_PATH.read_text())


@pytest.mark.parametrize("path", OWNED)
def test_the_founder_owns_these_paths(owners, path):
    assert owners.owners_of(path) == [FOUNDER], (
        f"{path} must be the founder's: it is a rule file, a dependency file, "
        "an instruction file, or something beside the package"
    )


@pytest.mark.parametrize("path", NOT_OWNED)
def test_these_paths_have_no_owner(owners, path):
    assert owners.owners_of(path) == [], (
        f"{path} is a folder builds work in: it must resolve to no owner, so a "
        "build does not wait on the founder"
    )


def test_the_first_line_is_the_catch_all(owners):
    """Later lines win, so the catch-all has to come first or the carve-outs
    would override nothing."""
    assert owners.rules[0].pattern == "*"
    assert list(owners.rules[0].owners) == [FOUNDER]


def test_the_file_uses_no_unsupported_pattern_syntax(owners):
    """GitHub's CODEOWNERS is gitignore-style minus three features: no ``!``
    negation, no ``[a-z]`` character ranges, no escaped ``#``. A file that uses
    one does not fail loudly -- it silently assigns nobody."""
    for rule in owners.rules:
        assert not rule.pattern.startswith("!"), f"negation is unsupported: {rule.pattern}"
        assert "[" not in rule.pattern, f"character ranges are unsupported: {rule.pattern}"
        assert "\\#" not in rule.pattern, f"escaped # is unsupported: {rule.pattern}"


def test_every_owner_line_names_the_founder_and_nobody_else(owners):
    """Until the automation gets its own identity (a G1 decision) the founder is
    the only code owner. A team that does not exist, or an account without write
    access, silently assigns nobody."""
    for rule in owners.rules:
        for owner in rule.owners:
            assert owner == FOUNDER, f"unexpected owner {owner} on {rule.pattern}"


# --- the resolver itself, against GitHub's documented semantics -------------


def test_last_matching_pattern_wins():
    owners = CodeOwners("* @a\n/docs/ @b\n")
    assert owners.owners_of("docs/x.md") == ["@b"]
    assert owners.owners_of("README.md") == ["@a"]


def test_a_pattern_with_no_owners_removes_ownership():
    owners = CodeOwners("* @a\n/generated/\n")
    assert owners.owners_of("generated/api.ts") == []
    assert owners.owners_of("src/api.ts") == ["@a"]


def test_an_unmatched_path_is_distinct_from_a_matched_path_with_no_owner():
    owners = CodeOwners("/apps/ @a\n/apps/github/\n")
    assert owners.owners_of("apps/main/index.js") == ["@a"]
    assert owners.owners_of("apps/github/index.js") == []
    assert owners.owners_of("README.md") is None


def test_a_trailing_slash_matches_everything_below_the_directory():
    owners = CodeOwners("/v2/tests/ @a\n")
    assert owners.owners_of("v2/tests/stats/deep/test_x.py") == ["@a"]
    assert owners.owners_of("v2/tests") is None


def test_a_leading_slash_anchors_at_the_repository_root():
    owners = CodeOwners("/build/ @a\n")
    assert owners.owners_of("build/out.js") == ["@a"]
    assert owners.owners_of("v2/build/out.js") is None


def test_an_unanchored_pattern_matches_at_any_depth():
    owners = CodeOwners("CLAUDE.md @a\n")
    assert owners.owners_of("CLAUDE.md") == ["@a"]
    assert owners.owners_of("v2/src/chronos2/stats/CLAUDE.md") == ["@a"]


def test_a_double_star_matches_across_directories():
    owners = CodeOwners("/v2/**/CLAUDE.md @a\n")
    assert owners.owners_of("v2/src/chronos2/CLAUDE.md") == ["@a"]
    assert owners.owners_of("v2/CLAUDE.md") == ["@a"]


def test_comments_and_blank_lines_are_ignored():
    owners = CodeOwners("# a comment\n\n* @a\n")
    assert len(owners.rules) == 1
    assert owners.owners_of("x") == ["@a"]


def test_matching_is_case_sensitive():
    owners = CodeOwners("/docs/ @a\n")
    assert owners.owners_of("docs/x.md") == ["@a"]
    assert owners.owners_of("Docs/x.md") is None
