"""The ``earlier-tests`` job: the earlier builds' tests, run as they were
approved, against this pull request's code.

The shape of this job is the answer to red-team finding f, which demonstrated
two ways of switching an earlier test off without editing it. So:

* the tree starts as a clean checkout of the **base commit**, and from the pull
  request it takes **only** ``v2/src/chronos2/**``,
  ``v2/migrations/**``, ``v2/pyproject.toml``, ``v2/uv.lock`` and any test file
  the base spec lists in ``may_modify_tests``. Everything else under ``v2/`` --
  the tests, every ``conftest.py``, any ``pytest.ini``, ``tox.ini`` or
  ``setup.cfg``, anything else beside the package -- is the base's copy, so
  nothing the pull request added there is present at all;

  The spec describes this tree as the base commit's ``v2/`` folder. It is the
  whole base checkout instead, which is the spec's own standard for the
  comparison ("the set collected on an untouched base checkout") and is needed
  for a plain reason: B01's ``tests/test_workflow_file.py`` reads
  ``.github/workflows/v2.yml``, outside ``v2/``. With a ``v2/``-only tree that
  test, and any later one like it, fails on every pull request for a reason
  that has nothing to do with the pull request. Widening the tree is strictly
  the safer direction -- everything outside the four taken paths is still the
  base's copy -- and it is recorded as a deviation in the build report;
* entry-point plugin loading is off, so a plugin cannot arrive through the lock
  file;
* the base's pytest settings are applied with ``-c``, with ``addopts`` emptied
  and the conftest search cut off at the tests folder;
* and it fails unless the set of test ids that ran equals the set collected on
  an untouched base checkout.

What it still does not stop: new *package* code defeating a test from the
inside. The reviewer's reading of the source diff, the sabotage run (B22) and
blind re-derivation at the gate are what catch that.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# The only paths taken from the pull request.
FROM_HEAD_DIRS = ("v2/src/chronos2", "v2/migrations")
FROM_HEAD_FILES = ("v2/pyproject.toml", "v2/uv.lock")


@dataclass
class Result:
    ok: bool
    reason: str
    base_ids: list[str] = field(default_factory=list)
    ran_ids: list[str] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)
    skipped_ids: list[str] = field(default_factory=list)
    command: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    tree: Path | None = None
    config_file: Path | None = None
    returncode: int = 0
    output: str = ""


def run(
    repo: Path,
    base_sha: str,
    head_sha: str,
    workdir: Path,
    may_modify_tests: list[str] | None = None,
    python: str | None = None,
) -> Result:
    may_modify_tests = may_modify_tests or []
    python = python or _default_python()
    workdir.mkdir(parents=True, exist_ok=True)

    base_tree = workdir / "base" / "v2"
    _export(repo, base_sha, workdir / "base")
    if not (base_tree / "tests").is_dir():
        return Result(
            ok=True,
            reason="the base commit has no v2/tests/, so there are no earlier tests to run.",
            tree=base_tree,
        )

    # The base's pytest settings, saved outside both trees so neither the base
    # nor the pull request can be the thing that supplies them.
    config_file = workdir / "base-config" / "pyproject.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base_tree / "pyproject.toml", config_file)

    hybrid = workdir / "hybrid" / "v2"
    _build_hybrid(repo, base_sha, head_sha, workdir, may_modify_tests)

    env = _env(hybrid)
    base_ids = _collect(python, base_tree, config_file, _env(base_tree))
    ran_ids = _collect(python, hybrid, config_file, env)

    junit = workdir / "junit.xml"
    command = [
        python,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-c",
        str(config_file),
        "--rootdir",
        str(hybrid),
        "--confcutdir",
        str(hybrid / "tests"),
        "-o",
        "addopts=",
        f"--junitxml={junit}",
        "-q",
        "tests",
    ]
    done = subprocess.run(
        command, cwd=hybrid, capture_output=True, text=True, env=env, check=False
    )
    failed, skipped = _outcomes(junit)

    result = Result(
        ok=False,
        reason="",
        base_ids=base_ids,
        ran_ids=ran_ids,
        failed_ids=failed,
        skipped_ids=skipped,
        command=command,
        env=env,
        tree=hybrid,
        config_file=config_file,
        returncode=done.returncode,
        output=done.stdout + done.stderr,
    )
    result.reason = _verdict(result)
    result.ok = result.reason == ""
    if result.ok:
        result.reason = f"the base's {len(base_ids)} earlier tests all ran and all passed."
    return result


def _verdict(result: Result) -> str:
    """Empty means green. Order matters: the count check is named first so a
    dropped test is never reported as a mere failure."""
    missing = sorted(set(result.base_ids) - set(result.ran_ids))
    extra = sorted(set(result.ran_ids) - set(result.base_ids))
    if missing or extra:
        return (
            f"the set of test ids that ran is not the set the base collects. "
            f"Missing {len(missing)}: {missing[:8]}. Unexpected {len(extra)}: {extra[:8]}. "
            "The earlier builds' tests run as they were approved; a pull request cannot "
            "change which of them count."
        )
    if result.skipped_ids:
        return f"earlier tests were skipped or expected-to-fail: {result.skipped_ids[:8]}."
    if result.failed_ids:
        return f"earlier tests failed against this pull request's code: {result.failed_ids[:8]}."
    if result.returncode != 0:
        return f"pytest exited {result.returncode} with no failure recorded:\n{result.output[-2000:]}"
    return ""


def _default_python() -> str:
    import sys

    return sys.executable


def _env(tree: Path) -> dict[str, str]:
    """Plugin auto-loading off; UTC; the package found in the tree being judged.

    ``PYTHONPATH`` pointing at the tree's ``src`` is also what makes trick 3
    faithful: a ``sitecustomize.py`` in ``v2/src/`` would be imported at
    interpreter start if it were there, and it is not, because the job does not
    take it.
    """
    return {
        **os.environ,
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "TZ": "UTC",
        "PYTHONPATH": str(tree / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _export(repo: Path, sha: str, into: Path) -> None:
    """The whole tree at ``sha``, as files, with no git history and no working
    copy of the branch anywhere near it."""
    into.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ("git", "-C", str(repo), "archive", sha),
        capture_output=True,
        check=True,
    )
    subprocess.run(("tar", "-x", "-C", str(into)), input=archive.stdout, check=True)


def _build_hybrid(
    repo: Path, base_sha: str, head_sha: str, workdir: Path, may_modify_tests: list[str]
) -> None:
    base = workdir / "base"
    hybrid_root = workdir / "hybrid"
    hybrid_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(base, hybrid_root, dirs_exist_ok=True)

    head = workdir / "head"
    _export(repo, head_sha, head)

    for rel in FROM_HEAD_DIRS:
        target = hybrid_root / rel
        if target.exists():
            shutil.rmtree(target)
        source = head / rel
        if source.exists():
            shutil.copytree(source, target)

    for rel in FROM_HEAD_FILES + tuple(may_modify_tests):
        target = hybrid_root / rel
        source = head / rel
        if target.exists():
            target.unlink()
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _collect(python: str, tree: Path, config_file: Path, env: dict[str, str]) -> list[str]:
    done = subprocess.run(
        [
            python,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-c",
            str(config_file),
            "--rootdir",
            str(tree),
            "--confcutdir",
            str(tree / "tests"),
            "-o",
            "addopts=",
            "tests",
        ],
        cwd=tree,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    ids: list[str] = []
    for line in done.stdout.split("\n"):
        line = line.strip()
        if "::" in line and not line.startswith(("<", "=", "E ", "ERROR")):
            ids.append(line)
    return sorted(set(ids))


def _outcomes(junit: Path) -> tuple[list[str], list[str]]:
    if not junit.exists():
        return [], []
    root = ET.parse(junit).getroot()
    failed: list[str] = []
    skipped: list[str] = []
    for case in root.iter("testcase"):
        name = ".".join(p for p in (case.get("classname"), case.get("name")) if p)
        if case.find("failure") is not None or case.find("error") is not None:
            failed.append(name)
        elif case.find("skipped") is not None:
            skipped.append(name)
    return sorted(failed), sorted(skipped)
