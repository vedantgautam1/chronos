"""B02 known answers: the protected values, the workflow file, and the two
properties the whole design rests on -- guard code comes from the base, and the
bootstrap rule.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
VALIDATION = REPO_ROOT / "v2" / "config" / "protected" / "validation.yaml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "v2-guards.yml"
RUN_GUARDS = REPO_ROOT / "v2" / "tools" / "guards" / "run_guards.sh"

# Exactly the spec's deliverable 4, with the decision each value comes from.
EXPECTED = {
    "seal": {"BTC": "2026-04-01T00:00:00Z", "ETH": "2026-04-01T00:00:00Z"},  # V2-D38
    "stress_friction_multiplier": 2.0,  # V2-D35
    "adverse_funding_percentile": 95,  # V2-D39
    "adverse_funding_hourly_rate": {},  # V2-D39, empty until the spike computes it
    "fragmentation_window_days": 90,  # V2-D31
    "sealed_confirm_min_trades": 200,  # V2-D38
}


# --- deliverable 4: the protected values -----------------------------------


@pytest.fixture
def loaded():
    return yaml.safe_load(VALIDATION.read_text())


def test_validation_holds_exactly_the_six_keys(loaded):
    assert sorted(loaded) == sorted(EXPECTED), "exactly the six keys the spec names, no more"


def test_every_value_is_exactly_what_the_spec_states(loaded):
    assert loaded == EXPECTED


def test_the_seal_dates_are_tz_aware_utc_strings_not_bare_dates(loaded):
    """Conventions: tz-aware UTC everywhere, never a bare date."""
    for symbol, value in loaded["seal"].items():
        assert isinstance(value, str), f"{symbol}: a quoted string, not a parsed date"
        assert value.endswith("Z"), f"{symbol}: must carry the UTC marker"
        assert len(value) == len("2026-04-01T00:00:00Z"), f"{symbol}: a full timestamp"


def test_the_friction_multiplier_is_a_float_not_an_int(loaded):
    assert isinstance(loaded["stress_friction_multiplier"], float)


def test_every_value_carries_its_decision_id_in_a_comment():
    """The spec: "containing only numbers the master doc has already locked,
    each with its decision id". A later session must be able to see which
    decision a value came from without leaving the file."""
    text = VALIDATION.read_text()
    for decision in ("V2-D31", "V2-D35", "V2-D38", "V2-D39"):
        assert decision in text, f"{decision} must be named in the file"


def test_the_schema_rejects_an_unknown_key(tmp_path):
    from protected_values import ProtectedValuesError, load

    bad = tmp_path / "validation.yaml"
    bad.write_text(VALIDATION.read_text() + "\nmax_drawdown: 0.5\n")
    with pytest.raises(ProtectedValuesError, match="max_drawdown"):
        load(bad)


def test_the_schema_rejects_a_missing_key(tmp_path):
    from protected_values import ProtectedValuesError, load

    bad = tmp_path / "validation.yaml"
    kept = {k: v for k, v in EXPECTED.items() if k != "fragmentation_window_days"}
    bad.write_text(yaml.safe_dump(kept))
    with pytest.raises(ProtectedValuesError, match="fragmentation_window_days"):
        load(bad)


def test_the_schema_rejects_a_wrongly_typed_value(tmp_path):
    from protected_values import ProtectedValuesError, load

    bad = tmp_path / "validation.yaml"
    bad.write_text(yaml.safe_dump({**EXPECTED, "fragmentation_window_days": "ninety"}))
    with pytest.raises(ProtectedValuesError, match="fragmentation_window_days"):
        load(bad)


def test_the_schema_accepts_the_real_file():
    from protected_values import load

    assert load(VALIDATION) == EXPECTED


# --- deliverable 1: what the workflow file says ----------------------------


@pytest.fixture
def workflow_text():
    return WORKFLOW.read_text()


def test_the_workflow_runs_on_the_ordinary_pull_request_event(workflow_text):
    parsed = yaml.safe_load(workflow_text)
    # ``on`` is parsed as the boolean True by YAML 1.1; accept either spelling.
    triggers = parsed.get("on", parsed.get(True))
    assert "pull_request" in triggers


def test_pull_request_target_appears_nowhere(workflow_text):
    """GitHub takes a ``pull_request_target`` workflow from the default branch
    (since 8 Dec 2025) and blocks the event by default in public repositories
    (from 2 Dec 2026). This repository is public."""
    assert "pull_request_target" not in workflow_text


def test_permissions_are_contents_read_and_nothing_else(workflow_text):
    parsed = yaml.safe_load(workflow_text)
    assert parsed["permissions"] == {"contents": "read"}
    for name, job in parsed["jobs"].items():
        if "permissions" in job:
            assert job["permissions"] == {"contents": "read"}, name


def test_the_workflow_references_no_secrets(workflow_text):
    assert "secrets." not in workflow_text


def test_the_workflow_has_the_two_jobs_the_spec_names(workflow_text):
    parsed = yaml.safe_load(workflow_text)
    assert sorted(parsed["jobs"]) == ["earlier-tests", "guards"]


def test_the_guards_job_checks_out_full_history_and_the_head_commit(workflow_text):
    """On ``pull_request`` the default checkout is the synthetic merge commit
    (``GITHUB_SHA`` is the merge commit on ``refs/pull/N/merge``). The guards
    read commits as data, so they need the real head commit and full history --
    a merge commit GitHub made has no role trailer and is not the branch's work.
    """
    assert "fetch-depth: 0" in workflow_text
    assert "pull_request.head.sha" in workflow_text
    assert "pull_request.base.sha" in workflow_text


def test_the_workflow_delegates_to_the_tested_script(workflow_text):
    """The extraction of the base commit's guard code is the property the whole
    design rests on, so it lives in ``run_guards.sh`` -- one copy, exercised by
    the two tests below -- rather than in shell inside the YAML where no test
    would reach it."""
    assert "run_guards.sh" in workflow_text


# --- the two properties the design rests on --------------------------------


def _run_guards(repo, base_sha=None, head_ref="claude/b06", base_ref="v2-build", extra=()):
    env = {**os.environ, "TZ": "UTC", "PYTHON": sys.executable}
    done = subprocess.run(
        [
            "bash",
            str(RUN_GUARDS),
            "--repo",
            str(repo.path),
            "--base-sha",
            base_sha if base_sha is not None else repo.sha(base_ref),
            "--head-sha",
            repo.sha(),
            "--head-ref",
            head_ref,
            "--base-ref",
            base_ref,
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return done


def test_the_guard_code_comes_from_the_base_commit(repo_factory):
    """The spec's own check: the pull-request branch replaces ``run_all.py``
    with ``exit(0)`` **and** edits a v1 file. The guards still fail, because the
    runner used the base commit's copy."""
    repo = repo_factory()
    repo.install_guards()
    # The factory leaves us on v2-build, so this commit moves the base itself.
    repo.commit("the guards, on the base", role="builder")
    repo.checkout("claude/b06", create=True)
    repo.write("v2/tools/guards/run_all.py", "raise SystemExit(0)\n")
    repo.write("src/chronos/run.py", "# edited v1\ndef trial():\n    return 1\n")
    repo.commit("B06 step 1: neuter the guards and edit v1")

    done = _run_guards(repo)
    assert done.returncode != 0, f"the guards must still fail.\n{done.stdout}\n{done.stderr}"
    assert "src/chronos/run.py" in done.stdout, done.stdout
    assert "bootstrap" not in done.stdout.lower(), "the base has guard code: no bootstrap notice"


