"""Models for the pipeline, spread deliberately across ids.

Two reasons this file is not just a string constant.

**Bounded retries.** A transient 503 with the default retry budget turned one
question into a five minute stall during this build. `attempts=2` makes a failure
visible in seconds instead.

**Quota headroom.** The free tier allows 5 requests per minute *per model*. A
parallel fan out fires three agents at once, and a refinement loop fires several
more, so a single pipeline run is 17 calls, measured. Pointing the three
researchers at three different model ids roughly triples the free tier headroom,
because the quota is counted per model.

That is a workaround, and it is also a real technique. Phase 5 makes the same
argument for a better reason: different jobs genuinely want different models.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.models import Gemini
from google.genai import types

# `docs/check_models.py --write` puts the morning's healthy model ids in this file.
# Loading it here is what closes the loop: the script that finds out which ids still
# have quota and the agents that run on them stop being connected by a human
# correctly pasting four environment variables ten minutes before a talk.
#
# `override=False` on purpose. A variable already set in the environment wins, so
#
#     TRIP_ASSEMBLER_MODEL=gemini-3.8-flash python3 -m agents.p3_workflow.run_pipeline
#
# still does what it looks like it does. The file is a default, not an override.
#
# Checked in the working directory first and then at the repo root, so it works
# both when run from the repo and when a phase folder has been copied out on its
# own. A missing file is a no op, which is the normal case.
_ENV_FILE = ".env.models"
for _candidate in (Path.cwd() / _ENV_FILE, Path(__file__).resolve().parents[2] / _ENV_FILE):
    if _candidate.is_file():
        load_dotenv(_candidate, override=False)
        break

# All three verified working with function calling. See docs/MODELS.md.
#
# Overridable from the environment, because the free tier's daily quota is per
# model and burns out per model. When one id starts returning 429 PerDay, you do
# not want to be editing six files with an audience watching:
#
#     TRIP_PRIMARY_MODEL=gemini-3.8-flash python3 -m agents.p3_workflow.run_pipeline "..."
#
# `python3 docs/check_models.py` tells you which ids still have headroom.
# Lite tier by default. These are the cheapest ids that still handle this work,
# and a full run was verified end to end on them, loop and all. Nothing here needs
# a large model: the agents call one tool and summarise a dict. Swap upward with
# the environment variables below if you find a step that genuinely struggles.
PRIMARY_MODEL_ID = os.environ.get("TRIP_PRIMARY_MODEL", "gemini-3.5-flash-lite")
SECOND_MODEL_ID = os.environ.get("TRIP_SECOND_MODEL", "gemini-3.1-flash-lite")
THIRD_MODEL_ID = os.environ.get("TRIP_THIRD_MODEL", "gemini-3.1-flash-lite-preview")

# The assembler runs inside the refinement loop and makes the most calls of any
# agent here: choose a hotel, then one call per day, then a summary, then possibly
# all of that again on the next pass. That is comfortably more than 5 requests in a
# minute, which is the free tier's per minute limit for a single model, so on a
# free key it rate limits itself even when nothing else is running.
#
# It therefore gets its own id when you give it one. Defaults to sharing SECOND,
# which is the right default on a paid key where none of this matters.
ASSEMBLER_MODEL_ID = os.environ.get(
    "TRIP_ASSEMBLER_MODEL", "gemini-3-flash-preview"
)


# Bounding retry *attempts* is not enough. An overloaded model does not refuse
# quickly, it hangs: a 503 on gemini-3.8-flash took 72 seconds to come back during
# this build, so two attempts plus backoff was a five minute stall with no output.
# A request timeout is what actually caps the damage. 25 seconds is generous for a
# Flash model and short enough to notice on stage.
TIMEOUT_MS = 25_000


def build_model(model_id: str = PRIMARY_MODEL_ID) -> Gemini:
    """Return a Gemini model that fails fast rather than hanging.

    Two guards, and you need both:

    - `attempts=2` so a transient failure is retried once and then given up on.
    - `timeout` so a single attempt cannot hang for over a minute on its own.
    """
    retry = types.HttpRetryOptions(attempts=2, initial_delay=1)
    return Gemini(
        model=model_id,
        retry_options=retry,
        # client_kwargs is passed straight to the genai Client, which is the only
        # way to reach the request timeout from here.
        client_kwargs={
            "http_options": types.HttpOptions(
                timeout=TIMEOUT_MS, retry_options=retry
            )
        },
    )
