"""Tools that read and write session state.

The change from Phase 1 is one parameter. Any tool that declares

    tool_context: ToolContext

gets the live session handed to it, and `tool_context.state` is a dict that
survives across turns, across agents, and (from this phase on) across restarts.

ADK strips that parameter out of the declaration it shows the model, so the model
never sees it and never tries to fill it in.
"""

from __future__ import annotations

from google.adk.tools import ToolContext

from .mock_data import (
    ACTIVITIES,
    FLIGHTS,
    GENERIC_ACTIVITIES,
    GENERIC_FLIGHTS,
    GENERIC_HOTELS,
    HOTELS,
)

# State keys, in one place so a typo cannot quietly split the state in two.
PREFS = "preferences"
ITINERARY = "itinerary"
COST = "running_cost_usd"


def _bump_cost(state, amount: float) -> float:
    """Add to the running trip cost and return the new total."""
    total = round(float(state.get(COST, 0)) + float(amount), 2)
    state[COST] = total
    return total


def save_preferences(
    city: str,
    days: int,
    budget_usd: int,
    interests: str,
    tool_context: ToolContext,
) -> dict:
    """Record what the traveller wants, so every later step can read it.

    Call this once, as early as possible, before looking anything up.

    Args:
        city: Destination city, for example Kandy.
        days: How many days the trip lasts.
        budget_usd: Total budget for the whole trip in USD.
        interests: Comma separated interests, for example "culture, food".

    Returns:
        A dict with "status" and the preferences that were stored.
    """
    prefs = {
        "city": city,
        "days": days,
        "budget_usd": budget_usd,
        "interests": [i.strip() for i in interests.split(",") if i.strip()],
    }
    tool_context.state[PREFS] = prefs
    tool_context.state.setdefault(ITINERARY, [])
    tool_context.state.setdefault(COST, 0)
    return {"status": "success", "preferences": prefs}


def get_flights(origin: str, dest: str, date: str, tool_context: ToolContext) -> dict:
    """Look up flights, and remember the cheapest one as part of the trip.

    Args:
        origin: Departure airport as a three letter IATA code, for example CMB.
        dest: Arrival airport as a three letter IATA code, for example SIN.
        date: Departure date in YYYY-MM-DD format.

    Returns:
        A dict with "status", a "flights" list, and "running_cost_usd" after the
        cheapest option has been added to the trip total.
    """
    if not origin or not dest:
        return {"status": "error", "error_message": "origin and dest are required."}

    route = (origin.strip().upper(), dest.strip().upper())
    options = FLIGHTS.get(route, GENERIC_FLIGHTS)
    cheapest = min(options, key=lambda f: f["price_usd"])

    state = tool_context.state
    state["chosen_flight"] = cheapest
    total = _bump_cost(state, cheapest["price_usd"])

    return {
        "status": "success",
        "date": date,
        "flights": options,
        "chosen_flight": cheapest,
        "running_cost_usd": total,
    }


def get_hotels(city: str, max_price_usd: int, tool_context: ToolContext) -> dict:
    """Look up places to stay, and remember the best rated affordable one.

    Args:
        city: City name, for example Kandy.
        max_price_usd: Highest acceptable nightly rate in USD. Pass 1000 when the
            traveller has not stated a nightly budget.

    Returns:
        A dict with "status", a "hotels" list, the "chosen_hotel", and
        "running_cost_usd" after the stay has been added to the trip total.
    """
    if not city:
        return {"status": "error", "error_message": "city is required."}

    state = tool_context.state
    options = HOTELS.get(city.strip().lower(), GENERIC_HOTELS)
    affordable = [h for h in options if h["price_usd_per_night"] <= max_price_usd]
    if not affordable:
        affordable = [min(options, key=lambda h: h["price_usd_per_night"])]

    chosen = max(affordable, key=lambda h: h["rating"])
    nights = max(int(state.get(PREFS, {}).get("days", 1)) - 1, 1)

    state["chosen_hotel"] = chosen
    total = _bump_cost(state, chosen["price_usd_per_night"] * nights)

    return {
        "status": "success",
        "hotels": affordable,
        "chosen_hotel": chosen,
        "nights": nights,
        "running_cost_usd": total,
    }


def get_activities(city: str, category: str) -> dict:
    """Look up things to do in a city, narrowed to one category.

    This only reads. Use add_to_itinerary to actually commit something to the plan.

    Args:
        city: City name, for example Kandy.
        category: One of culture, outdoors, food, or the word any for everything.

    Returns:
        A dict with "status" and an "activities" list.
    """
    if not city:
        return {"status": "error", "error_message": "city is required."}

    options = ACTIVITIES.get(city.strip().lower(), GENERIC_ACTIVITIES)
    wanted = category.strip().lower()
    if wanted and wanted != "any":
        narrowed = [a for a in options if a["category"] == wanted]
        if narrowed:
            options = narrowed

    return {"status": "success", "activities": options}


def add_to_itinerary(
    day: int,
    activity: str,
    price_usd: float,
    tool_context: ToolContext,
) -> dict:
    """Commit one activity to a specific day of the trip and bill it.

    Call this once per activity you decide to include. The itinerary grows in
    session state, so it is still there on the next turn and after a restart.

    Args:
        day: Which day of the trip, starting at 1.
        activity: Name of the activity, exactly as get_activities returned it.
        price_usd: Cost per person in USD.

    Returns:
        A dict with "status", the full "itinerary" so far, and "running_cost_usd".
    """
    state = tool_context.state

    itinerary = list(state.get(ITINERARY, []))
    itinerary.append({"day": day, "activity": activity, "price_usd": price_usd})
    itinerary.sort(key=lambda item: item["day"])
    state[ITINERARY] = itinerary

    total = _bump_cost(state, price_usd)

    return {"status": "success", "itinerary": itinerary, "running_cost_usd": total}


def review_trip(tool_context: ToolContext) -> dict:
    """Read back everything stored about this trip so far.

    Call this when the traveller asks what the plan looks like, or at the start of
    a new conversation to pick up where you left off.

    Returns:
        A dict with the stored preferences, chosen flight and hotel, the itinerary
        and the running cost.
    """
    state = tool_context.state
    return {
        "status": "success",
        "preferences": state.get(PREFS),
        "chosen_flight": state.get("chosen_flight"),
        "chosen_hotel": state.get("chosen_hotel"),
        "itinerary": state.get(ITINERARY, []),
        "running_cost_usd": state.get(COST, 0),
    }
