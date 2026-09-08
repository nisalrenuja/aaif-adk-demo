"""Demo the confirmation gate on its own, without paying for a full pipeline run.

It seeds a finished trip into session state, runs only `booking_agent`, and stops
when `book_trip` asks for approval. You answer. It resumes.

    python3 -m agents.p6_safety.run_booking            # asks you at the terminal
    python3 -m agents.p6_safety.run_booking approve    # scripted, for a rehearsal
    python3 -m agents.p6_safety.run_booking reject     # show the refusal path too

Show the reject path. Approving is the boring half. The interesting half is that
the agent handles being told no.
"""

from __future__ import annotations

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_confirmation import ToolConfirmation
from google.genai import types

from .agent import booking_agent

# The function call ADK emits when a tool is waiting on a human.
CONFIRMATION_CALL = "adk_request_confirmation"

APP_NAME = "booking_demo"
USER_ID = "demo_traveller"
SESSION_ID = "booking"

# A finished trip, so this script costs two or three model calls instead of
# fifteen. Everything here is what Phase 3 would have produced.
FINISHED_TRIP = {
    "preferences": {
        "city": "Kandy",
        "days": 3,
        "budget_usd": 250,
        "interests": ["culture", "food"],
        "origin": "none",
    },
    "chosen_flight": {},
    "chosen_hotel": {
        "name": "Kandy Hills Rest",
        "area": "Hantana",
        "price_usd_per_night": 42,
        "rating": 4.1,
        "style": "budget guesthouse",
    },
    "itinerary": [
        {"day": 1, "activity": "Temple of the Sacred Tooth Relic", "price_usd": 12, "duration_hours": 2},
        {"day": 1, "activity": "Kandy Lake walk", "price_usd": 0, "duration_hours": 1},
        {"day": 2, "activity": "Udawattakele forest hike", "price_usd": 6, "duration_hours": 3},
        {"day": 3, "activity": "Royal Botanical Gardens, Peradeniya", "price_usd": 10, "duration_hours": 3},
    ],
    "total_cost_usd": 112.0,
    "budget_status": "under_budget",
}


def _find_confirmation_request(event):
    """Return the pending confirmation call on this event, if there is one."""
    for call in event.get_function_calls() or []:
        if call.name == CONFIRMATION_CALL:
            return call
    return None


def _decide(confirmation_call, state: dict, scripted: str | None) -> bool:
    """Ask the human, or use the scripted answer during a rehearsal.

    The confirmation call carries `originalFunctionCall`, which is the exact call
    that is being held. A real product renders its own approval screen from that.
    This is the terminal version of the same idea.
    """
    pending = confirmation_call.args.get("originalFunctionCall", {})
    args = pending.get("args", {})

    print("\n" + "=" * 70)
    print("  THE AGENT HAS PAUSED AND IS WAITING FOR A HUMAN")
    print("=" * 70)
    print(f"\n  It wants to call: {pending.get('name', 'unknown')}")
    for key, value in args.items():
        print(f"      {key}: {value}")
    print(f"\n  This will charge: {state.get('total_cost_usd')} USD")
    hotel = (state.get("chosen_hotel") or {}).get("name")
    if hotel:
        print(f"  Hotel:            {hotel}")
    print(f"  Activities:       {len(state.get('itinerary', []))}")
    print("\n  This tool is irreversible. Nothing has been charged yet.\n")

    if scripted is not None:
        approved = scripted == "approve"
        print(f"  [scripted answer: {scripted}]")
        return approved

    answer = input("  Approve this booking? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _confirmation_response(call_id: str, approved: bool) -> types.Content:
    """Build the message that answers the confirmation request."""
    return types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=call_id,
                    name=CONFIRMATION_CALL,
                    response=ToolConfirmation(confirmed=approved).model_dump(
                        by_alias=True
                    ),
                )
            )
        ],
    )


async def main(scripted: str | None) -> None:
    load_dotenv()

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state=dict(FINISHED_TRIP),
    )
    runner = Runner(
        app_name=APP_NAME, agent=booking_agent, session_service=session_service
    )

    request = types.Content(
        role="user",
        parts=[
            types.Part(
                text=(
                    "Yes, book it. The name is A. Traveller and the email is "
                    "traveller@example.com."
                )
            )
        ],
    )

    pending = None
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=request
    ):
        for call in event.get_function_calls() or []:
            if call.name != CONFIRMATION_CALL:
                print(f"  [{event.author}] -> {call.name}({call.args})")
        pending = _find_confirmation_request(event) or pending
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                print(f"\n{text}\n")

    if pending is None:
        print("\nThe agent did not ask for confirmation. It probably wanted a name")
        print("and an email first, which is also correct behaviour.")
        return

    paused_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    approved = _decide(pending, dict(paused_session.state), scripted)
    print(f"\n  ...resuming as {'APPROVED' if approved else 'REJECTED'}\n")

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=_confirmation_response(pending.id, approved),
    ):
        for call in event.get_function_calls() or []:
            if call.name != CONFIRMATION_CALL:
                print(f"  [{event.author}] -> {call.name}")
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                print(f"\n{text}\n")

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    bookings = session.state.get("bookings", [])
    print(f"[bookings in state: {len(bookings)}]")
    for booking in bookings:
        print(f"  {booking['reference']} charged {booking['charged_usd']} USD")


if __name__ == "__main__":
    choice = sys.argv[1].lower() if len(sys.argv) > 1 else None
    if choice not in {None, "approve", "reject"}:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(main(choice))
