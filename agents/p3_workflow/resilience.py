"""Keep one flaky model call from taking down the whole fan out.

## The failure this fixes

`ParallelAgent` runs its sub agents in an `asyncio.TaskGroup`. A TaskGroup cancels
its siblings when any task raises. So a single transient `503 UNAVAILABLE, this
model is currently experiencing high demand` on one researcher does not degrade the
pipeline, it kills it, and the traceback you get is an `ExceptionGroup` that buries
the one line that actually mattered.

This happened during the build, mid run, with three of four researchers already
finished. It is exactly the failure that shows up on stage.

## The fix

`on_model_error_callback` fires when a model call fails. Return an `LlmResponse`
and ADK treats the error as handled: the agent produces that response instead of
raising, its siblings finish, and the pipeline carries on with one shortlist
missing rather than nothing at all.

## Why this is the right shape, not just a try block

Research is best effort. A trip plan missing a flight shortlist is worse than one
with it, and far better than no trip plan. The degraded response says plainly what
is missing, so the assembler and the presenter can be honest about it downstream
rather than quietly pretending the data was never wanted.

Whether a step is best effort or load bearing is a design decision. `check_budget`
is load bearing, and it deliberately has no such callback: if the budget cannot be
computed, failing loudly is correct.
"""

from __future__ import annotations

import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types


def _short_reason(error: Exception) -> str:
    """A human sized description of what went wrong.

    The fallback matters as much as the named cases. An earlier version returned
    just `type(error).__name__` here, so a real misconfiguration surfaced in the
    trace as the useless word "ClientError" and looked like a flake. Anything not
    recognised now carries the API's own message, truncated.
    """
    text = str(error)
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        return "the model's quota was exhausted"
    if "UNAVAILABLE" in text or "503" in text:
        return "the model was temporarily overloaded"
    if "404" in text or "NOT_FOUND" in text:
        return "the model id is not available on this key"
    if "DEADLINE" in text or "504" in text:
        return "the request timed out"

    # Surface the API's message rather than the exception class name.
    match = re.search(r"'message':\s*'([^']+)'", text)
    detail = match.group(1) if match else text.replace("\n", " ")
    return f"{type(error).__name__}: {detail[:160]}"


def degrade_gracefully(
    callback_context: CallbackContext,
    llm_request: LlmRequest,  # noqa: ARG001  ADK calls this by keyword
    error: Exception,
) -> LlmResponse:
    """Turn a failed model call into an honest, empty result.

    Attached to the researchers, whose work is best effort. Returning an
    LlmResponse marks the error handled, so the sibling agents in the parallel
    fan out are not cancelled with it.
    """
    agent_name = callback_context.agent_name
    reason = _short_reason(error)

    # Leave a breadcrumb in state so later steps, and you, can see what was lost.
    failures = list(callback_context.state.get("degraded_agents", []))
    failures.append({"agent": agent_name, "reason": reason})
    callback_context.state["degraded_agents"] = failures

    message = (
        f"{agent_name} could not complete because {reason}. "
        "No results are available from this step."
    )
    print(f"  [!] {message}")

    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=message)])
    )
