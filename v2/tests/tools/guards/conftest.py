"""Throwaway git repositories for the guard tests (B02 step 1).

Fixtures only. No ``pytest_*`` hooks, no ``autouse``, nothing that changes
which tests run or how they are collected -- the ``plumbing`` guard forbids
exactly that, and this file is inside the folder it polices.

One import-affecting line lives here, disclosed in the build report: the guards
are at ``v2/tools/guards/``, outside the ``chronos2`` package, and B02's spec
does not list ``v2/pyproject.toml`` in ``touches``, so ``pythonpath`` cannot be
set there. The path is added here instead.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
GUARDS_DIR = REPO_ROOT / "v2" / "tools" / "guards"
if str(GUARDS_DIR) not in sys.path:
    sys.path.insert(0, str(GUARDS_DIR))

def _yaml_list(key: str, items: list[str]) -> str:
    """``key: []`` when empty, otherwise ``key:`` and one ``  - item`` a line."""
    if not items:
        return f"{key}: []"
    return "\n".join([f"{key}:"] + [f"  - {item}" for item in items])


def spec_text(
    build_id: str,
    touches: list[str],
    may_modify_tests: list[str],
    adds_dependencies: list[str],
) -> str:
    """A spec header as the real ones are written: a fenced yaml block on top."""
    upper = build_id.upper()
    return "\n".join(
        [
            "```yaml",
            f"id: {upper}",
            "title: a throwaway spec for the guard tests",
            "size: M",
            "model: opus",
            "who: loop",
            "needs: []",
            "ticks: 3",
            _yaml_list("touches", touches),
            _yaml_list("may_modify_tests", may_modify_tests),
            _yaml_list("adds_dependencies", adds_dependencies),
            "```",
            "",
            f"# {upper} -- a throwaway spec",
            "",
        ]
    )


class Repo:
    """A git repository in a temp folder, built commit by commit."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test Session")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args: str) -> str:
        done = subprocess.run(
            ("git", "-C", str(self.path)) + args,
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout.strip()

    def write(self, rel: str, text: str) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def remove(self, rel: str) -> None:
        self.git("rm", "-q", rel)

    def move(self, src: str, dst: str) -> None:
        (self.path / dst).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", src, dst)

    def commit(self, message: str, role: str | None = "builder") -> str:
        """Commit everything staged plus everything new. ``role=None`` omits
        the trailer, which is what the ``roles`` guard must catch."""
        self.git("add", "-A")
        full = message if role is None else f"{message}\n\nChronos-Role: {role}"
        self.git("commit", "-q", "-m", full)
        return self.sha()

    def sha(self, ref: str = "HEAD") -> str:
        return self.git("rev-parse", ref)

    def checkout(self, ref: str, create: bool = False) -> None:
        self.git("checkout", "-q", "-b", ref) if create else self.git("checkout", "-q", ref)

    def spec(
        self,
        build_id: str,
        touches: list[str],
        may_modify_tests: list[str] | None = None,
        adds_dependencies: list[str] | None = None,
        slug: str = "throwaway",
    ) -> None:
        """Write a spec file the way the real ones are named: ``B06-slug.md``."""
        self.write(
            f"docs/v2/build/specs/{build_id.upper()}-{slug}.md",
            spec_text(
                build_id,
                touches,
                may_modify_tests or [],
                adds_dependencies or [],
            ),
        )

    def install_guards(self) -> None:
        """Copy the real guard code in, so ``run_guards.sh`` has something to
        extract. Used by the base-copy and bootstrap tests."""
        dest = self.path / "v2" / "tools" / "guards"
        dest.mkdir(parents=True, exist_ok=True)
        for src in sorted(GUARDS_DIR.iterdir()):
            if src.is_file():
                shutil.copy2(src, dest / src.name)


def _seed_v1(repo: Repo) -> None:
    """The frozen v1 material: ``src/``, ``tests/``, root pyproject, lock."""
    repo.write("src/chronos/__init__.py", '"""v1. Frozen."""\n')
    repo.write("src/chronos/run.py", "def trial():\n    return 1\n")
    repo.write("tests/test_v1.py", "def test_v1():\n    assert True\n")
    repo.write("pyproject.toml", '[project]\nname = "chronos"\nversion = "1.0.0"\n')
    repo.write("uv.lock", "version = 1\n")


def _seed_v2(repo: Repo) -> None:
    """Enough of the v2 tree for the guards to have something to judge."""
    repo.write("CLAUDE.md", "# CLAUDE.md\n\nRoot instruction file. The only one allowed.\n")
    repo.write("v2/src/chronos2/__init__.py", '"""v2."""\n')
    repo.write("v2/src/chronos2/core/canonical.py", "def canon(x):\n    return x\n")
    repo.write("v2/tests/conftest.py", '"""Deliberately empty."""\n')
    repo.write("v2/tests/core/test_canonical.py", "def test_canon():\n    assert 1 == 1\n")
    repo.write("v2/tools/v1_oracle/dump_stats.py", "print('oracle')\n")
    repo.write("v2/migrations/0001_init.sql", "-- init\n")
    repo.write(
        "v2/pyproject.toml",
        "[project]\n"
        'name = "chronos2"\n'
        'version = "0.1.0"\n'
        "dependencies = [\n"
        '    "numpy",\n'
        "]\n"
        "\n"
        "[dependency-groups]\n"
        'dev = [\n    "pytest",\n]\n'
        "\n"
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n',
    )
    repo.write("v2/uv.lock", 'version = 1\n\n[[package]]\nname = "numpy"\nversion = "2.0.0"\n')
    repo.write("docs/v2/CHRONOS_V2.md", "# CHRONOS v2 -- the master document\n")
    repo.write("docs/v2/build/LADDER.yaml", "builds: []\n")
    repo.write("docs/v2/build/BLUEPRINT.md", "# blueprint\n")
    repo.write("docs/v2/build/BUILD_CARDS.md", "# cards\n")
    repo.write("docs/v2/build/LEDGER.md", "# ledger\n")
    repo.write("docs/v2/build/gates/G0-report.md", "# G0\n")
    repo.write("docs/v2/CHANGELOG.md", "# changelog\n")
    repo.write("docs/v2/BUILD_NOTES.md", "# build notes\n")


@pytest.fixture
def repo_factory(tmp_path):
    """Build a repo with ``v1-final`` and a base branch, then hand it back.

    The returned callable takes the base branch name (default ``v2-build``) and
    the spec to put on the base, and leaves the repo checked out on the base.
    """
    counter = {"n": 0}

    def build(
        base: str = "v2-build",
        spec_for: str | None = "b06",
        touches: list[str] | None = None,
        may_modify_tests: list[str] | None = None,
        adds_dependencies: list[str] | None = None,
    ) -> Repo:
        counter["n"] += 1
        repo = Repo(tmp_path / f"repo{counter['n']}")
        _seed_v1(repo)
        repo.commit("v1 as frozen", role="builder")
        repo.git("branch", "v1-final")
        _seed_v2(repo)
        if spec_for is not None:
            repo.spec(
                spec_for,
                touches if touches is not None else ["v2/src/chronos2/stats/**"],
                may_modify_tests,
                adds_dependencies,
            )
        repo.commit("v2 base", role="builder")
        repo.git("branch", base)
        repo.checkout(base)
        return repo

    return build
