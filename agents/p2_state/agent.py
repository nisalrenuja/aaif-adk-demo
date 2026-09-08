"""Phase 2: state.

Phase 1 agents could only talk to the transcript. Now they write to a shared
scratchpad that outlives the turn.

Two teaching points:

1. `tool_context.state` is a plain dict shared by every agent in the session. A
   specialist writes into it, another specialist reads it back. No message passing.
2. Instructions are templates. `{preferences?}` in an instruction string is
   substituted from state before the call goes out, so an agent can be told what it
   already knows without anyone re-typing it. The trailing `?` means optional, which
   is what keeps the first turn from blowing up with a KeyError.

Where the state actually lives is a separate decision, made in
`session_services.py` and not in this file. That is the point of the split.
"""

from __future__ import annotations

from google.adk import Agent

from .model import build_model
from .tools import (
    add_to_itinerary,
    get_activities,
    get_flights,
    get_hotels,
    review_trip,
    save_preferences,
)

# A Gemini instance rather than a bare id string, so the retry budget is bounded.
# See model.py for why that matters on stage.
MODEL = build_model()


flight_agent = Agent(
    name="flight_agent",
    model=MODEL,
    description=(
        "Handles getting to and from a destination: flight availability, airlines, "
        "fares, departure times and connections."
    ),
    instruction=(
        "You handle flights only.\n"
        "\n"
        "What is already known about this trip: {preferences?}\n"
        "\n"
        "Convert city names to IATA codes before calling get_flights, for example "
        "Colombo is CMB and Singapore is SIN. get_flights records the cheapest "
        "option as the chosen flight and adds it to the running trip cost, so say "
        "the new running total back to the traveller.\n"
        "\n"
        "Never invent a flight the tool did not return."
    ),
    tools=[get_flights],
)

hotel_agent = Agent(
    name="hotel_agent",
    model=MODEL,
    description=(
        "Handles where to sleep: hotels, guesthouses and lodges, their nightly "
        "rates, neighbourhoods and ratings."
    ),
    instruction=(
        "You handle accommodation only.\n"
        "\n"
        "What is already known about this trip: {preferences?}\n"
        "\n"
        "Call get_hotels with the city and a nightly ceiling, using 1000 when no "
        "nightly budget was given. The tool picks the best rated affordable option, "
        "bills it for the length of the stay and returns the new running total. "
        "Report the choice, the alternatives and that total."
    ),
    tools=[get_hotels],
)

activity_agent = Agent(
    name="activity_agent",
    model=MODEL,
    description=(
        "Handles what to do once you arrive: sights, tours, hikes, temples, food "
        "experiences and day trips, and builds the day by day itinerary."
    ),
    instruction=(
        "You handle things to do, and you own the itinerary.\n"
        "\n"
        "What is already known about this trip: {preferences?}\n"
        "The itinerary so far: {itinerary?}\n"
        "\n"
        "Work in two steps. First call get_activities to see the options. Then call "
        "add_to_itinerary once for each activity you decide to include, with the "
        "day number and the price. Do not skip the second step: an activity you "
        "only mentioned in your reply is not in the plan.\n"
        "\n"
        "Respect the best_time field, so sunrise hikes go in the morning and "
        "viewpoints in the evening. Keep each day to roughly six or seven hours. "
        "Finish by stating the running cost the tool gave you."
    ),
    tools=[get_activities, add_to_itinerary],
)


root_agent = Agent(
    name="concierge",
    model=MODEL,
    description="Front desk for trip planning. Routes travellers to a specialist.",
    instruction=(
        "You are the concierge of a travel planning desk.\n"
        "\n"
        "Stored preferences for this traveller: {preferences?}\n"
        "Running cost so far in USD: {running_cost_usd?}\n"
        "\n"
        "Before anything else, if the preferences above are empty, call "
        "save_preferences with the city, number of days, total budget and "
        "interests. Ask the traveller for whatever is missing. Every specialist "
        "reads what you store there, so getting it right first saves repeated "
        "questions later.\n"
        "\n"
        "Once preferences exist, route:\n"
        "  flight_agent for getting there,\n"
        "  hotel_agent for where to stay,\n"
        "  activity_agent for what to do and the day by day plan.\n"
        "\n"
        "When someone asks you to plan a number of days somewhere, that is a "
        "request for a day by day plan, so go to activity_agent first. Only go to "
        "flight_agent once the traveller actually mentions travelling there, and "
        "never ask for a departure city unprompted.\n"
        "\n"
        "Call review_trip when the traveller asks what the plan looks like, or when "
        "a conversation resumes and you need to see where things stood.\n"
        "\n"
        "Never answer a travel question from your own knowledge."
    ),
    tools=[save_preferences, review_trip],
    sub_agents=[flight_agent, hotel_agent, activity_agent],
)
