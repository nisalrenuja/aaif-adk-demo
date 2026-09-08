"""The local expert. A separate service, owned by a different team.

This agent is not imported by the trip planner. It runs in its own process, on its
own port, and could just as easily run on someone else's machine in someone else's
repository written by someone you have never met.

The trip planner reaches it over the A2A protocol, which is the whole point of
Phase 7: agents compose across process and team boundaries, not just across
function calls.
"""

from __future__ import annotations

from google.adk import Agent
from google.adk.models import Gemini
from google.genai import types

MODEL_ID = "gemini-3.7-flash"

# Insider knowledge the trip planner's mock inventory does not have. In a real
# deployment this would be a database owned by a local operations team.
LOCAL_TIPS = {
    "kandy": [
        "The Temple of the Sacred Tooth Relic has three daily pujas. The 18:30 one is the one to attend, and you need to be inside by 18:00 to get a view.",
        "Tuk tuk drivers around the lake quote roughly triple to tourists. Agree the fare before getting in, or ask the guesthouse to call one.",
        "Trains to Ella sell out days ahead in season. Second class reserved is the sweet spot, and it is booked at the station counter, not online.",
        "The Botanical Gardens are much quieter before 09:00, and the walk from the gate to the orchid house is longer than it looks.",
        "Shorts and bare shoulders are refused at the temple. A sarong can be rented at the entrance but the queue is slow.",
    ],
    "colombo": [
        "Pettah market is best before 10:00. After that it is heat and crowds.",
        "Metered tuk tuks exist and cost about half a negotiated fare. Look for the meter sticker.",
    ],
    "ella": [
        "Little Adams Peak at sunrise is genuinely quiet. Ella Rock at sunrise is not.",
        "The Nine Arch Bridge train times shift. Ask your guesthouse the night before rather than trusting a blog.",
    ],
}


def get_local_tips(city: str) -> dict:
    """Insider advice for a city from someone who lives there.

    Covers timing, transport, etiquette and the things that are not written down,
    which is exactly what a general search will not tell you.

    Args:
        city: City name, for example Kandy.

    Returns:
        A dict with "status" and a "tips" list of short pieces of advice.
    """
    tips = LOCAL_TIPS.get(city.strip().lower())
    if tips is None:
        return {
            "status": "error",
            "error_message": f"No local expert covers {city}. Covered: "
            + ", ".join(sorted(LOCAL_TIPS)),
        }
    return {"status": "success", "city": city, "tips": tips}


root_agent = Agent(
    name="local_expert",
    model=Gemini(
        model=MODEL_ID,
        retry_options=types.HttpRetryOptions(attempts=2, initial_delay=1),
    ),
    description=(
        "A local who actually lives at the destination. Answers questions about "
        "timing, transport, etiquette, queues and scams: the practical detail that "
        "is not in any listing or search result."
    ),
    instruction=(
        "You are a local expert. Someone is planning a trip and wants the things "
        "only a resident knows.\n"
        "\n"
        "Call get_local_tips with the city, then pass on the three or four that "
        "matter most for their plan, in your own words and in one line each.\n"
        "\n"
        "If the tool has no entry for that city, say plainly that you do not cover "
        "it. Do not improvise local knowledge, because someone will act on it."
    ),
    tools=[get_local_tips],
)
