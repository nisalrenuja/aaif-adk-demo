"""Talk to the concierge from the terminal, against the persistent session.

The demo: run it once, stop it, run it again with the same session id, and the
trip is still there.

    python3 -m agents.p2_state.run_cli "3 days in Kandy, budget 600, I like culture"
    python3 -m agents.p2_state.run_cli "what does my plan look like so far?"

Needs GOOGLE_API_KEY in .env. Use show_state.py to inspect state without a key.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.genai import types

from .agent import root_agent
from .session_services import APP_NAME, build_session_service

USER_ID = "demo_traveller"
SESSION_ID = "kandy_trip"


async def main(message: str) -> None:
    load_dotenv()

    session_service = build_session_service()

    # Reuse the session if it is already on disk, otherwise start it.
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
        )
        print(f"[new session {SESSION_ID}]")
    else:
        print(f"[resumed session {SESSION_ID} with {len(session.events)} events]")

    runner = Runner(
        app_name=APP_NAME, agent=root_agent, session_service=session_service
    )

    content = types.Content(role="user", parts=[types.Part(text=message)])
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=content
    ):
        for call in event.get_function_calls() or []:
            print(f"  -> {call.name}({call.args})")
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
            if text.strip():
                print(f"\n{text.strip()}\n")

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    print(f"[state keys now: {sorted(session.state.keys())}]")

    # Without this the SQLAlchemy engine keeps a thread alive and the script
    # never returns to your prompt. See the phase README.
    close = getattr(session_service, "close", None)
    if close is not None:
        await close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(main(" ".join(sys.argv[1:])))
