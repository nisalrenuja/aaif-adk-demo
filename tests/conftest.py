"""Shared fixtures.

The suite lives at the repo root rather than inside a phase folder, because
`tools.py` is byte identical in six phases and testing it six times tests nothing
six times. It imports from `p8_production`, the last phase, which is the copy that
has to be right on stage. `tests/test_phase_sync.py` is what makes that safe: it
asserts the other five copies are identical, so a pass here is a pass for all of
them.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class FakeToolContext:
    """The two attributes the tools actually touch on a real `ToolContext`.

    Constructing a real one needs an InvocationContext, a session service and an
    event stream. The tools use `state` and `actions.escalate`, so that is what
    this provides. The same shape `test_budget_loop.py` uses, for the same reason.
    """

    def __init__(self) -> None:
        self.state: dict = {}
        self.actions = SimpleNamespace(escalate=False, skip_summarization=False)


@pytest.fixture
def ctx() -> FakeToolContext:
    """A fresh, empty tool context."""
    return FakeToolContext()


@pytest.fixture
def kandy(ctx: FakeToolContext) -> FakeToolContext:
    """A context already carrying Kandy preferences and both shortlists.

    Most tool behaviour only exists once research has run, so this is the starting
    point for anything past step one.
    """
    from agents.p8_production.tools import (
        research_activities,
        research_hotels,
        save_preferences,
    )

    save_preferences("Kandy", 3, 250, "culture, food", "none", ctx)
    research_hotels("Kandy", ctx)
    research_activities("Kandy", "culture, food", ctx)
    return ctx
