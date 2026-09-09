"""The client half of A2A: consuming an agent that lives somewhere else.

    RemoteA2aAgent(name=..., agent_card="http://localhost:8001/.well-known/agent-card.json")

That is it. From here on it behaves like any other sub agent. It goes into
`sub_agents`, the parent transfers to it, it returns a response. The trip planner
never imports the local expert's code, never sees its tools, and does not know what
model it runs on.

Which is the story: different teams own different agents, deploy on their own
schedule, and still compose into one product.

## Failing well

If the service is not running, the whole pipeline should not die. `build_local_expert()`
returns None when the card is unreachable, and `agent.py` simply leaves that agent
out of the fan out. A local expert is a nice to have, not a dependency, and a demo
that hard fails because a second terminal was not started is a bad demo.
"""

from __future__ import annotations

import warnings

import httpx
from google.adk.agents import BaseAgent

warnings.filterwarnings("ignore")

LOCAL_EXPERT_CARD = "http://localhost:8001/.well-known/agent-card.json"


def local_expert_available(timeout: float = 1.0) -> bool:
    """Return True if the local expert service is up and serving its card."""
    try:
        response = httpx.get(LOCAL_EXPERT_CARD, timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def build_local_expert() -> BaseAgent | None:
    """Return the remote local expert, or None when the service is not running.

    Returning None rather than raising is deliberate. See the module docstring.
    """
    if not local_expert_available():
        return None

    from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

    return RemoteA2aAgent(
        name="local_expert",
        agent_card=LOCAL_EXPERT_CARD,
        description=(
            "A local who lives at the destination. Knows timing, transport, "
            "etiquette and the practical detail that is not in any listing."
        ),
    )
