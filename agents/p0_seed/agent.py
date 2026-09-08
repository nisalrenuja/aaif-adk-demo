"""Phase 0: the seed.

One Agent. One tool. That is the whole surface area of ADK you need to start.

The teaching point: a tool in ADK is just a typed Python function with a good
docstring. ADK reads the signature and the docstring and turns them into the
function declaration the model sees. There is no decorator, no registry, no schema
file. If your docstring is vague, your agent is vague.
"""

from __future__ import annotations

from google.adk import Agent

from .mock_data import FLIGHTS, GENERIC_FLIGHTS

# Pinned on purpose, and this exact id was chosen the hard way. gemini-2.5-flash
# returns 404 for new API keys, and ADK 2.5's own default, gemini-3.5-flash, was
# returning 503 during this build. See docs/MODELS.md.
MODEL = "gemini-3.6-flash"


def get_flights(origin: str, dest: str, date: str) -> dict:
    """Look up available flights between two airports on a given date.

    Use this whenever the traveller asks about flights, fares or how to get from
    one city to another. Call it once per leg of the journey.

    Args:
        origin: Departure airport as a three letter IATA code, for example CMB.
        dest: Arrival airport as a three letter IATA code, for example SIN.
        date: Departure date in YYYY-MM-DD format.

    Returns:
        A dict with a "status" key. On success it also carries "flights", a list of
        options each holding carrier, number, depart, arrive, price_usd and stops.
        On failure it carries "error_message" explaining what went wrong.
    """
    if not origin or not dest:
        return {
            "status": "error",
            "error_message": "Both origin and dest are required, as IATA codes.",
        }

    route = (origin.strip().upper(), dest.strip().upper())
    options = FLIGHTS.get(route, GENERIC_FLIGHTS)

    return {
        "status": "success",
        "origin": route[0],
        "dest": route[1],
        "date": date,
        "flights": options,
    }


# ADK looks for a module level name called root_agent. That is what `adk web`
# loads and what the Runner executes.
root_agent = Agent(
    name="flight_agent",
    model=MODEL,
    description="Finds flights between two airports on a given date.",
    instruction=(
        "You are a concise flight search assistant.\n"
        "\n"
        "Call get_flights to answer any question about flights. Convert city names "
        "to IATA codes yourself before calling it, for example Colombo is CMB and "
        "Singapore is SIN. If the traveller has not given you a date, ask for one "
        "rather than guessing.\n"
        "\n"
        "Present results as a short list. Lead with the cheapest non stop option. "
        "Always show the price in USD. Never invent a flight that the tool did not "
        "return."
    ),
    tools=[get_flights],
)
