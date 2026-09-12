"""Tools for the pipeline.

Note where the arithmetic lives. The model chooses which activities go on which
day. The tools do every sum. That split is the reason the budget loop terminates:
`check_budget` is not an opinion, it is subtraction, and it sets `escalate` itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from google.adk.tools import ToolContext

from .mock_data import (
    ACTIVITIES,
    FLIGHTS,
    GENERIC_ACTIVITIES,
    GENERIC_FLIGHTS,
    GENERIC_HOTELS,
    HOTELS,
)

# --- What lives in session state -------------------------------------------
#
# Session state is a plain dict with string keys, which means a typo is a silent
# empty read rather than an error: write `chosen_flights` and the presenter simply
# renders a trip with no flight. The constants below stop that inside this file.
#
# They cannot stop it anywhere else, and everywhere else is where it happens. The
# agent instructions in `agent.py` reach into state as raw text, `{hotel_options?}`,
# and `workflow_graph.py` subscripts it directly. Neither goes through a constant.
#
# So the shape is written down once, here, and `tests/test_state_keys.py` asserts
# that every placeholder in every phase's instructions names a key that exists.
# The TypedDict is the declaration; the test is what makes it load bearing.


class Preferences(TypedDict):
    """What `save_preferences` records, and every later step reads."""

    city: str
    days: int
    budget_usd: int
    interests: list[str]
    origin: str


class ItineraryItem(TypedDict):
    """One activity on one day. `set_itinerary_day` builds these."""

    day: int
    activity: str
    price_usd: float
    duration_hours: float


class TripState(TypedDict, total=False):
    """Every key this pipeline reads or writes in session state.

    `total=False` because state fills in as the pipeline runs: nothing holds all of
    these at once, and every read in the codebase is already written to tolerate a
    missing key. The point of the type is the *vocabulary*, not the completeness.
    """

    # Written by the tools in this file.
    preferences: Preferences
    flight_options: list[dict]
    hotel_options: list[dict]
    activity_options: list[dict]
    chosen_flight: dict
    chosen_hotel: dict
    itinerary: list[ItineraryItem]
    total_cost_usd: float
    budget_feedback: str
    budget_status: str

    # Written by ADK itself, from each agent's `output_key`.
    flight_summary: str
    hotel_summary: str
    activity_summary: str
    events_summary: str
    draft_itinerary: str
    budget_verdict: str

    # Written by `resilience.degrade_gracefully` when a researcher's model fails.
    degraded_agents: list[dict]

    # Written by `workflow_graph.budget_gate`, which counts its own passes because
    # a graph has no LoopAgent to do it.
    budget_passes: int


# The same names as strings, for the code that has to subscript state. Deriving the
# set from the TypedDict rather than repeating it keeps the two from disagreeing.
STATE_KEYS: frozenset[str] = frozenset(TripState.__annotations__)

# State keys, in one place.
PREFS = "preferences"
FLIGHT_OPTIONS = "flight_options"
HOTEL_OPTIONS = "hotel_options"
ACTIVITY_OPTIONS = "activity_options"
CHOSEN_FLIGHT = "chosen_flight"
CHOSEN_HOTEL = "chosen_hotel"
ITINERARY = "itinerary"
TOTAL = "total_cost_usd"
FEEDBACK = "budget_feedback"
STATUS = "budget_status"


# --- Step 1: preferences ---------------------------------------------------


def save_preferences(
    city: str,
    days: int,
    budget_usd: int,
    interests: str,
    origin: str,
    tool_context: ToolContext,
) -> dict:
    """Record what the traveller wants. Every later step reads this.

    Args:
        city: Destination city, for example Kandy.
        days: How many days the trip lasts.
        budget_usd: Total budget for the whole trip in USD.
        interests: Comma separated interests, for example "culture, food".
        origin: Where the traveller is flying from, as a city name or IATA code.
            Pass the word none when they have not said, and never guess.

    Returns:
        A dict with "status" and the stored preferences.
    """
    prefs = {
        "city": city,
        "days": max(int(days), 1),
        "budget_usd": int(budget_usd),
        "interests": [i.strip() for i in interests.split(",") if i.strip()],
        "origin": origin.strip(),
    }
    tool_context.state[PREFS] = prefs
    return {"status": "success", "preferences": prefs}


# --- Step 2: the three researchers, run in parallel ------------------------


def research_flights(origin: str, dest: str, date: str, tool_context: ToolContext) -> dict:
    """Find flights and shortlist the cheapest one.

    Args:
        origin: Departure airport as a three letter IATA code, for example LHR.
        dest: Arrival airport as a three letter IATA code, for example CMB.
        date: Departure date in YYYY-MM-DD format.

    Returns:
        A dict with "status", the "flights" found and the "chosen_flight". If the
        traveller never said where they are flying from, this returns status
        skipped and the trip is costed without a flight.
    """
    if not origin or origin.strip().lower() in {"none", "unknown", ""}:
        tool_context.state[FLIGHT_OPTIONS] = []
        tool_context.state[CHOSEN_FLIGHT] = {}
        return {
            "status": "skipped",
            "reason": "No origin given, so the trip is costed without a flight.",
        }

    route = (origin.strip().upper(), dest.strip().upper())
    options = FLIGHTS.get(route, GENERIC_FLIGHTS)
    cheapest = min(options, key=lambda f: f["price_usd"])

    tool_context.state[FLIGHT_OPTIONS] = options
    tool_context.state[CHOSEN_FLIGHT] = cheapest
    return {
        "status": "success",
        "date": date,
        "flights": options,
        "chosen_flight": cheapest,
    }


def research_hotels(city: str, tool_context: ToolContext) -> dict:
    """Find every place to stay in a city and shortlist them all for later.

    Do not pick one here. The itinerary step picks, because only that step knows
    what is left in the budget.

    Args:
        city: City name, for example Kandy.

    Returns:
        A dict with "status" and the "hotels" found.
    """
    options = HOTELS.get(city.strip().lower(), GENERIC_HOTELS)
    tool_context.state[HOTEL_OPTIONS] = options
    return {"status": "success", "hotels": options}


def research_activities(city: str, interests: str, tool_context: ToolContext) -> dict:
    """Find things to do in a city, ranked so interests come first.

    Args:
        city: City name, for example Kandy.
        interests: Comma separated interests, or the word any.

    Returns:
        A dict with "status" and the "activities" found.
    """
    options = list(ACTIVITIES.get(city.strip().lower(), GENERIC_ACTIVITIES))
    wanted = {i.strip().lower() for i in interests.split(",") if i.strip()}

    if wanted and "any" not in wanted:
        options.sort(key=lambda a: a["category"] not in wanted)

    tool_context.state[ACTIVITY_OPTIONS] = options
    return {"status": "success", "activities": options}


# --- Step 3: assemble, inside the loop -------------------------------------


def choose_hotel(name: str, tool_context: ToolContext) -> dict:
    """Pick one hotel from the shortlist for the whole stay.

    Args:
        name: Hotel name exactly as it appeared in the shortlist.

    Returns:
        A dict with "status" and the "chosen_hotel", including what it costs for
        the full stay.
    """
    options = tool_context.state.get(HOTEL_OPTIONS, GENERIC_HOTELS)
    match = next((h for h in options if h["name"].lower() == name.strip().lower()), None)
    if match is None:
        return {
            "status": "error",
            "error_message": f"No hotel called {name}. Choose from: "
            + ", ".join(h["name"] for h in options),
        }

    nights = max(int(tool_context.state.get(PREFS, {}).get("days", 1)) - 1, 1)
    tool_context.state[CHOSEN_HOTEL] = match
    return {
        "status": "success",
        "chosen_hotel": match,
        "nights": nights,
        "stay_cost_usd": match["price_usd_per_night"] * nights,
    }


def set_itinerary_day(day: int, activity_names: list[str], tool_context: ToolContext) -> dict:
    """Set the activities for one day, replacing whatever was there before.

    Replacing rather than appending is what makes this safe to call again on the
    next loop iteration. The tool looks the prices up itself, so it cannot be
    talked into cheaper arithmetic.

    Args:
        day: Which day of the trip, starting at 1.
        activity_names: Activity names exactly as the shortlist gave them.

    Returns:
        A dict with "status", the day that was set and its "day_cost_usd".
    """
    options = tool_context.state.get(ACTIVITY_OPTIONS, GENERIC_ACTIVITIES)
    by_name = {a["name"].lower(): a for a in options}

    chosen, unknown, seen = [], [], set()
    for name in activity_names:
        key = name.strip().lower()
        found = by_name.get(key)
        if found is None:
            unknown.append(name)
        elif key in seen:
            # The same activity listed twice in one call is a slip, not a request
            # to do it twice. Keeping both would double the price and the hours.
            continue
        else:
            seen.add(key)
            chosen.append(
                {
                    "day": int(day),
                    "activity": found["name"],
                    "price_usd": found["price_usd"],
                    "duration_hours": found["duration_hours"],
                }
            )

    itinerary = [i for i in tool_context.state.get(ITINERARY, []) if i["day"] != int(day)]
    itinerary.extend(chosen)
    itinerary.sort(key=lambda i: (i["day"], i["activity"]))
    tool_context.state[ITINERARY] = itinerary

    result = {
        "status": "success",
        "day": int(day),
        "activities": chosen,
        "day_cost_usd": round(sum(i["price_usd"] for i in chosen), 2),
        "day_hours": sum(i["duration_hours"] for i in chosen),
    }
    if unknown:
        result["ignored_unknown_names"] = unknown
    return result


# --- Step 4: the budget gate that ends the loop ----------------------------


def evaluate_budget(state: Mapping[str, Any]) -> dict:
    """Total the trip and compare it to the budget. Pure arithmetic, no side effects.

    Shared by the `check_budget` tool used by the LoopAgent pipeline and by the
    `budget_gate` node used by the Workflow graph, so both runtimes are guaranteed
    to agree on the number.

    Args:
        state: The session state to read. Only read from, never written to, which
            is what lets both runtimes call it safely.

    Returns:
        A dict with "verdict" of either under_budget or over_budget, the
        "total_cost_usd", the "budget_usd", a "breakdown" by category, and a
        "feedback" line written for the assembler to act on. When over budget it
        also carries "overspend_usd", the most expensive activities and the
        cheaper hotels available.
    """
    prefs = state.get(PREFS, {})
    budget = float(prefs.get("budget_usd", 0) or 0)
    days = max(int(prefs.get("days", 1)), 1)
    nights = max(days - 1, 1)

    flight = state.get(CHOSEN_FLIGHT) or {}
    hotel = state.get(CHOSEN_HOTEL) or {}
    itinerary = state.get(ITINERARY, [])

    flight_cost = float(flight.get("price_usd", 0) or 0)
    hotel_cost = float(hotel.get("price_usd_per_night", 0) or 0) * nights
    activity_cost = float(sum(i["price_usd"] for i in itinerary))
    total = round(flight_cost + hotel_cost + activity_cost, 2)

    breakdown = {
        "flight_usd": round(flight_cost, 2),
        "hotel_usd": round(hotel_cost, 2),
        "activities_usd": round(activity_cost, 2),
    }

    if not budget:
        # No budget recorded, usually because save_preferences never ran. Saying
        # "under budget" here would be a lie that reads as a pass, so the loop is
        # allowed to end but the feedback says plainly that nothing was checked.
        return {
            "verdict": "under_budget",
            "total_cost_usd": total,
            "budget_usd": 0.0,
            "breakdown": breakdown,
            "feedback": (
                f"No budget was recorded, so the trip could not be checked "
                f"against one. It currently totals {total} USD."
            ),
        }

    if total > budget:
        overspend = round(total - budget, 2)
        feedback = (
            f"Over budget by {overspend} USD. Total {total}, budget {budget}. "
            f"Hotel is {breakdown['hotel_usd']} for {nights} nights, activities are "
            f"{breakdown['activities_usd']}. Cut cost by choosing a cheaper hotel or "
            f"dropping expensive activities, then set the affected days again."
        )
        return {
            "verdict": "over_budget",
            "total_cost_usd": total,
            "budget_usd": budget,
            "overspend_usd": overspend,
            "breakdown": breakdown,
            "most_expensive_activities": sorted(
                itinerary, key=lambda i: i["price_usd"], reverse=True
            )[:3],
            "cheaper_hotels": sorted(
                state.get(HOTEL_OPTIONS, []), key=lambda h: h["price_usd_per_night"]
            )[:2],
            "feedback": feedback,
        }

    return {
        "verdict": "under_budget",
        "total_cost_usd": total,
        "budget_usd": budget,
        "breakdown": breakdown,
        "feedback": f"Within budget at {total} USD of {budget} USD.",
    }


def check_budget(tool_context: ToolContext) -> dict:
    """Total the trip, compare it to the budget, and end the loop if it fits.

    Call this once, after the itinerary for every day has been set.

    This is the loop's exit condition. It is deliberately arithmetic rather than
    judgement: it sets escalate itself when the trip fits, so the LoopAgent stops
    without the model having to decide anything.

    Returns:
        A dict with "status", the "total_cost_usd", the "budget_usd", and
        "verdict" of either under_budget or over_budget. When over, it also
        carries "overspend_usd" and the most expensive items to consider cutting.
    """
    state = tool_context.state
    result = evaluate_budget(state)

    state[TOTAL] = result["total_cost_usd"]
    state[FEEDBACK] = result["feedback"]
    state[STATUS] = result["verdict"]

    if result["verdict"] == "under_budget":
        # This is the line that ends the LoopAgent. No model judgement involved.
        tool_context.actions.escalate = True

    return {"status": "success", **result}
