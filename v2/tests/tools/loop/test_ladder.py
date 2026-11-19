"""B03 step 2 -- what ``ladder.py`` must reject, and the two live-file checks.

The spec names five rejections. The last two tests are the ONLY two in this
build that read the live ``LADDER.yaml`` and ``BLUEPRINT.md``; everything else
runs on the frozen fixtures, so a routine ladder change cannot turn the
decision table red (red-team second pass, finding 11). These two are meant to
go red when the live files drift apart -- that is red-team first-pass finding
25, which asked for exactly this test.
"""

from __future__ import annotations

import textwrap

import pytest
from conftest import FIXTURES, REPO_ROOT

import ladder as ladder_mod
from ladder import LadderError

BUILD_DOCS = REPO_ROOT / "docs" / "v2" / "build"
LIVE_LADDER = BUILD_DOCS / "LADDER.yaml"
BLUEPRINT = BUILD_DOCS / "BLUEPRINT.md"

HEADER = """
version: 0.2
build_branch: v2-build
branch_prefix: claude/
claim_hours: 3
max_review_rounds: 2
halt_label: chronos-halt

ladder:
"""


def write(tmp_path, rows: str):
    path = tmp_path / "ladder.yaml"
    path.write_text(HEADER + textwrap.dedent(rows))
    return path


OK_ROW = "  - {id: B06, title: t, phase: 1, size: M, model: opus, who: loop, ticks: 3, spec: card}"


def test_a_minimal_ladder_loads(tmp_path):
    ladder = ladder_mod.load(write(tmp_path, OK_ROW))
    assert ladder.ids == ("B06",)
    assert ladder.claim_hours == 3
    assert ladder.branch_for("B06") == "claude/b06"


def test_rejects_a_duplicate_id(tmp_path):
    path = write(tmp_path, f"{OK_ROW}\n{OK_ROW}")
    with pytest.raises(LadderError, match="duplicate id B06"):
        ladder_mod.load(path)


def test_rejects_a_needs_that_points_later_in_the_file(tmp_path):
    rows = """
      - {id: B06, title: t, phase: 1, size: M, model: opus, who: loop, ticks: 3, needs: [B07], spec: card}
      - {id: B07, title: t, phase: 1, size: M, model: opus, who: loop, ticks: 3, spec: card}
    """
    with pytest.raises(LadderError, match="does not appear earlier"):
        ladder_mod.load(write(tmp_path, rows))


def test_rejects_size_l(tmp_path):
    row = "  - {id: B06, title: t, phase: 1, size: L, model: opus, who: loop, ticks: 3, spec: card}"
    with pytest.raises(LadderError, match="allowed sizes are"):
        ladder_mod.load(write(tmp_path, row))


def test_rejects_model_fable(tmp_path):
    row = "  - {id: B06, title: t, phase: 1, size: M, model: fable, who: loop, ticks: 3, spec: card}"
    with pytest.raises(LadderError, match="has model 'fable'"):
        ladder_mod.load(write(tmp_path, row))


def test_rejects_a_build_with_neither_a_spec_file_nor_card(tmp_path):
    row = "  - {id: B06, title: t, phase: 1, size: M, model: opus, who: loop, ticks: 3}"
    with pytest.raises(LadderError, match="neither a spec file nor 'card'"):
        ladder_mod.load(write(tmp_path, row))


def test_rejects_who_outside_the_allowed_set(tmp_path):
    row = "  - {id: B06, title: t, phase: 1, size: M, model: opus, who: anyone, ticks: 3, spec: card}"
    with pytest.raises(LadderError, match="has who 'anyone'"):
        ladder_mod.load(write(tmp_path, row))


def test_rejects_ticks_that_do_not_match_the_size(tmp_path):
    row = "  - {id: B06, title: t, phase: 1, size: S, model: opus, who: loop, ticks: 3, spec: card}"
    with pytest.raises(LadderError, match="size S and so must allow 2 ticks"):
        ladder_mod.load(write(tmp_path, row))


def test_rejects_a_gate_that_carries_a_spec(tmp_path):
    row = "  - {id: G9, gate: true, title: t, phase: 1, spec: specs/G9.md}"
    with pytest.raises(LadderError, match="is a gate and must have no spec"):
        ladder_mod.load(write(tmp_path, row))


def test_rejects_a_spec_path_that_does_not_exist(tmp_path):
    """The spec-path-exists rule, which the frozen fixtures are loaded without."""
    row = (
        "  - {id: B06, title: t, phase: 1, size: M, model: opus, who: loop, "
        "ticks: 3, spec: specs/nope.md}"
    )
    with pytest.raises(LadderError, match="does not exist under"):
        ladder_mod.load(write(tmp_path, row), spec_root=tmp_path)


def test_both_frozen_fixtures_validate():
    for name in ("ladder_a.yaml", "ladder_b.yaml"):
        ladder = ladder_mod.load(FIXTURES / name)
        assert ladder.ids[0] == "G0"
        assert "B54" in ladder.ids


# --------------------------------------------------------- the two live files


def test_the_live_ladder_validates():
    ladder = ladder_mod.load(LIVE_LADDER, spec_root=BUILD_DOCS)
    assert ladder.build_branch == "v2-build"
    assert ladder.branch_prefix == "claude/"
    assert ladder.ids[0] == "G0"


BLUEPRINT_WHO = {"loop": "loop", "founder": "you+"}


def _blueprint_part5_rows() -> list[tuple[str, str | None, str]]:
    """(id, size, who) for every table row in BLUEPRINT.md Part 5, in order.

    The blueprint writes ``loop`` for ``who: loop`` and ``you+`` for
    ``who: founder``, each sometimes followed by a note in brackets, which is
    ignored. Gates are written with an em dash for size and ``gate`` for who.
    """
    text = BLUEPRINT.read_text()
    part5 = text.split("## Part 5")[1].split("## Part 6")[0]
    rows: list[tuple[str, str | None, str]] = []
    for line in part5.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 5:
            continue
        name = cells[0].replace("*", "").strip()
        if name in ("Build", "") or set(cells[0]) <= set("-: "):
            continue
        size = cells[2].strip()
        who = cells[4].split("(")[0].strip()
        rows.append((name, None if size in ("—", "-") else size, who))
    return rows


def test_the_blueprint_and_the_ladder_agree_on_id_size_and_who_in_order():
    ladder = ladder_mod.load(LIVE_LADDER, spec_root=BUILD_DOCS)
    expected = [
        (e.id, None if e.gate else e.size, "gate" if e.gate else BLUEPRINT_WHO[e.who])
        for e in ladder
    ]
    assert _blueprint_part5_rows() == expected


def test_the_blueprint_parser_actually_found_the_tables():
    """A parser that silently found nothing would make the test above vacuous."""
    rows = _blueprint_part5_rows()
    assert len(rows) > 50
    assert rows[0] == ("G0", None, "gate")
