"""B02 known answers for the ``earlier-tests`` job.

The scenario the spec names: a temp repository with **one passing and one
failing earlier test**. Each case must end with the failing test still failing
and the job red. The four tricks are the ones the third red-team pass found
(finding f); it ran the first two for real against a simpler version of this
job, on pytest 9.1.1, and both beat it.

The job starts from a clean checkout of the **base** commit's ``v2/`` folder and
takes from the pull request only ``v2/src/chronos2/**``, ``v2/migrations/**``,
``v2/pyproject.toml``, ``v2/uv.lock`` and any test file the base spec lists in
``may_modify_tests``. So each trick is still *in the pull request* and simply
never reaches the tree the tests run in.
"""

from __future__ import annotations

import earlier_tests


def seed_earlier_tests(repo) -> None:
    """One passing and one failing earlier test, on the base."""
    repo.write("v2/tests/earlier/test_ok.py", "def test_ok():\n    assert 1 == 1\n")
    repo.write(
        "v2/tests/earlier/test_edge.py",
        "from chronos2.core.canonical import canon\n\n\n"
        "def test_edge():\n"
        "    assert canon('raw') == 'CANON'\n",
    )
    repo.commit("earlier build: two tests, one of them failing")


def run_job(repo, tmp_path, name, may_modify_tests=None):
    return earlier_tests.run(
        repo=repo.path,
        base_sha=repo.sha("v2-build"),
        head_sha=repo.sha(),
        workdir=tmp_path / f"job-{name}",
        may_modify_tests=may_modify_tests or [],
    )


def assert_red_and_edge_still_failing(result):
    assert not result.ok, f"the job must be red; reason given: {result.reason}"
    failing = " ".join(result.failed_ids)
    assert "test_edge" in failing, (
        "the earlier failing test must still be failing; the trick must not have "
        f"removed or silenced it. ran={result.ran_ids} failed={result.failed_ids}"
    )


# --- the four tricks -------------------------------------------------------


def test_a_conftest_beside_the_package_cannot_drop_a_test(repo_factory, tmp_path):
    """Trick 1: a ``v2/conftest.py`` whose hook name is built from two strings,
    so a text scan for ``pytest_`` does not see it, dropping the failing test."""
    repo = repo_factory()
    seed_earlier_tests(repo)
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/conftest.py",
        "_a = 'pytest_collection'\n"
        "_b = '_modifyitems'\n"
        "\n"
        "def _drop(config, items):\n"
        "    items[:] = [i for i in items if 'test_edge' not in i.nodeid]\n"
        "\n"
        "globals()[_a + _b] = _drop\n",
    )
    repo.commit("B06 step 1: a conftest above the tests folder")
    assert_red_and_edge_still_failing(run_job(repo, tmp_path, "conftest"))


def test_a_pytest_ini_cannot_narrow_what_counts_as_a_test(repo_factory, tmp_path):
    """Trick 2: ``v2/pytest.ini`` with ``python_functions = test_ok``, so only
    the passing test is collected."""
    repo = repo_factory()
    seed_earlier_tests(repo)
    repo.checkout("claude/b06", create=True)
    repo.write("v2/pytest.ini", "[pytest]\npython_functions = test_ok\ntestpaths = tests\n")
    repo.commit("B06 step 1: a pytest.ini beside the package")
    assert_red_and_edge_still_failing(run_job(repo, tmp_path, "pytestini"))


def test_a_sitecustomize_cannot_patch_the_package(repo_factory, tmp_path):
    """Trick 3: ``v2/src/sitecustomize.py`` -- imported automatically at
    interpreter start -- patching the package so the failing test passes. It
    sits beside the package, not inside it, so the job never takes it."""
    repo = repo_factory()
    seed_earlier_tests(repo)
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/src/sitecustomize.py",
        "import chronos2.core.canonical as c\n\nc.canon = lambda x: 'CANON'\n",
    )
    repo.commit("B06 step 1: a sitecustomize beside the package")
    result = run_job(repo, tmp_path, "sitecustomize")
    assert_red_and_edge_still_failing(result)
    assert not (result.tree / "src" / "sitecustomize.py").exists(), (
        "only v2/src/chronos2/** is taken from the pull request, not all of v2/src/"
    )


