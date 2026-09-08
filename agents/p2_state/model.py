"""The model, with a retry budget that will not eat your stage time.

Two things were learned the hard way while building this demo, both worth a slide.

**Availability is not what `models.list()` says.** `gemini-2.5-flash` still appears
in the listing and returns 404 NOT_FOUND on generation, because it is closed to new
API keys. Send one real request before you trust an id. `docs/check_models.py` does
exactly that.

**A transient 503 will hang you for five minutes.** The genai client retries with
tenacity and a generous default budget. During this build a `503 UNAVAILABLE, high
demand` on one model turned a single question into a five minute stall with no
output. On stage that reads as a crash. Bounding `attempts` turns it into a fast,
visible error you can talk over while you switch to the fallback id below.
"""

from __future__ import annotations

from google.adk.models import Gemini
from google.genai import types

# Verified working with function calling on 2026-09-08. See docs/MODELS.md.
MODEL_ID = "gemini-3.6-flash"

# If MODEL_ID starts returning 503 on the day, change this one line. 3.7 and 3.5
# were both healthy when 3.8 was overloaded, so the failures rotate.
FALLBACK_MODEL_ID = "gemini-3.7-flash"


def build_model(model_id: str = MODEL_ID) -> Gemini:
    """Return the demo model with a short, predictable retry budget."""
    return Gemini(
        model=model_id,
        retry_options=types.HttpRetryOptions(attempts=2, initial_delay=1),
    )
