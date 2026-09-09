"""Offline check of the loop's exit condition. No API key, no quota, no model.

The budget gate is pure arithmetic, which means it can be tested like any other
function. That is the argument for keeping the maths in tools rather than in a
prompt, and it is worth showing on stage right before the live run.

    python3 -m agents.p3_workflow.test_budget_loop
"""

from __future__ import annotations

from types import SimpleNamespace

from .tools import (
    check_budget,
    choose_hotel,
    research_activities,
    research_hotels,
    save_preferences,
    set_itinerary_day,
)


class FakeContext:
    """The two attributes a ToolContext exposes to these tools."""

    def __init__(self) -> None:
        self.state: dict = {}
        self.actions = SimpleNamespace(escalate=False, skip_summarization=False)


def main() -> None:
    """Run the offline checks and report. Raises AssertionError on failure."""
    ctx = FakeContext()

    save_preferences("Kandy", 3, 250, "culture, food", "none", ctx)
    research_hotels("Kandy", ctx)
    research_activities("Kandy", "culture, food", ctx)

    # Pass one: the expensive hotel and the pricey activities.
    choose_hotel("Temple View Grand", ctx)
    set_itinerary_day(1, ["Temple of the Sacred Tooth Relic", "Ambuluwawa Tower day trip"], ctx)
    set_itinerary_day(2, ["Ceylon tea factory tour, Hantana", "Kandyan dance performance"], ctx)
    set_itinerary_day(3, ["Royal Botanical Gardens, Peradeniya", "Kandy Lake walk"], ctx)

    first = check_budget(ctx)
    print(f"pass 1: {first['verdict']}, total {first['total_cost_usd']} "
          f"vs budget {first['budget_usd']}, escalate={ctx.actions.escalate}")
    assert first["verdict"] == "over_budget"
    assert ctx.actions.escalate is False, "an over budget plan must not end the loop"

    # Pass two: exactly what the feedback told it to do.
    choose_hotel("Kandy Hills Rest", ctx)
    set_itinerary_day(1, ["Temple of the Sacred Tooth Relic", "Kandy Lake walk"], ctx)
    set_itinerary_day(2, ["Udawattakele forest hike", "Bahiravokanda Buddha viewpoint"], ctx)
    set_itinerary_day(3, ["Royal Botanical Gardens, Peradeniya"], ctx)

    second = check_budget(ctx)
    print(f"pass 2: {second['verdict']}, total {second['total_cost_usd']} "
          f"vs budget {second['budget_usd']}, escalate={ctx.actions.escalate}")
    assert second["verdict"] == "under_budget"
    assert ctx.actions.escalate is True, "an in budget plan must end the loop"

    # Replacing a day must not double count it.
    before = len(ctx.state["itinerary"])
    set_itinerary_day(3, ["Royal Botanical Gardens, Peradeniya"], ctx)
    assert len(ctx.state["itinerary"]) == before, "set_itinerary_day must replace"

    print("\nAll checks passed. The loop exits on arithmetic, not on judgement.")


if __name__ == "__main__":
    main()
