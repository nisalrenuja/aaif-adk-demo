"""Print what is stored in the SQLite session database.

No model call, no API key needed. Run it after `run_cli.py`, or after killing and
restarting `adk web`, to prove the trip is still there.

    python3 -m agents.p2_state.show_state
"""

from __future__ import annotations

import asyncio
import json

from .session_services import APP_NAME, DB_PATH, SQLITE_URL


async def main() -> None:
    if not DB_PATH.exists():
        print(f"No database yet at {DB_PATH}.")
        print("Run `python3 -m agents.p2_state.run_cli` first, or use adk web with")
        print('  adk web agents --session_service_uri="sqlite:///./trip.db"')
        return

    from google.adk.sessions import DatabaseSessionService

    service = DatabaseSessionService(db_url=SQLITE_URL)
    try:
        listing = await service.list_sessions(app_name=APP_NAME)

        if not listing.sessions:
            print(f"Database exists at {DB_PATH} but holds no sessions yet.")
            return

        for stub in listing.sessions:
            session = await service.get_session(
                app_name=APP_NAME, user_id=stub.user_id, session_id=stub.id
            )
            print(
                f"\nsession {stub.id}  "
                f"(user {stub.user_id}, {len(session.events)} events)"
            )
            print(json.dumps(dict(session.state), indent=2, default=str))
    finally:
        # Without this the SQLAlchemy engine keeps a thread alive and the script
        # never returns to your prompt. See the phase README.
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
