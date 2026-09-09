"""Check which Gemini model ids you can actually run the demo on today.

Run this the morning of the talk.

    python3 docs/check_models.py              # fast, one request per model
    python3 docs/check_models.py --headroom   # slower, measures remaining quota

## Why this exists

Two traps, both hit during the build of this repo.

**`models.list()` lies.** `gemini-2.5-flash` still appears in the listing and
returns `404 NOT_FOUND, no longer available to new users` on generation. Listing a
model is not proof you can call it, so this script sends a real request with a real
tool declaration.

**Reachable is not the same as sufficient.** This is the trap the first version of
this script walked into. One successful request only proves a model has *at least
one* call left. The free tier allows 20 requests per day per model, and a single
Phase 3 pipeline run costs 10 to 15 calls spread over four model slots. A model
sitting on 1 remaining call reports green and then dies at the first agent with no
progress at all, which is exactly what happened here.

So the default mode is honest about what it does not know, and `--headroom`
measures the thing you actually care about.
"""

from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Ordered roughly by preference. The demo needs four distinct ids with headroom.
CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
]

# What one full Phase 3 pipeline run costs, per model slot, measured from real
# runs. The assembler is the expensive one: a hotel, one call per day, a summary,
# then all of it again if the budget loop takes a second pass.
SLOT_COST = {
    "TRIP_ASSEMBLER_MODEL": 10,
    "TRIP_PRIMARY_MODEL": 6,
    "TRIP_THIRD_MODEL": 5,
    "TRIP_SECOND_MODEL": 3,
}

# How many probe calls --headroom will spend per model before it stops counting.
# Enough to tell "plenty" from "nearly gone" without burning the thing you are
# trying to measure.
HEADROOM_CAP = 6

_DECLARATION = types.FunctionDeclaration(
    name="get_flights",
    description="Find flights between two airports.",
    parameters_json_schema={
        "type": "object",
        "properties": {"origin": {"type": "string"}, "dest": {"type": "string"}},
        "required": ["origin", "dest"],
    },
)


def _client() -> genai.Client:
    """A client that fails fast, so a 503 does not stall the check for minutes."""
    return genai.Client(
        http_options=types.HttpOptions(
            timeout=25_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        )
    )


def _classify(exc: Exception) -> tuple[str, str]:
    """Turn an exception into (status, human readable reason)."""
    text = str(exc)
    if "PerDay" in text:
        return "EXHAUSTED", "daily quota gone, resets at midnight Pacific"
    if "PerMinute" in text:
        return "RATE LIMITED", "per minute limit, wait about a minute"
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        return "EXHAUSTED", "quota exceeded"
    if "503" in text or "UNAVAILABLE" in text:
        return "OVERLOADED", "503, model is busy right now"
    if "404" in text or "NOT_FOUND" in text:
        return "UNAVAILABLE", "404, not available on this key"
    if "504" in text or "DEADLINE" in text:
        return "SLOW", "timed out after 25s"
    return "ERROR", text[:60]


def _probe(client: genai.Client, model: str) -> tuple[str, str, bool]:
    """One real request. Returns (status, reason, made_a_tool_call)."""
    try:
        response = client.models.generate_content(
            model=model,
            contents="Find flights from CMB to SIN",
            config=types.GenerateContentConfig(
                tools=[types.Tool(function_declarations=[_DECLARATION])]
            ),
        )
        parts = response.candidates[0].content.parts or []
        return "ok", "", any(p.function_call for p in parts)
    except Exception as exc:  # every failure mode here is interesting
        status, reason = _classify(exc)
        return status, reason, False


