"""The one tool that spends money, and the gate in front of it.

Every tool so far has been a read. `book_trip` is not: it is the point where the
agent does something a human cannot undo by asking nicely. So it does not run until
a person says yes.

The gate is one argument:

    FunctionTool(func=book_trip, require_confirmation=True)

That is the whole mechanism. ADK intercepts the call before the function body runs,
emits a confirmation request, and pauses the invocation. Nothing in `book_trip`
knows this is happening, which is the point: the safety property does not depend on
the tool author remembering to implement it.

## What actually happens on the wire

1. The model decides to call `book_trip(...)`.
2. ADK sees `require_confirmation` and there is no confirmation yet, so instead of
   running the function it emits a function call named `adk_request_confirmation`
   carrying the pending call's id, and stops.
3. A human approves or rejects.
4. The client sends back a `FunctionResponse` with that same id and a
   `ToolConfirmation` payload.
5. Approved, the function body finally runs. Rejected, the tool returns
   `This tool call is rejected` and the model has to deal with that.

Step 3 is deliberately outside the model's reach. It cannot approve itself, cannot
be talked into approving itself, and cannot route around the gate, because the gate
is in the framework rather than in a prompt.
"""

from __future__ import annotations

import random
import string

from google.adk.tools import FunctionTool, ToolContext

BOOKINGS = "bookings"


def _reference() -> str:
    """A booking reference that looks like the real thing."""
    return "TRP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def book_trip(traveller_name: str, email: str, tool_context: ToolContext) -> dict:
    """Book the trip currently in the plan: flight, hotel and every activity.

    This charges the traveller and cannot be undone from here. Only call it when
    the traveller has clearly asked to book, and never to check whether something
    is available.

    Args:
        traveller_name: Full name for the booking, as it appears on their passport.
        email: Email address for the confirmation.

    Returns:
        A dict with "status", a "reference" to quote, what was charged, and a
        "side_effects" field. Report the side effects exactly as given: this
        records a booking and nothing else. It does not send email, contact an
        airline or hotel, or move money.
    """
    state = tool_context.state

    flight = state.get("chosen_flight") or {}
    hotel = state.get("chosen_hotel") or {}
    itinerary = state.get("itinerary", [])
    total = state.get("total_cost_usd")

    if not hotel and not itinerary:
        return {
            "status": "error",
            "error_message": (
                "There is no plan to book yet. Build the itinerary first."
            ),
        }

    booking = {
        "reference": _reference(),
        "traveller_name": traveller_name,
        "email": email,
        "flight": flight or None,
        "hotel": hotel or None,
        "days_booked": len({item["day"] for item in itinerary}),
        "activities_booked": len(itinerary),
        "charged_usd": total,
        # Spelled out because the model will otherwise fill the gap itself. An
        # early run of this demo cheerfully told the traveller "a confirmation
        # email has been sent to your address". Nothing of the sort happened.
        "side_effects": (
            "None. This is a mock booking stored in session state. No email was "
            "sent, no airline or hotel was contacted, and no payment was taken."
        ),
    }

    state[BOOKINGS] = [*state.get(BOOKINGS, []), booking]

    return {"status": "success", **booking}


def cancel_booking(reference: str, tool_context: ToolContext) -> dict:
    """Cancel a booking that was already made.

    Args:
        reference: The booking reference, for example TRP-4KD9XQ.

    Returns:
        A dict with "status" saying whether the booking was found and cancelled.
    """
    bookings = tool_context.state.get(BOOKINGS, [])
    remaining = [b for b in bookings if b["reference"] != reference.strip().upper()]

    if len(remaining) == len(bookings):
        return {"status": "error", "error_message": f"No booking called {reference}."}

    tool_context.state[BOOKINGS] = remaining
    return {"status": "success", "cancelled": reference, "refunded": True}


# The gate. `book_trip` spends money, so it waits for a human.
book_trip_tool = FunctionTool(func=book_trip, require_confirmation=True)

# Cancelling is safe and reversible in the traveller's favour, so it does not need
# a gate. Gate what is irreversible, not everything, or people stop reading the
# prompts and start clicking approve on reflex.
cancel_booking_tool = FunctionTool(func=cancel_booking)
