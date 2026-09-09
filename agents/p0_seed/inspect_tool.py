"""Print the function declaration ADK generates from get_flights.

Run this on stage right after showing the Python function. It proves the claim
that the docstring is the contract the model sees, with nothing else involved.

    python3 -m agents.p0_seed.inspect_tool
"""

from __future__ import annotations

import json
import warnings

from google.adk.tools import FunctionTool

from .agent import get_flights

warnings.filterwarnings("ignore", message=r".*EXPERIMENTAL.*")


def main() -> None:
    """Print the declaration ADK generated from the get_flights docstring."""
    declaration = FunctionTool(func=get_flights)._get_declaration()
    print(json.dumps(declaration.model_dump(exclude_none=True), indent=2))


if __name__ == "__main__":
    main()