def _measure_headroom(client: genai.Client, model: str) -> tuple[int, bool, str]:
    """Spend up to HEADROOM_CAP calls.

    Returns (extra calls that succeeded, hit_the_cap, why_it_stopped).

    Why it stopped matters. Running out of quota means the count *is* the
    headroom. A 503 or a timeout means the model simply misbehaved partway
    through and the count tells you nothing about remaining quota. Reporting
    those two the same way would be the same class of mistake this script exists
    to correct.
    """
    for n in range(HEADROOM_CAP):
        status, _, _ = _probe(client, model)
        if status != "ok":
            return n, False, status
        time.sleep(0.4)  # stay clear of the 5 per minute burst limit
    return HEADROOM_CAP, True, "cap"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--headroom",
        action="store_true",
        help=(
            f"measure remaining quota by spending up to {HEADROOM_CAP} calls per "
            "model. Slower, and it consumes some of what it measures."
        ),
    )
    args = parser.parse_args()

    load_dotenv()
    client = _client()

    if args.headroom:
        print(
            f"Measuring headroom, up to {HEADROOM_CAP} calls per model. "
            "This consumes quota.\n"
        )
    else:
        print("Sending one request per model.\n")

    print(f"{'model':32}{'status':14}{'headroom':22}notes")
    print("-" * 96)

    # (model, calls confirmed available, whether the true number may be higher)
    usable: list[tuple[str, int, bool]] = []

    for model in CANDIDATES:
        started = time.time()
        status, reason, called_tool = _probe(client, model)
        elapsed = time.time() - started

        if status != "ok":
            print(f"{model:32}{status:14}{'0 calls left':22}{reason}")
            continue

        note = f"{elapsed:.1f}s" + ("" if called_tool else ", NO tool call")

        if args.headroom:
            extra, capped, why = _measure_headroom(client, model)
            total = 1 + extra
            if capped:
                headroom = f"at least {total}"
                usable.append((model, total, True))
            elif why in {"EXHAUSTED", "RATE LIMITED"}:
                headroom = f"exactly {total}"
                usable.append((model, total, False))
            else:
                headroom = f"{total}, then {why.lower()}"
                note += f", stopped by {why.lower()} not quota"
                usable.append((model, total, True))
        else:
            headroom = "unknown, at least 1"
            usable.append((model, 1, True))

        print(f"{model:32}{'reachable':14}{headroom:22}{note}")

    print()
    if not args.headroom:
        print("WARNING: 'reachable' only proves at least one call remains.")
        print("The free tier allows 20 requests per day per model, and one full")
        print("pipeline run costs 10 to 15 across four models. A model with a single")
        print("call left looks identical to a fresh one here. Use --headroom to tell")
        print("them apart, or enable billing and stop thinking about it.")
        print()

    _suggest(usable, measured=args.headroom)


def _suggest(usable: list[tuple[str, int, bool]], *, measured: bool) -> None:
    """Print an env line assigning the healthiest models to the hungriest slots."""
    if len(usable) < 4:
        print(f"Only {len(usable)} model(s) usable. A full pipeline run needs four")
        print("distinct ids with headroom. Enable billing, or wait for the daily")
        print("reset at midnight Pacific.")
        return

    ranked = sorted(usable, key=lambda item: -item[1])
    slots = sorted(SLOT_COST.items(), key=lambda item: -item[1])
    assignment = {slot: ranked[i][0] for i, (slot, _) in enumerate(slots)}
    counts = {model: (n, more) for model, n, more in usable}

    if measured:
        definitely_short, unknown = [], []
        for slot, cost in slots:
            model = assignment[slot]
            n, may_be_more = counts[model]
            if n >= cost:
                continue
            if may_be_more:
                unknown.append(f"{model} has at least {n}, the slot wants ~{cost}")
            else:
                definitely_short.append(f"{model} has {n}, the slot wants ~{cost}")

        if definitely_short:
            print("Not enough quota for a full run:")
            for line in definitely_short:
                print(f"  {line}")
            print()
        if unknown:
            print(f"Cannot confirm, probing stopped at the {HEADROOM_CAP} call cap:")
            for line in unknown:
                print(f"  {line}")
            print("  Raise HEADROOM_CAP to find out, at the cost of the quota it spends.")
            print()

    print("Suggested configuration, hungriest slot gets the healthiest model:")
    print()
    for slot, cost in slots:
        print(f"  {slot}={assignment[slot]}  (needs about {cost} calls)")
    print()
    env = " \\\n  ".join(f"{slot}={assignment[slot]}" for slot, _ in slots)
    print("Copy and paste:\n")
    print(f"  {env} \\\n  python3 -m agents.p3_workflow.run_pipeline "
          '"Plan me 3 days in Kandy, budget 250 USD"')


if __name__ == "__main__":
    main()
