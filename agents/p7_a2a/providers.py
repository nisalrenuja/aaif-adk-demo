"""Model diversity: not every agent in a pipeline wants the same model.

ADK talks to non Google models through LiteLLM, which is one wrapper class:

    from google.adk.models.lite_llm import LiteLlm
    Agent(model=LiteLlm(model="anthropic/claude-sonnet-4-5"), ...)

That is the whole integration. Same Agent, same tools, same state, same pipeline.

## The argument for mixing

The pipeline has two kinds of work in it, and they want different things.

**Structured lookups.** The four researchers call one tool, read a dict and emit a
line of summary. That work rewards being cheap and fast, and a small Gemini Flash
does it well. There are four of them and they run on every request, so they are
where the cost is.

**Composition.** The assembler balances a budget against interests, weather and
what is on in town. The presenter writes the thing a human actually reads. That is
judgement and prose, and it is worth spending a stronger model on. There are two of
them and they run once or twice.

Cheap where it is repeated, strong where it is read. That is the slide.

## Degrading gracefully

If no third party key is present, `build_creative_model()` returns a Gemini model
and says so. The demo keeps working on a machine that only has a Gemini key, which
matters because that is most machines, including possibly yours on the day.
"""

from __future__ import annotations

import os

from google.adk.models import Gemini
from google.genai import types

from .model import (
    ASSEMBLER_MODEL_ID,
    PRIMARY_MODEL_ID,
    SECOND_MODEL_ID,
    THIRD_MODEL_ID,
    build_model,
)

# LiteLLM model ids. Change these to match whatever key you actually hold.
# The prefix before the slash is the provider, and LiteLLM reads the matching
# environment variable itself: ANTHROPIC_API_KEY, OPENAI_API_KEY and so on.
ANTHROPIC_MODEL = "anthropic/claude-sonnet-4-5"
OPENAI_MODEL = "openai/gpt-4.1"


def creative_model_description() -> str:
    """One line naming what the creative agents will actually run on."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return f"{ANTHROPIC_MODEL} via LiteLLM"
    if os.environ.get("OPENAI_API_KEY"):
        return f"{OPENAI_MODEL} via LiteLLM"
    return f"{PRIMARY_MODEL_ID} (no third party key found, staying on Gemini)"


def build_creative_model():
    """Return the model for the composition agents.

    Prefers a third party model when a key for one is present, and falls back to
    Gemini when it is not, so the pipeline runs either way.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(model=ANTHROPIC_MODEL)

    if os.environ.get("OPENAI_API_KEY"):
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(model=OPENAI_MODEL)

    return build_model(PRIMARY_MODEL_ID)


def build_lookup_model(model_id: str = THIRD_MODEL_ID) -> Gemini:
    """Return the cheap, fast model used by the four researchers."""
    return Gemini(
        model=model_id,
        retry_options=types.HttpRetryOptions(attempts=2, initial_delay=1),
    )


__all__ = [
    "ANTHROPIC_MODEL",
    "ASSEMBLER_MODEL_ID",
    "OPENAI_MODEL",
    "PRIMARY_MODEL_ID",
    "SECOND_MODEL_ID",
    "THIRD_MODEL_ID",
    "build_creative_model",
    "build_lookup_model",
    "creative_model_description",
]