def test_a_plugin_added_to_the_lock_file_is_not_loaded(repo_factory, tmp_path):
    """Trick 4: a pytest plugin pulled in through ``uv.lock`` alone.

    What this test proves: the lock file *is* one of the four paths taken from
    the pull request, and the job still runs with entry-point plugin loading
    switched off, and the failing test still fails. What it does **not** do is
    install a real distribution into a temp environment and watch it not load --
    that is outside this build's size. The control under test is the
    ``PYTEST_DISABLE_PLUGIN_AUTOLOAD`` flag, asserted on the command the job
    actually runs. ``plumbing`` separately fails any lock change in a build whose
    spec names no new library, and the lock file is founder-owned.
    """
    repo = repo_factory(touches=["v2/uv.lock"], adds_dependencies=["pytest-sneaky"])
    seed_earlier_tests(repo)
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/uv.lock",
        'version = 1\n\n[[package]]\nname = "numpy"\nversion = "2.0.0"\n'
        '\n[[package]]\nname = "pytest-sneaky"\nversion = "0.1.0"\n',
    )
    repo.commit("B06 step 1: a plugin in the lock file only")
    result = run_job(repo, tmp_path, "lock")
    assert_red_and_edge_still_failing(result)
    assert "pytest-sneaky" in (result.tree / "uv.lock").read_text(), (
        "the lock file is taken from the pull request, so the trick is in the tree"
    )
    assert result.env.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"


# --- the count case --------------------------------------------------------


def test_the_job_is_red_when_fewer_tests_run_than_the_base_collects(repo_factory, tmp_path):
    """"one case that must be red for the count: the pull request deletes
    nothing but the run reports fewer test ids than the base's collection."

    Here the package raises on import, so a whole earlier test file errors out
    and never yields its test id. Nothing was deleted; the count still drops.
    """
    repo = repo_factory()
    seed_earlier_tests(repo)
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/src/chronos2/core/canonical.py",
        "raise RuntimeError('this module no longer imports')\n",
    )
    repo.commit("B06 step 1: the package no longer imports")
    result = run_job(repo, tmp_path, "count")
    assert not result.ok
    assert len(result.ran_ids) < len(result.base_ids), (
        f"base collected {result.base_ids}, the run produced {result.ran_ids}"
    )
    assert "collected" in result.reason.lower() or "count" in result.reason.lower()


# --- the controls ----------------------------------------------------------


def test_the_job_is_green_when_the_pull_request_fixes_the_failing_test(repo_factory, tmp_path):
    """The control that must succeed: an honest change to the package, inside
    the one folder the job takes, turns the earlier failing test green."""
    repo = repo_factory()
    seed_earlier_tests(repo)
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/core/canonical.py", "def canon(x):\n    return 'CANON'\n")
    repo.commit("B06 step 1: make the earlier test pass honestly")
    result = run_job(repo, tmp_path, "honest")
    assert result.ok, f"reason: {result.reason} failed={result.failed_ids}"
    assert set(result.ran_ids) == set(result.base_ids)


def test_the_job_passes_trivially_when_the_base_has_no_tests_folder(repo_factory, tmp_path):
    repo = repo_factory()
    # The factory leaves us on v2-build, so this commit moves the base itself.
    repo.git("rm", "-r", "-q", "v2/tests")
    repo.commit("a base with no v2/tests/")
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "def dsr():\n    return 0.0\n")
    repo.commit("B06 step 1")
    result = run_job(repo, tmp_path, "notests")
    assert result.ok
    assert "no v2/tests" in result.reason


def test_a_test_file_the_base_spec_allows_is_taken_from_the_pull_request(repo_factory, tmp_path):
    """``may_modify_tests`` is the one exception: that file comes from the pull
    request, and the collected set is compared against the base's with it
    applied."""
    repo = repo_factory(may_modify_tests=["v2/tests/earlier/test_edge.py"])
    seed_earlier_tests(repo)
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/tests/earlier/test_edge.py",
        "from chronos2.core.canonical import canon\n\n\n"
        "def test_edge():\n"
        "    assert canon('raw') == 'raw'\n",
    )
    repo.commit("B06 step 1: the edit the spec allows")
    result = run_job(
        repo, tmp_path, "maymodify", may_modify_tests=["v2/tests/earlier/test_edge.py"]
    )
    assert result.ok, f"reason: {result.reason} failed={result.failed_ids}"


def test_the_command_carries_every_setting_the_spec_names(repo_factory, tmp_path):
    repo = repo_factory()
    seed_earlier_tests(repo)
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "def dsr():\n    return 0.0\n")
    repo.commit("B06 step 1")
    result = run_job(repo, tmp_path, "command")
    command = " ".join(result.command)
    assert "-p no:cacheprovider" in command
    assert '-o addopts=' in command
    assert "--confcutdir" in command
    assert "-c " in command, "the base's pytest settings are applied with -c"
    assert result.config_file.name == "pyproject.toml"
    assert result.env.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"
    assert result.env.get("TZ") == "UTC"
