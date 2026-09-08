"""The three function tools, one per specialist agent.

Same rules as Phase 0: typed arguments, a docstring that reads like instructions to
the model, and a dict return that never raises.
"""

from __future__ import annotations

from .mock_data import (
    ACTIVITIES,
    FLIGHTS,
    GENERIC_ACTIVITIES,
    GENERIC_FLIGHTS,
    GENERIC_HOTELS,
    HOTELS,
)


def get_flights(origin: str, dest: str, date: str) -> dict:
    """Look up available flights between two airports on a given date.

    Args:
        origin: Departure airport as a three letter IATA code, for example CMB.
        dest: Arrival airport as a three letter IATA code, for example SIN.
        date: Departure date in YYYY-MM-DD format.

    Returns:
        A dict with "status", and on success a "flights" list where each option has
        carrier, number, depart, arrive, price_usd and stops.
    """
    if not origin or not dest:
        return {"status": "error", "error_message": "origin and dest are required."}

    route = (origin.strip().upper(), dest.strip().upper())
    return {
        "status": "success",
        "origin": route[0],
        "dest": route[1],
        "date": date,
        "flights": FLIGHTS.get(route, GENERIC_FLIGHTS),
    }


def get_hotels(city: str, max_price_usd: int) -> dict:
    """Look up places to stay in a city, filtered by nightly price.

    Args:
        city: City name, for example Kandy.
        max_price_usd: Highest acceptable nightly rate in USD. Pass a large number
            such as 1000 when the traveller has not stated a budget.

    Returns:
        A dict with "status", and on success a "hotels" list where each option has
        name, area, price_usd_per_night, rating and style.
    """
    if not city:
        return {"status": "error", "error_message": "city is required."}

    options = HOTELS.get(city.strip().lower(), GENERIC_HOTELS)
    affordable = [h for h in options if h["price_usd_per_night"] <= max_price_usd]

    if not affordable:
        cheapest = min(options, key=lambda h: h["price_usd_per_night"])
        return {
            "status": "success",
            "city": city,
            "hotels": [cheapest],
            "note": (
                f"Nothing under {max_price_usd} USD a night in {city}. Returning the "
                f"cheapest option at {cheapest['price_usd_per_night']} USD instead."
            ),
        }

    return {"status": "success", "city": city, "hotels": affordable}


def get_activities(city: str, category: str) -> dict:
    """Look up things to do in a city, optionally narrowed to one category.

    Args:
        city: City name, for example Kandy.
        category: One of culture, outdoors, food, or the word any to get everything.

    Returns:
        A dict with "status", and on success an "activities" list where each option
        has name, category, duration_hours, price_usd and best_time.
    """
    if not city:
        return {"status": "error", "error_message": "city is required."}

    options = ACTIVITIES.get(city.strip().lower(), GENERIC_ACTIVITIES)
    wanted = category.strip().lower()

    if wanted and wanted != "any":
        filtered = [a for a in options if a["category"] == wanted]
        if filtered:
            options = filtered

    return {"status": "success", "city": city, "activities": options}
