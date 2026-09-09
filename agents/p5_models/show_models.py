"""Print which model every agent in the pipeline is running on.

Costs nothing and needs no key. Run it on stage instead of reading eight lines of
Python out loud.

    python3 -m agents.p5_models.show_models
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from .agent import (
    activity_researcher,
    budget_checker,
    events_researcher,
    flight_researcher,
    hotel_researcher,
    itinerary_assembler,
    preference_agent,
    presenter,
)
from .providers import creative_model_description

ROLES = [
    ("preference_agent", preference_agent, "parse"),
    ("flight_researcher", flight_researcher, "lookup"),
    ("hotel_researcher", hotel_researcher, "lookup"),
    ("activity_researcher", activity_researcher, "judgement"),
    ("events_researcher", events_researcher, "lookup"),
    ("itinerary_assembler", itinerary_assembler, "assembly"),
    ("budget_checker", budget_checker, "arithmetic"),
    ("presenter", presenter, "write-up"),
]


def main() -> None:
    """Print the model every agent will actually use."""
    print(f"{'agent':22} {'role':14} {'provider':10} model")
    print("-" * 72)
    for name, agent, role in ROLES:
        model = agent.model
        provider = type(model).__name__
        model_id = getattr(model, "model", str(model))
        print(f"{name:22} {role:14} {provider:10} {model_id}")

    print()
    print(f"activity_researcher resolves to: {creative_model_description()}")
    print()
    print("Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env and rerun to see that")
    print("one row move to another provider while every other agent stays on Gemini.")
    print()
    print("events_researcher cannot move: google_search is built into Gemini, so it")
    print("pins that agent to that provider. See the phase README.")


if __name__ == "__main__":
    main()
