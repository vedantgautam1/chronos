"""B03 round 2 -- two contracts of ``next_action`` that nothing pinned.

**Finding 2.** Deliver 3 specifies "a pure function ``decide(ladder, facts, now)``
with no I/O", and the module's own docstring says it does none. It read the
system clock at ``next_action.py:174``: ``_waiting_reason`` called ``_for_gate``
with ``datetime.now(UTC)`` instead of threading through the ``now`` it was
given. The review measured that the value cannot change an answer today --
every gate path that reaches ``_waiting_reason`` returns before ``now`` is
consulted -- so the protection is accidental, and one new ``WAIT_FOUNDER``
branch below the ``_fresh`` call would make ``decide`` non-deterministic with
no test able to see it. B04 and B05 are the builds that would add one.

Because the read is inert, no *behavioural* test can go red on it: that is the
finding. So the contract is pinned structurally instead -- the clock is read in
exactly one place, and every helper that could ever need the time is handed it.

**Finding 8.** Rows 27 and 37b state "error exit, non-zero". That holds only
because ``main`` has no handler, so the exception escapes and Python exits 1.
Wrapping ``main`` in a ``try``/``except`` that prints and returns 0 -- a
plausible tidy-up for B04 -- would leave every existing test passing while the
loop walked past two states the spec says it must stop on. The test below is a
regression guard on that: it was green before this round's change and is meant
to stay green.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import ladder as ladder_mod
import next_action
import pytest
from conftest import FIXTURES
from facts import Build, Facts, Gate
from next_action import decide

NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def ladder_a():
    return ladder_mod.load(FIXTURES / "ladder_a.yaml")


# ----------------------------------------- finding 2: decide() reads no clock


def test_the_only_clock_read_in_the_module_is_in_main():
    """``main`` is the I/O boundary and is where a clock read belongs.
    Anywhere else and ``decide`` is not the pure function Deliver 3 names."""
    module_source = inspect.getsource(next_action)
    main_source = inspect.getsource(next_action.main)
    assert module_source.count("datetime.now") == 1
    assert main_source.count("datetime.now") == 1


@pytest.mark.parametrize(
    "name", ["_for_gate", "_for_build", "_waiting_reason", "_for_parked_or_start"]
)
def test_every_helper_that_could_need_the_time_is_handed_it(name):
    """Threading ``now`` through is what makes the purity structural rather
    than accidental: a helper that is given the time cannot reach for the
    wall clock instead."""
    assert "now" in inspect.signature(getattr(next_action, name)).parameters


def test_decide_is_deterministic_for_a_gate_waiting_on_the_founder(ladder_a):
    """A forward guard rather than a red-then-green one: the clock read was
    inert, so this passes before and after the fix. It is here so that a later
    branch which *does* consult the time cannot slip through."""
    facts = Facts(
        builds={i: Build(done=True) for i in ("B01", "B01A", "B02", "B03", "B04", "B05")},
        gates={"G0": Gate(on_main=True, on_base=True), "G1": Gate(writeup_pr="open")},
    )
    answers = {
        decide(ladder_a, facts, NOW.replace(year=year)) for year in (2026, 2036)
    }
    assert len(answers) == 1


# ------------------------------------------ finding 8: main() swallows nothing


def test_main_does_not_swallow_the_errors_the_loop_must_stop_on():
    """Rows 27 and 37b depend on an exception escaping ``main``. A blanket
    handler would be caught here, because it would swallow this one too."""
    with pytest.raises(ladder_mod.LadderError, match="no ladder file"):
        next_action.main(["--ladder", str(FIXTURES / "no-such-ladder.yaml")])
