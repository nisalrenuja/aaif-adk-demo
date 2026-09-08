"""Shared plumbing for the two demo scripts in this phase.

Kept separate so run_pipeline.py and run_graph.py differ only in the one line that
matters: which runtime they hand to the Runner.
"""

from __future__ import annotations

import json
import warnings

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

warnings.filterwarnings("ignore", message=r".*deprecated in favor of Workflow.*")
warnings.filterwarnings("ignore", message=r".*EXPERIMENTAL.*")

APP_NAME = "trip_pipeline"
USER_ID = "demo_traveller"
SESSION_ID = "pipeline_run"

_INTERESTING_STATE = [
    "preferences",
    "chosen_flight",
    "chosen_hotel",
    "itinerary",
    "total_cost_usd",
    "budget_status",
    "budget_feedback",
]


async def run(message: str, **runner_kwargs) -> None:
    """Run one request and narrate which agent or node did what.

    Args:
        message: The traveller's request.
        **runner_kwargs: Either `agent=...` for the classic pipeline or `node=...`
            for the Workflow graph. That single difference is the whole comparison.
    """
    load_dotenv()

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    runner = Runner(
        app_name=APP_NAME, session_service=session_service, **runner_kwargs
    )

    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""

    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=content
    ):
        for call in event.get_function_calls() or []:
            print(f"  [{event.author}] -> {call.name}")
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                final_text = text
                print(f"  [{event.author}] finished")

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    print("\n--- final plan ---\n")
    print(final_text)

    print("\n--- state the pipeline built ---\n")
    for key in _INTERESTING_STATE:
        if key in session.state:
            print(f"{key}: {json.dumps(session.state[key], default=str)}")