def test_the_bootstrap_notice_appears_only_when_the_base_has_no_guard_code(repo_factory):
    """With no guard code at the base the runner uses the head's copy and says
    so in bold at the top of its summary. By construction that happens exactly
    twice: this build's own pull request, and the first gate move."""
    repo = repo_factory()
    repo.checkout("claude/b06", create=True)
    repo.install_guards()
    repo.write("v2/src/chronos2/stats/dsr.py", "def dsr():\n    return 0.0\n")
    repo.commit("B02-like: the guards arrive on the branch itself")

    done = _run_guards(repo)
    first_line = done.stdout.strip().splitlines()[0]
    assert "**" in first_line, f"the notice must be bold and first: {first_line!r}"
    assert "bootstrap" in first_line.lower()
    assert "own copy" in first_line.lower() or "pull request" in first_line.lower()


def test_the_earlier_tests_job_runs_through_the_same_script(repo_factory):
    """Both jobs go through run_guards.sh, so there is one extraction path and
    one entry point rather than two. This drives the second job end to end: an
    earlier failing test, in the base's copy of the tests folder, run against
    the branch's package."""
    repo = repo_factory()
    repo.install_guards()
    repo.write("v2/tests/earlier/test_edge.py", "def test_edge():\n    assert 1 == 2\n")
    repo.commit("the guards and an earlier failing test, on the base", role="builder")
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "def dsr():\n    return 0.0\n")
    repo.commit("B06 step 1")

    done = _run_guards(repo, extra=["--earlier-tests"])
    assert done.returncode != 0, done.stdout
    assert "earlier-tests" in done.stdout
    assert "test_edge" in done.stdout, done.stdout


def test_the_runner_exits_zero_on_a_clean_build_branch(repo_factory):
    """A check that has never been seen green proves as little as one that has
    never been seen red."""
    repo = repo_factory(touches=["v2/src/chronos2/stats/**"])
    repo.install_guards()
    # The factory leaves us on v2-build, so this commit moves the base itself.
    repo.commit("the guards, on the base", role="builder")
    repo.checkout("claude/b06", create=True)
    repo.write("v2/src/chronos2/stats/dsr.py", "def dsr():\n    return 0.0\n")
    repo.commit("B06 step 1: an ordinary, clean build commit")

    done = _run_guards(repo)
    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
