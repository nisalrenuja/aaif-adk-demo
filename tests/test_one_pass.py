"""The assembler's single pass, checked as an invariant rather than read as prose.

`one_pass.py` exists to turn an instruction, "make exactly one pass and then stop",
into something the model cannot ignore. That claim is only worth making if it is
tested, so these are the properties it has to hold:

1. A repeat call in the same pass does not reach the tool.
2. The next pass starts clean, or the refinement loop could never cut anything.
3. A refusal leaves the plan exactly as the first call left it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.p8_production.one_pass import LEDGER_KEY, enforce_one_pass, start_new_pass
from agents.p8_production.tools import choose_hotel, set_itinerary_day


def tool(name: str) -> SimpleNamespace:
    """The one attribute the callback reads off a real `BaseTool`."""
    return SimpleNamespace(name=name)


def call(name: str, args: dict, ctx) -> dict | None:
    """Run the guard the way ADK does: by keyword."""
    return enforce_one_pass(tool=tool(name), args=args, tool_context=ctx)


# --- within one pass -------------------------------------------------------


def test_first_call_is_allowed(ctx):
    assert call("choose_hotel", {"name": "Kandy Hills Rest"}, ctx) is None


def test_second_choose_hotel_in_the_same_pass_is_refused(ctx):
    call("choose_hotel", {"name": "Kandy Hills Rest"}, ctx)
    refusal = call("choose_hotel", {"name": "Lakeside Boutique"}, ctx)
    assert refusal is not None
    assert refusal["status"] == "skipped"


def test_the_refusal_tells_the_model_what_to_do_next(ctx):
    """A bare error invites a retry. The result has to end the attempt."""
    call("choose_hotel", {"name": "Kandy Hills Rest"}, ctx)
    refusal = call("choose_hotel", {"name": "Lakeside Boutique"}, ctx)
    assert "budget check" in refusal["next_step"]
    assert "choose_hotel" in refusal["recorded_this_pass"]


def test_the_same_day_twice_is_refused(ctx):
    call("set_itinerary_day", {"day": 1, "activity_names": ["a"]}, ctx)
    assert call("set_itinerary_day", {"day": 1, "activity_names": ["b"]}, ctx) is not None


def test_different_days_are_all_allowed(ctx):
    """One call per day is the correct shape, not a repeat."""
    for day in (1, 2, 3):
        assert call("set_itinerary_day", {"day": day, "activity_names": []}, ctx) is None


def test_tools_that_are_not_rationed_pass_through(ctx):
    """Only the two assembly tools are limited. Nothing else is touched."""
    for name in ("check_budget", "research_hotels", "book_trip"):
        assert call(name, {}, ctx) is None
        assert call(name, {}, ctx) is None


# --- across passes ---------------------------------------------------------


def test_a_new_pass_clears_the_ledger(ctx):
    """The whole refinement mechanism depends on this.

    If the ledger survived into the next loop iteration, the second pass could not
    pick a cheaper hotel and the budget loop would run three times changing
    nothing, which is worse than the behaviour this guard replaced.
    """
    call("choose_hotel", {"name": "Temple View Grand"}, ctx)
    assert call("choose_hotel", {"name": "Kandy Hills Rest"}, ctx) is not None

    start_new_pass(callback_context=ctx)

    assert call("choose_hotel", {"name": "Kandy Hills Rest"}, ctx) is None


def test_start_new_pass_returns_nothing(ctx):
    """Returning content from a before_agent_callback would skip the agent."""
    assert start_new_pass(callback_context=ctx) is None


# --- what it protects ------------------------------------------------------


def test_a_refused_call_cannot_change_the_plan(kandy):
    """The point of the guard, stated as the property it defends.

    The first hotel is the one the budget check totals. A second call, whatever it
    asks for, cannot move the number.
    """
    assert call("choose_hotel", {"name": "Kandy Hills Rest"}, kandy) is None
    choose_hotel("Kandy Hills Rest", kandy)

    refusal = call("choose_hotel", {"name": "Temple View Grand"}, kandy)
    assert refusal is not None
    # The tool body never runs, so state still holds the first choice.
    assert kandy.state["chosen_hotel"]["name"] == "Kandy Hills Rest"


def test_a_refused_day_leaves_the_itinerary_alone(kandy):
    assert call("set_itinerary_day", {"day": 1}, kandy) is None
    set_itinerary_day(1, ["Kandy Lake walk"], kandy)

    assert call("set_itinerary_day", {"day": 1}, kandy) is not None
    assert [i["activity"] for i in kandy.state["itinerary"]] == ["Kandy Lake walk"]


# --- where the bookkeeping lives -------------------------------------------


def test_the_ledger_is_invocation_scoped(ctx):
    """`temp:` keys are applied in memory and trimmed before anything is stored.

    Without the prefix this counter would be written into the SQLite session file
    from Phase 2 onward, and would show up in `show_state.py` next to the trip.
    """
    assert LEDGER_KEY.startswith("temp:")
    call("choose_hotel", {}, ctx)
    assert all(k.startswith("temp:") for k in ctx.state)


@pytest.mark.parametrize("missing", [{}, {"day": None}])
def test_a_malformed_day_argument_does_not_crash_the_guard(ctx, missing):
    """A callback that raises takes the whole run down. It must be boring."""
    assert call("set_itinerary_day", missing, ctx) is None
    assert call("set_itinerary_day", missing, ctx) is not None
