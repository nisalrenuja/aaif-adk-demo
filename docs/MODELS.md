# Model choice, and why this exact id

Tested on 2026-09-08 against the demo API key. This page exists because model
availability turned out to be the least predictable part of the whole build.

## What we pin

```python
MODEL = "gemini-3.6-flash"
```

## What we found when we actually called the API

| Model id | Result |
| --- | --- |
| `gemini-2.5-flash` | **404 NOT_FOUND.** "This model is no longer available to new users." It still appears in `models.list()`, which makes this trap easy to walk into. |
| `gemini-2.5-flash-lite` | 404, same reason |
| `gemini-3.5-flash` | **503 UNAVAILABLE**, model overloaded. This is ADK 2.5's own built in default, which is worth knowing before a live demo leans on it |
| `gemini-3.6-flash` | works, including function calling |
| `gemini-3.7-flash` | works, including function calling |
| `gemini-3.8-flash` | works, including function calling |
| `gemini-flash-latest` | works, but it is an alias and aliases move |

## The three lessons for the slide

1. **`models.list()` lies.** `gemini-2.5-flash` is listed and still 404s on
   generation. Listing a model is not proof you can call it. Always send one real
   request before you trust an id.
2. **Do not rely on the framework default.** ADK 2.5 defaults to
   `gemini-3.5-flash`, which was returning 503 during this build. Every agent in
   this repo names its model explicitly.
3. **Do not put an alias on a slide.** `gemini-flash-latest` works today and means
   something different next month. Pin the number.

## Re-checking before the talk

```bash
python3 docs/check_models.py              # fast: is each id reachable at all
python3 docs/check_models.py --headroom   # slower: how many calls are actually left
```

Run this the morning of the talk. It sends a real tool calling request per
candidate id, so a model that quietly moved overnight shows up before the room
does.

**Use `--headroom` on the day.** A single successful request only proves a model
has at least one call remaining, and a model with one call left is
indistinguishable from a fresh one in the fast mode. That is not a hypothetical:
it cost a rehearsal here, where every id reported reachable and the run then died
at the very first agent with zero progress because the daily quota was already
spent.

`--headroom` measures what is actually left, distinguishes running out of quota
from a model merely misbehaving mid probe, and prints a ready to paste environment
line assigning the healthiest models to the hungriest slots.

## The quota wall, and why it shapes Phase 3 onward

The free tier has **two** separate limits, and the second one is the dangerous one.
Both were hit during this build:

| Quota id | Limit | What it means |
| --- | --- | --- |
| `GenerateRequestsPerMinutePerProjectPerModel-FreeTier` | 5 | 5 requests a minute, per model |
| `GenerateRequestsPerDayPerProjectPerModel-FreeTier` | 20 | **20 requests a day, per model** |

The per day limit is the one that ends a rehearsal. A single Phase 3 pipeline run
costs 10 to 15 model calls, so on a free key you get roughly **one and a half full
runs per model, per day**. Spread across the three model ids this repo uses, that is
about four runs in total before everything is exhausted until the quota resets.

The error names which limit you hit, so read the `quotaId`, not just the number:

```
429 RESOURCE_EXHAUSTED. Quota exceeded for metric:
generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 20, model: gemini-3.6-flash
quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
```

That number is small enough to change the architecture. Count the model calls in a
single "plan me 3 days in Kandy" on a free key:

| Step | Calls |
| --- | --- |
| concierge decides and saves preferences | 2 |
| transfer, then the specialist answers | 2 |
| each further specialist | 2 each |
| a Phase 3 parallel fan out across three researchers | 3 at once |
| a Phase 3 refinement loop, per iteration | 2 or more |

One full pipeline run is comfortably 10 to 15 calls. At 5 per minute the run stalls
part way through and the demo dies in front of the room.

### Three ways out, in order of preference

1. **Enable billing on the API key. For a live talk this is not optional.** At 20
   requests per model per day, a free key gives you roughly four full pipeline runs
   before it stops working, and it stops working for the rest of the day rather
   than for the next minute. Rehearsing in the afternoon can leave you with nothing
   left for the evening slot. Paid tier limits are far above anything this demo
   does and the spend for a rehearsal plus a talk is small.
2. **Spread agents across different model ids.** The quota is per model, so pointing
   the three parallel researchers at `gemini-3.6-flash`, `gemini-3.7-flash` and
   `gemini-3.5-flash` roughly triples the headroom for free. This repo does that in
   Phase 3 by default. It is a workaround, but it is also a real technique, and it
   sets up the Phase 5 argument that different agents want different models.
3. **Rehearse phase by phase, not end to end.** Wait a minute between runs. Fine for
   building, not something to rely on with an audience watching.

### The bounded retry lesson

The genai client retries with a generous default budget. A transient 503 during this
build turned one question into a five minute stall with no output, which on stage
reads as a crash. Every agent from Phase 2 on is built through `build_model()`,
which sets `retry_options=HttpRetryOptions(attempts=2, initial_delay=1)` so a
failure surfaces in seconds and you can talk over it.
