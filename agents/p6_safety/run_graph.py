"""Run the same pipeline on the graph runtime.

    python3 -m agents.p3_workflow.run_graph "Plan me 3 days in Kandy, budget 250"

The only difference from run_pipeline.py is `node=` instead of `agent=`. Same
tools, same state, same result, one fewer model call per refinement pass because
the budget gate is a plain function rather than an agent.
"""

from __future__ import annotations

import asyncio
import sys

from ._runner import run
from .workflow_graph import root_agent

if __name__ == "__main__":
    request = " ".join(sys.argv[1:]) or (
        "Plan me 3 days in Kandy, budget 250 USD, I like culture and food"
    )
    asyncio.run(run(request, node=root_agent))
