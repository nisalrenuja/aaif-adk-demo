"""Make the assembler's single pass a property of the code, not a request in prose.

## The instruction this replaces

`itinerary_assembler` is told, in its instruction:

    Make exactly one pass and then stop. One choose_hotel call, one
    set_itinerary_day call per day, then report. Do not re-check your own
    arithmetic and do not revise a choice you already made in this pass.

That sentence is load bearing and it is also just a sentence. A model having a bad
day re-picks the hotel, re-sets day 1 "to be sure", and the pass that was supposed
to cost four calls costs nine. Nothing stops it. The instruction is the only thing
standing between the demo and a quota wall.

This module is that sentence expressed as an invariant instead: within one turn of
the assembler, `choose_hotel` runs at most once and `set_itinerary_day` runs at
most once per day. A second attempt does not reach the tool body at all.

## What this actually buys, stated honestly

It does **not** make the extra model call disappear. By the time a callback fires,
the model has already been invoked and has already asked for the tool. What it
guarantees is narrower and more useful:

- The plan **cannot** be rewritten halfway through a pass. Whatever the first
  `choose_hotel` picked is what the budget check totals, so the number on stage and
  the number in `test_budget_loop.py` come from the same arithmetic.
- The refusal is a tool result the model reads, and it says what to do next, so a
  second attempt converges instead of repeating.

Cost is bounded, not eliminated. The honest version of the slide is "the framework
makes the wrong behaviour impossible", not "the framework makes it free".

## Why the ledger is scoped the way it is

A `LoopAgent` runs the assembler again on the next iteration, and that pass *must*
be able to pick a cheaper hotel: that is the whole refinement mechanism. So the
ledger cannot be per invocation, or the second pass could never cut anything.

`before_agent_callback` clears it at the start of every assembler turn, which is
exactly one pass. The key uses ADK's `temp:` prefix, which lives in the in-memory
session for the duration of the invocation and is trimmed before anything is
persisted, so this bookkeeping never lands in your SQLite session file.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import BaseTool, ToolContext

# `temp:` is ADK's invocation scoped prefix. Applied to the in-memory session so
# later steps in the same run can read it, trimmed from the event delta so it is
# never written to storage. See google.adk.sessions.base_session_service.
LEDGER_KEY = "temp:assembler_pass_calls"

# One call each per pass. `set_itinerary_day` is keyed by day, because one call per
# day of the trip is correct and a second call for a day already set is the
# re-check the instruction was trying to prevent.
ONCE_PER_PASS = "choose_hotel"
ONCE_PER_DAY = "set_itinerary_day"


def start_new_pass(callback_context: CallbackContext) -> None:
    """Clear the ledger. Attach as the assembler's `before_agent_callback`.

    Returning nothing lets the agent run normally. Returning content here would
    skip the agent entirely, which is not what we want.
    """
    callback_context.state[LEDGER_KEY] = {}


def _ledger_key(tool_name: str, args: dict[str, Any]) -> str | None:
    """What this call counts against, or None if the tool is not rationed."""
    if tool_name == ONCE_PER_PASS:
        return tool_name
    if tool_name == ONCE_PER_DAY:
        return f"{tool_name}:{args.get('day')}"
    return None


def enforce_one_pass(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict | None:
    """Refuse a repeat call within the same pass. Attach as `before_tool_callback`.

    ADK calls this by keyword, so the parameter names are part of the contract.
    Returning None lets the tool run. Returning a dict short circuits it and hands
    that dict back to the model as the tool's result.
    """
    key = _ledger_key(tool.name, args)
    if key is None:
        return None

    ledger = dict(tool_context.state.get(LEDGER_KEY, {}))
    if key in ledger:
        # Already done this pass. Say what happened and what to do instead, so the
        # model moves on rather than trying a third time.
        return {
            "status": "skipped",
            "reason": (
                f"{tool.name} already ran in this pass and the result is recorded. "
                "One pass sets each thing once. Do not call it again."
            ),
            "next_step": (
                "Report the plan you have. The budget check runs after you and it "
                "is the only thing that decides whether the plan is affordable. If "
                "it comes back over budget you get another pass to cut."
            ),
            "recorded_this_pass": sorted(ledger),
        }

    ledger[key] = True
    tool_context.state[LEDGER_KEY] = ledger
    return None
