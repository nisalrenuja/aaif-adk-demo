"""Serve the local expert over the A2A protocol.

    python3 -m local_expert_service.server

Then it is reachable at http://localhost:8001, and its agent card, the machine
readable description of what it can do, is at

    http://localhost:8001/.well-known/agent-card.json

Two lines do the work:

    app = to_a2a(root_agent, port=PORT)
    uvicorn.run(app, ...)

`to_a2a` wraps an ordinary ADK agent in a Starlette app that speaks A2A. The agent
in agent.py has no idea it is being served. It has no A2A imports, no server code
and no protocol knowledge. That separation is the reason this is worth showing:
publishing an agent is a deployment decision, not a rewrite.
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import uvicorn
from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import root_agent

HOST = "localhost"
PORT = 8001


def main() -> None:
    """Serve the local expert over A2A until interrupted."""
    load_dotenv()
    app = to_a2a(root_agent, host=HOST, port=PORT)

    print(f"local_expert serving on http://{HOST}:{PORT}")
    print(f"agent card: http://{HOST}:{PORT}/.well-known/agent-card.json")
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
