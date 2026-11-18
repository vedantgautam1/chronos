"""B02 known answers: one failing and one passing case per guard rule.

Every case is a throwaway git repository built in a temp folder (spec step 1).
The table in ``specs/B02-guards.md`` under "Known answers and checks" is the
source for every case here; the docstrings name the row.
"""

from __future__ import annotations

import checks
from conftest import spec_text
from gitrepo import Context


def context(repo, head_ref="claude/b06", base_ref="v2-build", base=None, is_fork=False):
    return Context(
        repo=repo.path,
        base_sha=base if base is not None else repo.sha(base_ref),
        head_sha=repo.sha(),
        head_ref=head_ref,
        base_ref=base_ref,
        is_fork=is_fork,
    )


def text(findings) -> str:
    return " | ".join(f"{f.guard}: {f.message}" for f in findings)


# --------------------------------------------------------------------------
# v1_frozen -- "a comment added to a v1 file" / "no v1 change"
# --------------------------------------------------------------------------


def test_v1_frozen_fails_on_a_comment_added_to_a_v1_file(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("src/chronos/run.py", "# a harmless comment\ndef trial():\n    return 1\n")
    repo.commit("B06 step 1: touch v1")
    found = checks.v1_frozen(context(repo))
    assert found, "a change to src/chronos/run.py must be caught"
    assert "src/chronos/run.py" in text(found)


def test_v1_frozen_passes_when_v1_is_untouched(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "def dsr():\n    return 0.0\n")
    repo.commit("B06 step 1: v2 only")
    assert checks.v1_frozen(context(repo)) == []


def test_v1_frozen_catches_the_root_lock_and_pyproject(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("uv.lock", "version = 1\n# added\n")
    repo.commit("B06 step 1: touch the v1 lock")
    assert "uv.lock" in text(checks.v1_frozen(context(repo)))


# --------------------------------------------------------------------------
# branch_kind -- the must-fail and must-pass rows, in order
# --------------------------------------------------------------------------


def test_branch_kind_fails_on_an_unknown_branch_name(repo_factory):
    repo = repo_factory()
    repo.checkout("feature/x", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("feature work")
    assert checks.branch_kind(context(repo, head_ref="feature/x"))


def test_branch_kind_fails_on_a_one_digit_build_id(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b6", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B6 step 1")
    assert checks.branch_kind(context(repo, head_ref="claude/b6"))


def test_branch_kind_fails_on_a_suffixed_build_branch(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06-stats", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B06 step 1")
    assert checks.branch_kind(context(repo, head_ref="claude/b06-stats"))


def test_branch_kind_fails_when_a_gate_branch_touches_source(repo_factory):
    repo = repo_factory()
    repo.checkout("gate/g1", create=True)
    repo.write("docs/v2/build/gates/G1-report.md", "# G1\n")
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("G1 write-up plus a sneaky source change")
    found = checks.branch_kind(context(repo, head_ref="gate/g1"))
    assert found
    assert "v2/src/chronos2/stats/dsr.py" in text(found)


def test_branch_kind_fails_when_a_doc_branch_touches_source(repo_factory):
    repo = repo_factory()
    repo.checkout("doc/x", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("doc branch touching source")
    assert checks.branch_kind(context(repo, head_ref="doc/x"))


def test_branch_kind_fails_on_a_gate_move_without_the_gate_report(repo_factory):
    repo = repo_factory(base="main")
    repo.checkout("v2-build", create=True)
    repo.write("docs/v2/CHANGELOG.md", "# changelog\n\n## something\n")
    repo.commit("work, but no gate report")
    found = checks.branch_kind(context(repo, head_ref="v2-build", base_ref="main"))
    assert found
    assert "gate report" in text(found).lower()


def test_branch_kind_fails_on_a_head_branch_from_a_fork(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B06 step 1")
    found = checks.branch_kind(context(repo, is_fork=True))
    assert found
    assert "fork" in text(found).lower()


def test_branch_kind_passes_a_build_branch(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B06 step 1")
    assert checks.branch_kind(context(repo)) == []


def test_branch_kind_passes_a_suffixed_build_id_that_is_on_the_ladder(repo_factory):
    """``claude/b01a`` is a real build branch (B01A). Two digits plus one
    letter is the id; ``claude/b6`` and ``claude/b06-stats`` are not."""
    repo = repo_factory(spec_for="b01a")
    repo.checkout("claude/b01a", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B01A step 1")
    assert checks.branch_kind(context(repo, head_ref="claude/b01a")) == []


def test_branch_kind_passes_a_lane_branch(repo_factory):
    repo = repo_factory()
    repo.checkout("lane/notes", create=True)
    repo.write("scratch/note.md", "a note\n")
    repo.commit("lane note")
    assert checks.branch_kind(context(repo, head_ref="lane/notes")) == []


def test_branch_kind_passes_a_spec_correction(repo_factory):
    repo = repo_factory()
    repo.checkout("spec/b10-fix", create=True)
    repo.write("docs/v2/build/specs/B10-trial-ontology.md", "# B10\n")
    repo.commit("spec correction")
    assert checks.branch_kind(context(repo, head_ref="spec/b10-fix")) == []


def test_branch_kind_passes_a_doc_branch_touching_the_master_doc(repo_factory):
    repo = repo_factory()
    repo.checkout("doc/decision-52", create=True)
    repo.write("docs/v2/CHRONOS_V2.md", "# CHRONOS v2\n\nV2-D52.\n")
    repo.commit("decision 52")
    assert checks.branch_kind(context(repo, head_ref="doc/decision-52")) == []


def test_branch_kind_passes_a_gate_writeup(repo_factory):
    repo = repo_factory()
    repo.checkout("gate/g1", create=True)
    repo.write("docs/v2/build/gates/G1-report.md", "# G1\n")
    repo.write("docs/v2/CHRONOS_V2.md", "# CHRONOS v2\n\nstatus board updated\n")
    repo.commit("G1 write-up")
    assert checks.branch_kind(context(repo, head_ref="gate/g1")) == []


def test_branch_kind_passes_a_gate_move_with_the_gate_report(repo_factory):
    repo = repo_factory(base="main")
    repo.checkout("v2-build", create=True)
    repo.write("docs/v2/build/gates/G1-report.md", "# G1\n")
    repo.commit("the G1 report")
    assert checks.branch_kind(context(repo, head_ref="v2-build", base_ref="main")) == []


# --------------------------------------------------------------------------
# scope -- inside / outside touches, and the base's copy of the spec
# --------------------------------------------------------------------------


def test_scope_fails_on_a_path_outside_touches(repo_factory):
    repo = repo_factory(touches=["v2/src/chronos2/stats/**"])
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/core/newthing.py", "x = 1\n")
    repo.commit("B06 step 1: outside touches")
    found = checks.scope(context(repo))
    assert found
    assert "v2/src/chronos2/core/newthing.py" in text(found)


def test_scope_passes_inside_touches(repo_factory):
    repo = repo_factory(touches=["v2/src/chronos2/stats/**"])
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B06 step 1: inside touches")
    assert checks.scope(context(repo)) == []


def test_scope_allows_the_builders_own_report_changelog_and_status(repo_factory):
    repo = repo_factory(touches=["v2/src/chronos2/stats/**"])
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.write("docs/v2/build/reports/B06.md", "# B06\n")
    repo.write("docs/v2/build/status/B06.json", '{"build": "B06", "state": "building"}\n')
    repo.write("docs/v2/CHANGELOG.md", "# changelog\n\n## B06\n")
    repo.commit("B06 step 1")
    assert checks.scope(context(repo)) == []


def test_scope_reads_touches_from_the_base_not_the_branch(repo_factory):
    """The must-fail row: the branch edits its own spec to add a path, then
    changes that path. ``touches`` comes from the base commit, so it still
    fails -- and ``protected`` separately refuses the spec edit."""
    repo = repo_factory(touches=["v2/src/chronos2/stats/**"])
    repo.checkout("claude/b06", create=True)
    repo.write(
        "docs/v2/build/specs/B06-throwaway.md",
        spec_text("b06", ["v2/src/chronos2/stats/**", "v2/src/chronos2/core/**"], [], []),
    )
    repo.write("v2/src/chronos2/core/newthing.py", "x = 1\n")
    repo.commit("B06 step 1: widen my own spec, then use it")
    found = checks.scope(context(repo))
    assert found, "touches must be read from the base commit's spec"
    assert "v2/src/chronos2/core/newthing.py" in text(found)


# --------------------------------------------------------------------------
# roles
# --------------------------------------------------------------------------


def test_roles_fails_on_a_commit_with_no_trailer(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B06 step 1: no role", role=None)
    found = checks.roles(context(repo))
    assert found
    assert "trailer" in text(found).lower()


def test_roles_fails_when_a_builder_writes_a_review(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("docs/v2/build/reviews/b06-r1.md", "verdict: PASS\n")
    repo.commit("B06: review myself", role="builder")
    found = checks.roles(context(repo))
    assert found
    assert "review" in text(found).lower()


def test_roles_fails_when_a_builder_sets_status_merged(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("docs/v2/build/status/B06.json", '{"build": "B06", "state": "merged"}\n')
    repo.commit("B06: merge myself", role="builder")
    found = checks.roles(context(repo))
    assert found
    assert "merged" in text(found)


def test_roles_fails_when_a_reviewer_touches_source(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B06 step 1", role="builder")
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 2\n")
    repo.commit("B06 review: just a one-character fix", role="reviewer")
    found = checks.roles(context(repo))
    assert found
    assert "reviewer" in text(found).lower()


def test_roles_fails_when_passed_names_an_older_code_commit(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    first = repo.commit("B06 step 1", role="builder")
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 2\n")
    repo.commit("B06 step 2", role="builder")
    repo.write("docs/v2/build/reviews/B06-r1.md", f"code commit reviewed: {first}\nverdict: PASS\n")
    repo.write("docs/v2/build/status/B06.json", '{"build": "B06", "state": "passed"}\n')
    repo.commit("B06 review r1: PASS", role="reviewer")
    found = checks.roles(context(repo))
    assert found
    assert "code commit" in text(found).lower()


def test_roles_passes_builder_then_reviewer_then_merge_in_order(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 1\n")
    repo.commit("B06 step 1", role="builder")
    repo.write("v2/src/chronos2/stats/dsr.py", "x = 2\n")
    last_code = repo.commit("B06 step 2", role="builder")
    repo.write(
        "docs/v2/build/reviews/B06-r1.md",
        f"code commit reviewed: {last_code}\nverdict: PASS\n",
    )
    repo.write("docs/v2/build/status/B06.json", '{"build": "B06", "state": "passed"}\n')
    repo.commit("B06 review r1: PASS", role="reviewer")
    repo.write("docs/v2/build/LEDGER.md", "# ledger\n\n| B06 | 2 ticks |\n")
    repo.write("docs/v2/build/status/B06.json", '{"build": "B06", "state": "merged"}\n')
    repo.commit("B06: ledger row, status merged", role="reviewer")
    assert checks.roles(context(repo)) == []


# --------------------------------------------------------------------------
# frozen_files
# --------------------------------------------------------------------------


def test_frozen_files_fails_when_an_assertion_is_loosened(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/tests/core/test_canonical.py", "def test_canon():\n    assert 1 >= 1\n")
    repo.commit("B06 step 1: loosen an earlier assertion")
    found = checks.frozen_files(context(repo))
    assert found
    assert "v2/tests/core/test_canonical.py" in text(found)


def test_frozen_files_fails_when_an_existing_test_file_is_deleted(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.remove("v2/tests/core/test_canonical.py")
    repo.commit("B06 step 1: delete an earlier test")
    assert checks.frozen_files(context(repo))


def test_frozen_files_fails_when_an_existing_test_file_is_renamed(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.move("v2/tests/core/test_canonical.py", "v2/tests/core/test_canonical_old.py")
    repo.commit("B06 step 1: rename an earlier test")
    assert checks.frozen_files(context(repo))


def test_frozen_files_fails_when_an_oracle_dump_script_is_emptied(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/tools/v1_oracle/dump_stats.py", "")
    repo.commit("B06 step 1: empty the oracle")
    assert "dump_stats.py" in text(checks.frozen_files(context(repo)))


def test_frozen_files_fails_when_an_existing_migration_is_edited(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/migrations/0001_init.sql", "-- init\n-- and an edit\n")
    repo.commit("B06 step 1: edit an earlier migration")
    assert "0001_init.sql" in text(checks.frozen_files(context(repo)))


def test_frozen_files_passes_new_test_dump_and_migration_files(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/tests/stats/test_dsr.py", "def test_dsr():\n    assert 1 == 1\n")
    repo.write("v2/tools/v1_oracle/dump_dsr.py", "print('dsr')\n")
    repo.write("v2/migrations/0002_trials.sql", "-- trials\n")
    repo.commit("B06 step 1: all new files")
    assert checks.frozen_files(context(repo)) == []


def test_frozen_files_passes_a_file_the_base_spec_lists_in_may_modify_tests(repo_factory):
    repo = repo_factory(may_modify_tests=["v2/tests/core/test_canonical.py"])
    repo.checkout("claude/b06", create=True)
    repo.write("v2/tests/core/test_canonical.py", "def test_canon():\n    assert 2 == 2\n")
    repo.commit("B06 step 1: an edit the spec allows")
    assert checks.frozen_files(context(repo)) == []


# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------


def test_plumbing_fails_on_an_instruction_file_in_a_source_folder(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/CLAUDE.md", "# read me, later session\n")
    repo.commit("B06 step 1: plant an instruction file")
    found = checks.plumbing(context(repo))
    assert found
    assert "CLAUDE.md" in text(found)


def test_plumbing_fails_on_a_dot_claude_folder_below_the_root(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/.claude/settings.json", "{}\n")
    repo.commit("B06 step 1: a .claude folder under v2")
    assert ".claude" in text(checks.plumbing(context(repo)))


def test_plumbing_fails_on_a_conftest_hook(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/tests/stats/conftest.py",
        "def pytest_collection_modifyitems(items):\n    items[:] = []\n",
    )
    repo.commit("B06 step 1: a collection hook")
    assert "pytest_collection_modifyitems" in text(checks.plumbing(context(repo)))


def test_plumbing_fails_on_a_hook_in_a_test_file(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/tests/stats/test_dsr.py",
        "def pytest_runtest_makereport(item, call):\n    return None\n",
    )
    repo.commit("B06 step 1: a report hook")
    assert "pytest_runtest_makereport" in text(checks.plumbing(context(repo)))


def test_plumbing_fails_on_pytest_plugins(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write("v2/tests/stats/conftest.py", 'pytest_plugins = ["mything"]\n')
    repo.commit("B06 step 1: pytest_plugins")
    assert "pytest_plugins" in text(checks.plumbing(context(repo)))


def test_plumbing_fails_on_addopts_in_pyproject(repo_factory):
    repo = repo_factory(touches=["v2/pyproject.toml"])
    repo.checkout("claude/b06", create=True)
    pyproject = (repo.path / "v2" / "pyproject.toml").read_text()
    repo.write(
        "v2/pyproject.toml",
        pyproject.replace('testpaths = ["tests"]', 'testpaths = ["tests"]\naddopts = "-k not slow"'),
    )
    repo.commit("B06 step 1: addopts")
    assert "addopts" in text(checks.plumbing(context(repo)))


def test_plumbing_fails_on_an_entry_points_table(repo_factory):
    repo = repo_factory(touches=["v2/pyproject.toml"])
    repo.checkout("claude/b06", create=True)
    pyproject = (repo.path / "v2" / "pyproject.toml").read_text()
    repo.write(
        "v2/pyproject.toml",
        pyproject + '\n[project.entry-points.pytest11]\nmine = "mything"\n',
    )
    repo.commit("B06 step 1: a pytest11 entry point")
    assert "entry-points" in text(checks.plumbing(context(repo)))


def test_plumbing_fails_on_a_dependency_the_base_spec_does_not_name(repo_factory):
    repo = repo_factory(touches=["v2/pyproject.toml"], adds_dependencies=[])
    repo.checkout("claude/b06", create=True)
    pyproject = (repo.path / "v2" / "pyproject.toml").read_text()
    repo.write("v2/pyproject.toml", pyproject.replace('    "numpy",', '    "numpy",\n    "arch",'))
    repo.commit("B06 step 1: an unnamed dependency")
    found = checks.plumbing(context(repo))
    assert found
    assert "arch" in text(found)


def test_plumbing_fails_on_a_lock_change_with_no_adds_dependencies(repo_factory):
    repo = repo_factory(touches=["v2/uv.lock"], adds_dependencies=[])
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/uv.lock",
        'version = 1\n\n[[package]]\nname = "numpy"\nversion = "2.0.0"\n'
        '\n[[package]]\nname = "pytest-sneaky"\nversion = "0.1.0"\n',
    )
    repo.commit("B06 step 1: a lock-only library")
    found = checks.plumbing(context(repo))
    assert found
    assert "pytest-sneaky" in text(found), "the added package must be named in the finding"


def test_plumbing_passes_a_conftest_with_fixtures_only(repo_factory):
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/tests/stats/conftest.py",
        "import pytest\n\n\n@pytest.fixture\ndef sample():\n    return [1.0, 2.0]\n",
    )
    repo.commit("B06 step 1: fixtures only")
    assert checks.plumbing(context(repo)) == []


def test_plumbing_passes_a_dependency_the_base_spec_names(repo_factory):
    repo = repo_factory(touches=["v2/pyproject.toml", "v2/uv.lock"], adds_dependencies=["arch"])
    repo.checkout("claude/b06", create=True)
    pyproject = (repo.path / "v2" / "pyproject.toml").read_text()
    repo.write("v2/pyproject.toml", pyproject.replace('    "numpy",', '    "numpy",\n    "arch",'))
    repo.write(
        "v2/uv.lock",
        'version = 1\n\n[[package]]\nname = "numpy"\nversion = "2.0.0"\n'
        '\n[[package]]\nname = "arch"\nversion = "7.0.0"\n',
    )
    repo.commit("B06 step 1: the dependency the spec names")
    assert checks.plumbing(context(repo)) == []


def test_plumbing_reports_an_autouse_fixture_without_failing(repo_factory):
    """"every ``autouse=True`` fixture in the diff is printed for the reviewer"
    -- printed, not failed."""
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.write(
        "v2/tests/stats/conftest.py",
        "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef env():\n    return None\n",
    )
    repo.commit("B06 step 1: an autouse fixture")
    found = checks.plumbing(context(repo))
    notes = checks.notes(context(repo))
    assert found == [], "an autouse fixture is reported, not a finding"
    assert "autouse" in " ".join(n.message for n in notes)


# --------------------------------------------------------------------------
# protected
# --------------------------------------------------------------------------


def test_protected_fails_when_a_build_changes_a_protected_value_it_does_not_own(repo_factory):
    repo = repo_factory(touches=["v2/src/chronos2/stats/**"])
    repo.checkout("claude/b06", create=True)
    repo.write("v2/config/protected/validation.yaml", "stress_friction_multiplier: 1.0\n")
    repo.commit("B06 step 1: loosen a protected value")
    found = checks.protected(context(repo))
    assert found
    assert "validation.yaml" in text(found)


def test_protected_fails_when_a_build_changes_a_guard_it_does_not_own(repo_factory):
    repo = repo_factory(touches=["v2/src/chronos2/stats/**"])
    repo.checkout("claude/b06", create=True)
    repo.write("v2/tools/guards/run_all.py", "raise SystemExit(0)\n")
    repo.commit("B06 step 1: neuter the guards")
    assert "v2/tools/guards/run_all.py" in text(checks.protected(context(repo)))


def test_protected_fails_when_a_build_changes_a_workflow_it_does_not_own(repo_factory):
    repo = repo_factory(touches=["v2/src/chronos2/stats/**"])
    repo.checkout("claude/b06", create=True)
    repo.write(".github/workflows/v2.yml", "name: v2\non: push\n")
    repo.commit("B06 step 1: rewrite the workflow")
    assert ".github/workflows/v2.yml" in text(checks.protected(context(repo)))


def test_protected_fails_on_the_master_doc_even_when_the_spec_lists_it(repo_factory):
    repo = repo_factory(touches=["docs/v2/CHRONOS_V2.md"])
    repo.checkout("claude/b06", create=True)
    repo.write("docs/v2/CHRONOS_V2.md", "# CHRONOS v2\n\nrewritten by a build\n")
    repo.commit("B06 step 1: edit the master doc")
    found = checks.protected(context(repo))
    assert found, "the master doc is never writable from a build branch"
    assert "CHRONOS_V2.md" in text(found)


def test_protected_fails_on_a_spec_even_when_the_spec_lists_it(repo_factory):
    repo = repo_factory(touches=["docs/v2/build/specs/**"])
    repo.checkout("claude/b06", create=True)
    repo.write("docs/v2/build/specs/B06-throwaway.md", "# rewritten\n")
    repo.commit("B06 step 1: edit my own spec")
    assert checks.protected(context(repo))


def test_protected_fails_on_the_ladder_blueprint_cards_and_gates(repo_factory):
    for path in (
        "docs/v2/build/LADDER.yaml",
        "docs/v2/build/BLUEPRINT.md",
        "docs/v2/build/BUILD_CARDS.md",
        "docs/v2/build/gates/G0-report.md",
    ):
        repo = repo_factory(touches=[path])
        repo.checkout("claude/b06", create=True)
        repo.write(path, "# rewritten by a build\n")
        repo.commit("B06 step 1: edit a founder-owned plan file")
        assert checks.protected(context(repo)), f"{path} must never be writable from a build"


def test_protected_passes_when_the_base_spec_lists_the_path(repo_factory):
    """The must-pass row: B20 creating the touchstones folder, which its own
    spec lists in ``touches``."""
    repo = repo_factory(
        spec_for="b20", touches=["v2/src/chronos2/fixtures/touchstones/**"]
    )
    repo.checkout("claude/b20", create=True)
    repo.write("v2/src/chronos2/fixtures/touchstones/t_a1.py", "def t_a1():\n    return 1\n")
    repo.commit("B20 step 1: the touchstones")
    assert checks.protected(context(repo, head_ref="claude/b20")) == []


def test_protected_prints_the_old_and_new_protected_values(repo_factory):
    """"the guard prints the old and new values, so the founder sees the diff
    he is approving" (CLAUDE.md hard rule 7)."""
    repo = repo_factory(spec_for="b02", touches=["v2/config/protected/**"])
    repo.checkout("claude/b02", create=True)
    repo.write("v2/config/protected/validation.yaml", "stress_friction_multiplier: 2.0\n")
    repo.commit("B02 step 5: the protected values")
    notes = checks.notes(context(repo, head_ref="claude/b02"))
    printed = " ".join(n.message for n in notes)
    assert "stress_friction_multiplier" in printed
    assert "2.0" in printed


def test_protected_refuses_a_founder_owned_path_on_a_lane_branch(repo_factory):
    repo = repo_factory()
    repo.checkout("lane/x", create=True)
    repo.write("v2/src/chronos2/__init__.py", '"""changed from a lane"""\n')
    repo.commit("lane touching source")
    ctx = context(repo, head_ref="lane/x")
    assert checks.protected(ctx) or checks.branch_kind(ctx)


def test_lane_passes_when_it_stays_in_scratch(repo_factory):
    repo = repo_factory()
    repo.checkout("lane/x", create=True)
    repo.write("scratch/note.md", "a note\n")
    repo.commit("lane note")
    ctx = context(repo, head_ref="lane/x")
    assert checks.protected(ctx) == []
    assert checks.branch_kind(ctx) == []
