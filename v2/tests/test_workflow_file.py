"""The v2 CI workflow must run with read-only permissions and no secrets."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "v2.yml"


def test_workflow_exists():
    assert WORKFLOW.is_file()


def test_workflow_permissions_are_read_only():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert data.get("permissions") == {"contents": "read"}


def test_workflow_has_no_secrets_reference():
    assert "secrets." not in WORKFLOW.read_text(encoding="utf-8")
