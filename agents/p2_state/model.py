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

import os

from google.adk.models import Gemini
from google.genai import types

# Verified working with function calling on 2026-09-08. See docs/MODELS.md.
# Overridable from the environment, so a model that runs out of daily quota does
# not mean editing a file with an audience watching. `python3 docs/check_models.py
# --headroom` prints a ready to paste line.
MODEL_ID = os.environ.get("TRIP_PRIMARY_MODEL", "gemini-3.5-flash-lite")

# Bounding retry attempts is not enough. An overloaded model does not refuse
# quickly, it hangs: a 503 took 72 seconds to come back during this build, so two
# attempts plus backoff was a five minute stall with no output. The request
# timeout is what actually caps the damage.
TIMEOUT_MS = 25_000


def build_model(model_id: str = MODEL_ID) -> Gemini:
    """Return the demo model, bounded so it fails fast rather than hanging."""
    retry = types.HttpRetryOptions(attempts=2, initial_delay=1)
    return Gemini(
        model=model_id,
        retry_options=retry,
        # client_kwargs goes straight to the genai Client, which is the only way
        # to reach the request timeout from here.
        client_kwargs={
            "http_options": types.HttpOptions(
                timeout=TIMEOUT_MS, retry_options=retry
            )
        },
    )
