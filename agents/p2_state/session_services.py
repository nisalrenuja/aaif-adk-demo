"""Where the state actually lives.

This is the whole point of Phase 2. The agents in `agent.py` never mention storage.
They write to `tool_context.state`. Swapping the backing store is a one line change
here, and nothing else in the project moves.

    InMemorySessionService()                  gone when the process exits
    DatabaseSessionService(db_url=SQLITE_URL) survives a restart
    VertexAiSessionService(...)               managed, in the cloud

Same interface, three deployment stories.
"""

from __future__ import annotations

from pathlib import Path

from google.adk.sessions import BaseSessionService

APP_NAME = "trip_planner"

# The SQLite file lands next to this module, so it is easy to find, delete and
# show on stage. It is gitignored.
DB_PATH = Path(__file__).parent / "trip_sessions.db"
SQLITE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Flip this on stage. That is the demo.
PERSIST = True


def build_session_service() -> BaseSessionService:
    """Return the session service the demo should use right now."""
    if PERSIST:
        # Requires sqlalchemy and aiosqlite, both in requirements.txt.
        from google.adk.sessions import DatabaseSessionService

        return DatabaseSessionService(db_url=SQLITE_URL)

    from google.adk.sessions import InMemorySessionService

    return InMemorySessionService()
