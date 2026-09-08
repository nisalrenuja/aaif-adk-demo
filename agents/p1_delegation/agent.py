"""Phase 1: delegation.

One agent that does everything becomes three specialists plus a concierge that
routes to them.

The teaching point: `sub_agents` is the whole multi agent primitive. You do not
write a router. The concierge is an LLM that reads each sub agent's `description`
and calls the built in `transfer_to_agent` tool to hand the conversation over.

Which means the `description` field stops being documentation and becomes routing
logic. That is the single most important line in each specialist below.
"""

from __future__ import annotations

from google.adk import Agent

from .tools import get_activities, get_flights, get_hotels

MODEL = "gemini-3.6-flash"


# --- The specialists -------------------------------------------------------
# Each one owns a narrow job and exactly the tools that job needs. Note how the
# descriptions are written for a reader who has to choose between them, not for a
# developer browsing the file.

flight_agent = Agent(
    name="flight_agent",
    model=MODEL,
    description=(
        "Handles getting to and from a destination: flight availability, airlines, "
        "fares, departure times and connections. Use for anything about flying."
    ),
    instruction=(
        "You handle flights only.\n"
        "\n"
        "Convert city names to IATA codes before calling get_flights, for example "
        "Colombo is CMB and Singapore is SIN. Ask for a date if you do not have one.\n"
        "\n"
        "Report the cheapest non stop first, then one alternative. Give prices in "
        "USD. Never invent a flight the tool did not return.\n"
        "\n"
        "If the traveller moves on to hotels or things to do, say so plainly and let "
        "the concierge take over rather than guessing outside your area."
    ),
    tools=[get_flights],
)

hotel_agent = Agent(
    name="hotel_agent",
    model=MODEL,
    description=(
        "Handles where to sleep: hotels, guesthouses, hostels and lodges, their "
        "nightly rates, neighbourhoods and ratings. Use for anything about "
        "accommodation or where to stay."
    ),
    instruction=(
        "You handle accommodation only.\n"
        "\n"
        "Call get_hotels with the city and a nightly ceiling. If the traveller has "
        "not given a budget, pass 1000 rather than asking, then mention the range "
        "you found.\n"
        "\n"
        "Recommend two or three options across price points and say who each one "
        "suits. Always quote the nightly rate in USD."
    ),
    tools=[get_hotels],
)

activity_agent = Agent(
    name="activity_agent",
    model=MODEL,
    description=(
        "Handles what to do once you arrive: sights, tours, hikes, temples, food "
        "experiences and day trips, including how long each takes and what it "
        "costs. Use for anything about things to do, itineraries or sightseeing."
    ),
    instruction=(
        "You handle things to do only.\n"
        "\n"
        "Call get_activities with the city and a category, using the word any when "
        "the traveller has not expressed a preference.\n"
        "\n"
        "When asked to fill several days, group activities by day and respect the "
        "best_time field, so put sunrise hikes in the morning and viewpoints in the "
        "evening. Keep each day to roughly six or seven hours of activity. Show the "
        "cost of each item in USD."
    ),
    tools=[get_activities],
)


# --- The concierge ---------------------------------------------------------
# It has no tools of its own. Its whole job is deciding who should answer.

root_agent = Agent(
    name="concierge",
    model=MODEL,
    description="Front desk for trip planning. Routes travellers to a specialist.",
    instruction=(
        "You are the concierge of a travel planning desk. You do not look anything "
        "up yourself. You have three specialists and your job is to get the "
        "traveller to the right one.\n"
        "\n"
        "Transfer to flight_agent for anything about getting there.\n"
        "Transfer to hotel_agent for anything about where to stay.\n"
        "Transfer to activity_agent for anything about what to do or day by day "
        "plans.\n"
        "\n"
        "If a request spans several of these, such as planning a whole trip, handle "
        "one part at a time: transfer for the first part, and when that specialist "
        "is finished, move on to the next.\n"
        "\n"
        "Only ask the traveller a question yourself when you genuinely cannot tell "
        "which specialist is needed. Never answer a travel question from your own "
        "knowledge."
    ),
    # This one argument is the entire multi agent mechanism.
    sub_agents=[flight_agent, hotel_agent, activity_agent],
)
