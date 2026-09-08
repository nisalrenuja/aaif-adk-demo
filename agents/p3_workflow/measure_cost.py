"""Run the pipeline and report exactly what it cost, in calls and in tokens.

    python3 -m agents.p3_workflow.measure_cost

Every event ADK emits carries `usage_metadata`, so the real number is available
without any guesswork. This adds it up per agent and per model, which answers the
two questions that actually matter before a talk:

  1. Can I afford this on the free tier today?  (calls per model vs 20 per day)
  2. What does it cost on a paid key?           (tokens, times the current rate)

It prints tokens rather than money on purpose. Per token prices change, and a
wrong number on a slide is worse than no number. Multiply by the current rate at
https://ai.google.dev/pricing and you have a figure you can defend.
"""

from __future__ import annotations

import asyncio
import collections
import sys
import warnings

warnings.filterwarnings("ignore")

from dotenv import load_dotenv
from google.genai import types

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from .agent import root_agent

APP_NAME = "cost_measurement"
USER_ID = "demo_traveller"
SESSION_ID = "measure"

# Free tier, per model, per day. The number that decides whether you can rehearse.
FREE_TIER_DAILY = 20


class Tally:
    """Calls and tokens, sliced by agent and by model."""

    def __init__(self) -> None:
        self.by_agent: dict[str, dict[str, int]] = collections.defaultdict(
            lambda: {"calls": 0, "input": 0, "output": 0, "thoughts": 0}
        )
        self.agent_model: dict[str, str] = {}

    def note_models(self, agent) -> None:
        """Record which model each agent runs on, walking the whole tree."""
        model = getattr(agent, "model", None)
        if model is not None:
            self.agent_model[agent.name] = getattr(model, "model", str(model))
        for child in getattr(agent, "sub_agents", []) or []:
            self.note_models(child)

    def add(self, author: str, usage) -> None:
        row = self.by_agent[author]
        row["calls"] += 1
        row["input"] += usage.prompt_token_count or 0
        row["output"] += usage.candidates_token_count or 0
        row["thoughts"] += usage.thoughts_token_count or 0

    def report(self) -> None:
        print("\n" + "=" * 78)
        print("  COST OF ONE FULL PIPELINE RUN")
        print("=" * 78)

        print(f"\n{'agent':24}{'model':30}{'calls':>7}{'in':>9}{'out':>8}")
        print("-" * 78)
        totals = {"calls": 0, "input": 0, "output": 0, "thoughts": 0}
        for agent, row in sorted(self.by_agent.items()):
            model = self.agent_model.get(agent, "?")
            print(f"{agent:24}{model:30}{row['calls']:>7}{row['input']:>9}{row['output']:>8}")
            for k in totals:
                totals[k] += row[k]

        print("-" * 78)
        print(f"{'TOTAL':24}{'':30}{totals['calls']:>7}{totals['input']:>9}{totals['output']:>8}")
        if totals["thoughts"]:
            print(f"\n  (plus {totals['thoughts']} thinking tokens, billed as output)")

        # Per model, which is what the free tier actually counts.
        per_model: dict[str, int] = collections.Counter()
        for agent, row in self.by_agent.items():
            per_model[self.agent_model.get(agent, "?")] += row["calls"]

        print(f"\n{'model':34}{'calls':>7}   free tier headroom (20/day)")
        print("-" * 78)
        for model, calls in sorted(per_model.items(), key=lambda kv: -kv[1]):
            runs = FREE_TIER_DAILY // calls if calls else 0
            warn = "  <-- tight" if runs <= 2 else ""
            print(f"{model:34}{calls:>7}   {runs} run(s) per day on this model{warn}")

        billable = totals["input"] + totals["output"] + totals["thoughts"]
        print(f"\n  {totals['calls']} model calls, {billable} billable tokens for one run.")
        print(f"  A talk that runs the pipeline twice costs about {billable * 2} tokens.")
        print("  Multiply by the current rate at https://ai.google.dev/pricing.")
        print("\n  Free tier verdict:", end=" ")
        worst = max(per_model.values()) if per_model else 0
        if worst == 0:
            print("no data")
        elif FREE_TIER_DAILY // worst >= 4:
            print(f"comfortable, about {FREE_TIER_DAILY // worst} runs a day.")
        elif FREE_TIER_DAILY // worst >= 2:
            print(f"workable but tight, about {FREE_TIER_DAILY // worst} runs a day.")
        else:
            print("do not rely on it. One run nearly exhausts a model for the day.")


async def main(request: str) -> None:
    load_dotenv()

    tally = Tally()
    tally.note_models(root_agent)

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        app_name=APP_NAME, agent=root_agent, session_service=session_service
    )

    content = types.Content(role="user", parts=[types.Part(text=request)])
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=content
    ):
        if event.usage_metadata is not None:
            tally.add(event.author, event.usage_metadata)
        for call in event.get_function_calls() or []:
            print(f"  [{event.author}] -> {call.name}")

    tally.report()


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or (
        "Plan me 3 days in Kandy, budget 250 USD, I like culture and food"
    )
    asyncio.run(main(prompt))
