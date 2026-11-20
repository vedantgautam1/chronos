"""B04 — the agent definitions, the four commands, and the templates.

What this file pins, and why it is one file: B04's ``touches`` lists exactly
one test path, so every check below lives here even though it spans three
kinds of thing (markdown front matter, markdown prose, and the small helper
the four skills share).

Three deliberate choices a reviewer should see stated rather than discover:

1. **The ``CLAUDE.md`` check compares against a pinned digest, not against
   ``origin/v2-build``.** The spec's known answer says "compared against the
   base branch". A test that shells out to ``git show origin/v2-build:…``
   passes here and fails in CI: ``.github/workflows/v2.yml`` uses
   ``actions/checkout@v4`` with no ``fetch-depth``, so the tests job gets one
   commit and no ``v2-build`` ref. That is exactly B03's git-identity defect
   (green locally, red on the runner), so the base-branch bytes are pinned
   here as a digest instead — B03's own precedent of frozen copies rather
   than live files — and the live comparison against the base branch is run
   by hand and recorded in ``reports/B04.md``.

2. **``MODELS`` is imported from ``ladder``, not restated.** The allowed set
   is the ladder's to define; a copy here could drift from it.

3. **The helper is exercised through injected fakes, never the network.**
   ``loop_cli`` takes its ``next_action`` runner and its GitHub backend as
   arguments, the way ``facts.py`` puts ``git`` and ``gh api`` behind one
   replaceable function each.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path

import pytest
import yaml
from ladder import MODELS

REPO_ROOT = Path(__file__).resolve().parents[4]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
TEMPLATES_DIR = REPO_ROOT / "docs" / "v2" / "build" / "templates"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

BUILDER_AGENTS = ("chronos-builder-opus", "chronos-builder-sonnet")
ROLE_AGENTS = ("chronos-reviewer", "chronos-auditor")
AGENTS = BUILDER_AGENTS + ROLE_AGENTS

TICK = "chronos-tick"
SKILLS = (TICK, "chronos-status", "chronos-halt", "chronos-resume")

BUILDER_TRAILER = "Chronos-Role: builder"
REVIEWER_TRAILER = "Chronos-Role: reviewer"

# Built-in Claude Code commands, so a skill may not take these names. The
# official skills reference: `name` sets the command you type "unless another
# command already uses that name", and `/status` is listed as a built-in that
# "works while Claude is responding". B04's spec asked for `/status` and
# `/resume`; both are taken, which is why all four carry the `chronos-`
# prefix. Pinned as a test so a later tidy-up cannot quietly reintroduce it.
BUILTIN_COMMANDS = frozenset(
    {
        "status",
        "resume",
        "continue",
        "help",
        "clear",
        "compact",
        "context",
        "cost",
        "model",
        "agents",
        "skills",
        "tasks",
        "todos",
        "usage",
        "stats",
        "doctor",
        "init",
        "review",
        "config",
        "exit",
        "vim",
        "bug",
        "login",
        "logout",
        "memory",
        "effort",
        "theme",
        "sandbox",
        "statusline",
        "release-notes",
        "add-dir",
        "reset",
        "new",
    }
)

# The four bullets of CLAUDE.md's "Build loop" section as they stand on the
# base branch, v2-build at 51fc0abf8927db545d22229f2936b50d77ba30c1.
#
# The spec (Deliver 5, and the known answer) says "three". There are four: the
# fourth arrived in blueprint v0.3 and the spec was written in v0.4 without
# updating the count, so the count was already stale when it was written.
# Preserving all four is the conservative reading. Recorded as a spec defect
# in reports/B04.md, "For the gate".
BASE_BULLET_COUNT = 4
BASE_BULLETS_SHA256 = "a95ff6461b7b155d7bdf616f975c750616496e4772ce84d20eaf2458a32309fe"
BASE_BULLET_ANCHORS = (
    "In a build or review session, the end-of-session list below is replaced",
    "Unattended sessions never merge into `main`",
    "Builder and reviewer are different sessions.",
    (
        "Never create a `CLAUDE.md`, `AGENTS.md` or `.claude` folder below "
        "the repository root."
    ),
)


# ------------------------------------------------------------------ helpers


def _split_front_matter(path: Path) -> tuple[dict, str]:
    """Front matter and body. Claude Code reads the front matter only when the
    opening `---` is the file's first line, so that is what is required here.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} does not open with a '---' front-matter line")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise AssertionError(f"{path} has no closing '---' front-matter line")
    meta = yaml.safe_load(text[4:end]) or {}
    assert isinstance(meta, dict), f"{path} front matter is not a mapping"
    return meta, text[end + 5 :]


