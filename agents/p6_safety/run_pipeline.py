"""Run the classic pipeline: SequentialAgent wrapping ParallelAgent and LoopAgent.

    python3 -m agents.p3_workflow.run_pipeline "Plan me 3 days in Kandy, budget 250"

Watch the three researchers report in together, then the assemble and check pair
repeat until the total fits.
"""

from __future__ import annotations

import asyncio
import sys

from ._runner import run
from .agent import root_agent

if __name__ == "__main__":
    request = " ".join(sys.argv[1:]) or "Plan me 3 days in Kandy, budget 250 USD, I like culture and food"
    asyncio.run(run(request, agent=root_agent))