def _agent(name: str) -> tuple[dict, str]:
    return _split_front_matter(AGENTS_DIR / f"{name}.md")


def _skill(name: str) -> tuple[dict, str]:
    return _split_front_matter(SKILLS_DIR / name / "SKILL.md")


def _build_loop_bullets(text: str) -> list[str]:
    section = re.search(
        r"^## Build loop.*?$(.*?)^## At the end", text, re.DOTALL | re.MULTILINE
    )
    if section is None:
        raise AssertionError("CLAUDE.md has no 'Build loop' section")
    return [
        line for line in section.group(1).splitlines() if line.startswith("- ")
    ]


def _load_cli():
    path = SKILLS_DIR / TICK / "loop_cli.py"
    spec = importlib.util.spec_from_file_location("loop_cli", path)
    if spec is None or spec.loader is None:  # pragma: no cover - import guard
        raise AssertionError(f"{path} is not importable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRefs:
    """A lock backend that answers from memory and records every call.

    Mirrors the duck type `Lock` expects (`commit`, `create`, `update`,
    `read`, `delete`) so the helper drives the real `Lock`, not a stand-in
    for it.
    """

    def __init__(self, existing: dict[str, str] | None = None) -> None:
        self.refs: dict[str, str] = dict(existing or {})
        self.messages: dict[str, str] = {}
        self.calls: list[str] = []
        self._n = 0

    def commit(self, message: str, parent: str | None) -> str:
        self._n += 1
        sha = f"{self._n:040x}"
        self.messages[sha] = message
        self.calls.append("commit")
        return sha

    def create(self, ref: str, sha: str) -> bool:
        self.calls.append(f"create {ref}")
        if ref in self.refs:
            return False
        self.refs[ref] = sha
        return True

    def update(self, ref: str, sha: str, expect: str | None = None) -> bool:
        self.calls.append(f"update {ref}")
        self.refs[ref] = sha
        return True

    def read(self, ref: str) -> str | None:
        self.calls.append(f"read {ref}")
        return self.refs.get(ref)

    def message(self, sha: str) -> str:
        return self.messages.get(sha, "")

    def delete(self, ref: str) -> None:
        self.calls.append(f"delete {ref}")
        self.refs.pop(ref, None)


class FakeIssues:
    """The halt-issue side of GitHub: what is open, and what was asked of it."""

    def __init__(self, open_halt: int | None = None) -> None:
        self.open_halt = open_halt
        self.opened: list[str] = []
        self.closed: list[int] = []

    def halt_issue(self) -> int | None:
        return self.open_halt

    def open_halt_issue(self, body: str) -> int:
        self.opened.append(body)
        return 999

    def close_issue(self, number: int) -> None:  # must never be called
        self.closed.append(number)


def _ok(payload: str):
    return lambda argv: (0, payload, "")


def _fails(stderr: str):
    return lambda argv: (1, "", stderr)


ACTION_BUILD_OPUS = (
    '{"kind": "START_BUILD", "id": "T01", "model": "opus", '
    '"branch": "claude/t01", "reason": "T01 is next.", "waiting_on_founder": []}'
)


# ------------------------------------------------------------- agent files


def test_every_required_agent_file_exists():
    missing = [n for n in AGENTS if not (AGENTS_DIR / f"{n}.md").is_file()]
    assert not missing, f"missing agent definitions: {missing}"


@pytest.mark.parametrize("name", AGENTS)
def test_every_agent_carries_the_required_front_matter(name):
    meta, body = _agent(name)
    # `name` and `description` are the two the official subagents reference
    # marks required; everything else is optional.
    assert meta.get("name") == name, f"{name}: front-matter name must match"
    assert isinstance(meta.get("description"), str)
    assert meta["description"].strip(), f"{name}: description must say when to use it"
    assert body.strip(), f"{name}: the body is the system prompt and must not be empty"


@pytest.mark.parametrize("name", AGENTS)
def test_every_agent_pins_an_allowed_model(name):
    meta, _ = _agent(name)
    model = meta.get("model")
    assert model in MODELS, (
        f"{name}: model is {model!r}; the ladder allows {MODELS}. "
        "Never 'fable', and never 'inherit' or omitted — omitting it hands the "
        "choice to CLAUDE_CODE_SUBAGENT_MODEL or the calling session."
    )


@pytest.mark.parametrize("name", ROLE_AGENTS)
def test_the_reviewer_and_auditor_run_on_opus(name):
    meta, _ = _agent(name)
    assert meta["model"] == "opus", (
        f"{name}: BLUEPRINT 2.2 and 2.8 — reviews and gate audits are always Opus"
    )


def test_the_two_builder_agents_share_one_body_and_differ_in_model():
    """Deliver 1: "same body, different ``model``".

    The first version of this test also required every front-matter key but
    ``name`` and ``model`` to match, which would have forced one shared
    ``description`` on both agents — and the description is what the loop
    routes on, so the two would have been indistinguishable. The spec says
    *body*, not front matter. Corrected before either agent file existed;
    disclosed in ``reports/B04.md``.
    """
    opus_meta, opus_body = _agent("chronos-builder-opus")
    sonnet_meta, sonnet_body = _agent("chronos-builder-sonnet")
    assert opus_body == sonnet_body, "Deliver 1: same body, different model"
    assert opus_meta["model"] == "opus"
    assert sonnet_meta["model"] == "sonnet"
    # The descriptions must differ, and each must name the model it pins, or
    # the loop cannot tell which builder an action wants.
    assert opus_meta["description"] != sonnet_meta["description"]
    assert "opus" in opus_meta["description"].lower()
    assert "sonnet" in sonnet_meta["description"].lower()
    # Nothing else may drift between them.
    ignored = ("name", "model", "description")
    assert {k: v for k, v in opus_meta.items() if k not in ignored} == {
        k: v for k, v in sonnet_meta.items() if k not in ignored
    }


@pytest.mark.parametrize("name", BUILDER_AGENTS)
def test_builder_bodies_carry_the_builder_trailer_and_not_the_reviewers(name):
    _, body = _agent(name)
    assert BUILDER_TRAILER in body
    assert REVIEWER_TRAILER not in body


def test_the_reviewer_body_carries_the_reviewer_trailer_and_not_the_builders():
    _, body = _agent("chronos-reviewer")
    assert REVIEWER_TRAILER in body
    assert BUILDER_TRAILER not in body


@pytest.mark.parametrize("name", AGENTS)
def test_every_agent_body_forbids_instruction_files_below_the_root(name):
    _, body = _agent(name)
    assert "AGENTS.md" in body and ".claude" in body, (
        f"{name}: red-team second pass finding 4 — every agent body repeats "
        "'never create a CLAUDE.md, AGENTS.md or .claude folder'"
    )
    assert "Never create" in body or "never create" in body


@pytest.mark.parametrize("name", AGENTS)
def test_every_agent_body_requires_still_mine_before_every_push(name):
    _, body = _agent(name)
    assert "still_mine" in body, f"{name}: check the lock before every push"


@pytest.mark.parametrize("name", AGENTS)
def test_every_agent_body_reads_the_spec_from_the_base_branch(name):
    _, body = _agent(name)
    assert "v2-build" in body, f"{name}: 'read the spec from v2-build'"


def test_the_reviewer_body_states_the_push_before_approval_rule():
    _, body = _agent("chronos-reviewer")
    low = body.lower()
    assert "before" in low and "approv" in low
    assert "merged" in low, (
        "reviewer rule 6 / red-team third pass finding a: push the final "
        "`merged` commit BEFORE the founder is asked, and never after"
    )


# ------------------------------------------------------------- skill files


def test_every_required_skill_file_exists():
    missing = [n for n in SKILLS if not (SKILLS_DIR / n / "SKILL.md").is_file()]
    assert not missing, f"missing skills: {missing}"


@pytest.mark.parametrize("name", SKILLS)
def test_every_skill_carries_the_required_front_matter(name):
    meta, body = _skill(name)
    assert meta.get("name") == name
    assert isinstance(meta.get("description"), str)
    assert meta["description"].strip()
    assert body.strip()


@pytest.mark.parametrize("name", SKILLS)
def test_no_skill_takes_a_built_in_command_name(name):
    meta, _ = _skill(name)
    for candidate in (name, str(meta.get("name", ""))):
        assert candidate.lower() not in BUILTIN_COMMANDS, (
            f"{candidate!r} is a built-in Claude Code command, so the skill "
            "would not be the command the founder gets"
        )
    assert name.startswith("chronos-")


@pytest.mark.parametrize("name", SKILLS)
def test_every_skill_is_manually_invoked_only(name):
    meta, _ = _skill(name)
    assert meta.get("disable-model-invocation") is True, (
        f"{name}: a command that takes a lock, dispatches a build or opens an "
        "emergency stop must never fire because a sentence resembled its "
        "description"
    )


def test_the_resume_skill_never_closes_a_halt_issue():
    _, body = _skill("chronos-resume")
    assert "close the issue yourself on GitHub" in body
    assert "only your account releases the stop" in body


def test_the_tick_skill_dispatches_through_the_task_tool():
    _, body = _skill(TICK)
    assert "subagent_type" in body, (
        "a subagent is invoked through the Task/Agent tool, not by running "
        "`claude <agent-name>` in a shell"
    )
    assert "claude chronos-builder" not in body


def test_the_tick_skill_runs_the_loop_without_python_isolated_mode():
    """`-I` strips the script's own directory from ``sys.path``, so
    ``next_action.py``'s sibling ``import ladder`` fails at once —
    reproduced: ``ModuleNotFoundError: No module named 'ladder'``.

    The first version of this test asserted ``"python -I" not in body``,
    which is wrong: the skill has to *name* ``-I`` in order to warn against
    it, because ``CLAUDE.md``'s conventions tell sessions to use it. Every
    mention must be a prohibition, which is what this asserts instead —
    stricter than the absence check it replaces. Disclosed in
    ``reports/B04.md``.
    """
    _, body = _skill(TICK)
    assert "uv run python tools/loop/next_action.py" in body
    assert "Never run it with `python -I`" in body
    mentions = [ln for ln in body.splitlines() if "python -I" in ln]
    assert mentions, "the trap must be named, or a later session re-adds it"
    for line in mentions:
        assert "never" in line.lower(), f"-I named without a prohibition: {line}"


def test_the_tick_skill_fetches_before_it_gathers():
    _, body = _skill(TICK)
    assert "fetch --no-tags --prune origin" in body, (
        "B03 finding 3, declined there and handed to B04 as the loop's clone "
        "discipline: on a stale clone four facts read empty and a "
        "twice-failed build is resumed where row 17 says halt"
    )


@pytest.mark.parametrize("name", SKILLS)
def test_no_skill_merges_into_main(name):
    _, body = _skill(name)
    assert "never merge" in body.lower() or "main" not in body.lower()


# -------------------------------------------------------------- templates


@pytest.mark.parametrize(
    ("filename", "needle"),
    [
        ("report.md", "For the gate"),
        ("review.md", "code commit reviewed"),
        ("gate-report.md", "three things you can check yourself"),
    ],
)
def test_every_template_exists_and_carries_its_named_section(filename, needle):
    """Deliver 4 names a section each template must carry.

    Matched case-insensitively: the spec writes these as descriptive
    references in lower case ("with 'code commit reviewed'"), while a
    section heading capitalises naturally. The section's presence is what
    the spec asks for, not its letter case.
    """
    path = TEMPLATES_DIR / filename
    assert path.is_file(), f"missing template: {path}"
    assert needle.lower() in path.read_text(encoding="utf-8").lower()


# ---------------------------------------------------------------- CLAUDE.md


def test_claude_md_build_loop_keeps_the_base_branch_bullets_byte_for_byte():
    bullets = _build_loop_bullets(CLAUDE_MD.read_text(encoding="utf-8"))
    kept = bullets[:BASE_BULLET_COUNT]
    for anchor in BASE_BULLET_ANCHORS:
        assert any(anchor in b for b in kept), f"bullet missing or reworded: {anchor}"
    digest = hashlib.sha256(
        ("\n".join(kept) + "\n").encode("utf-8")
    ).hexdigest()
    assert digest == BASE_BULLETS_SHA256, (
        "the Build loop section's original bullets changed; the spec says they "
        "stay word for word"
    )


def test_claude_md_names_the_four_commands_and_where_the_agents_live():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    for command in SKILLS:
        assert f"/{command}" in text, f"CLAUDE.md does not name /{command}"
    assert ".claude/agents/" in text


# ------------------------------------------------------- the shared helper


def test_tick_passes_the_ladder_argument_through():
    cli = _load_cli()
    seen: list[list[str]] = []

    def runner(argv):
        seen.append(argv)
        return 0, ACTION_BUILD_OPUS, ""

    cli.claim(
        ["--ladder", "X", "--session-model", "opus"],
        next_action=runner,
        refs=FakeRefs(),
        issues=FakeIssues(),
    )
    assert seen, "next_action was never run"
    assert "--ladder" in seen[0] and "X" in seen[0]


def test_tick_on_the_wrong_model_prints_the_mismatch_and_takes_no_lock():
    cli = _load_cli()
    refs, issues = FakeRefs(), FakeIssues()
    code, out = cli.claim(
        ["--session-model", "sonnet"],
        next_action=_ok(ACTION_BUILD_OPUS),
        refs=refs,
        issues=issues,
    )
    assert code != 0
    assert "wants opus" in out.lower() and "sonnet" in out.lower()
    assert not any(c.startswith("create") for c in refs.calls), (
        "a model mismatch must stop before the lock, so no commit is made"
    )
    assert issues.opened == []


def test_tick_with_a_lock_held_by_someone_else_says_claimed_nothing_to_do():
    cli = _load_cli()
    refs = FakeRefs(existing={"refs/heads/lock/t01": "deadbeef"})
    code, out = cli.claim(
        ["--session-model", "opus"],
        next_action=_ok(ACTION_BUILD_OPUS),
        refs=refs,
        issues=FakeIssues(),
    )
    assert code == 0
    assert "claimed, nothing to do" in out
    assert "subagent_type" not in out, "nothing is dispatched when the lock is lost"


def test_tick_opens_exactly_one_halt_issue_when_next_action_fails():
    cli = _load_cli()
    refs, issues = FakeRefs(), FakeIssues()
    code, out = cli.claim(
        ["--session-model", "opus"],
        next_action=_fails("FactsError: ladder not found"),
        refs=refs,
        issues=issues,
    )
    assert code != 0
    assert len(issues.opened) == 1, f"expected exactly one halt issue, got {issues.opened}"
    assert "FactsError: ladder not found" in issues.opened[0], (
        "the stop issue carries the error text (B03 row 37b)"
    )
    assert not any(c.startswith("create") for c in refs.calls)
    assert "halt" in out.lower()


def test_tick_dispatches_the_named_agent_when_the_model_matches():
    cli = _load_cli()
    refs = FakeRefs()
    code, out = cli.claim(
        ["--session-model", "opus"],
        next_action=_ok(ACTION_BUILD_OPUS),
        refs=refs,
        issues=FakeIssues(),
    )
    assert code == 0
    assert "chronos-builder-opus" in out
    assert "subagent_type" in out
    assert "create refs/heads/lock/t01" in refs.calls


def test_resume_leaves_an_open_halt_issue_open():
    cli = _load_cli()
    issues = FakeIssues(open_halt=7)
    code, out = cli.resume([], issues=issues)
    assert code != 0
    assert issues.closed == [], (
        "red-team second pass finding 13 / B03 row 30: /chronos-resume never "
        "closes a chronos-halt issue"
    )
    assert issues.open_halt == 7
    assert "close the issue yourself on GitHub" in out
    assert "only your account releases the stop" in out


def test_a_labelled_pull_request_is_not_read_as_an_emergency_stop():
    """`GET /issues` returns pull requests as well as issues.

    B03's round-2 reviewer measured this on the live repository: all 32 of
    what that endpoint returns here are pull requests and none is an issue.
    So a pull request that picked up the label — and the loop opens pull
    requests constantly — would read as an emergency stop and freeze
    everything. The collector filters on the `pull_request` key; this pins
    it, because nothing else did.
    """
    cli = _load_cli()
    labelled_pr = '[{"number": 34, "pull_request": {"url": "..."}}]'
    issues = cli.GitHubIssues(
        "owner/repo", "owner", runner=lambda *a, **k: (0, labelled_pr)
    )
    assert issues.halt_issue() is None

    real_issue = '[{"number": 7}]'
    issues = cli.GitHubIssues(
        "owner/repo", "owner", runner=lambda *a, **k: (0, real_issue)
    )
    assert issues.halt_issue() == 7


def test_an_unreadable_halt_answer_reports_a_stop_rather_than_none():
    """Fails closed. "No stop" is the one answer that must never be guessed."""
    cli = _load_cli()
    for runner in (
        lambda *a, **k: (1, ""),  # the call failed
        lambda *a, **k: (0, "not json"),  # the answer is unreadable
    ):
        issues = cli.GitHubIssues("owner/repo", "owner", runner=runner)
        assert issues.halt_issue() == -1
        code, out = cli.resume([], issues=issues)
        assert code != 0, "an unreadable stop must not resume the loop"
        assert "nothing is resumed" in out.lower()


def test_resume_reports_no_stop_when_none_is_open():
    cli = _load_cli()
    issues = FakeIssues(open_halt=None)
    code, out = cli.resume([], issues=issues)
    assert code == 0
    assert issues.closed == []
    assert "no emergency stop" in out.lower()
