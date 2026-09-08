# Day of the talk runbook

Everything that can go wrong here has already gone wrong once during the build.
This is the short version.

## The night before

```bash
pip install -r requirements.txt
pip install litellm                        # only if showing Phase 5
pip install "google-adk[a2a]" sse-starlette # only if showing Phase 7
python3 docs/check_models.py               # confirm the model ids still work
```

**Enable billing on the API key.** This is the one that will end the demo. See the
quota section below.

## Two hours before

```bash
python3 docs/check_models.py                     # ids can move overnight
python3 -m agents.p3_workflow.test_budget_loop   # offline, must pass
adk web agents                                   # all nine phases in the dropdown
```

If `check_models.py` shows your pinned id failing, change the three constants at
the top of `agents/p3_workflow/model.py` (and the same file in later phases) and
rerun. It is one edit per phase folder.

## The quota trap, stated plainly

The Gemini free tier allows **20 requests per day, per model**. One full Phase 3
pipeline run costs 10 to 15 model calls.

That means a free key gives you roughly **four full runs in a day, total**, across
the three model ids this repo spreads across. Rehearsing in the afternoon can leave
you with nothing for an evening slot, and the failure is a hard 429 rather than a
slow response.

**Enable billing.** Everything else in this runbook is a nicety. This is the one
that decides whether the demo happens.

## Running order

Spine, 20 to 25 minutes:

| Phase | Command | Beat |
| --- | --- | --- |
| 1 | `adk web agents`, pick `p1_delegation` | the `transfer_to_agent` event in the Events panel |
| 2 | `run_cli`, kill it, `show_state` | the trip is still on disk |
| 3 | `test_budget_loop`, then `run_pipeline` | offline proof, then the fan out and the loop in the trace |
| 6 | `run_booking reject` | nothing was charged |
| 8 | Events panel, then `adk eval` on one case | it looks like real software |

Flex, only if the room is fast: 4, 5, 7. Otherwise show the code on a slide and say
it is in the repo, which it is.

Deploy: pre recorded terminal or a live URL. Never a live build.

## When something breaks

| Symptom | Cause | Fix |
| --- | --- | --- |
| `429 RESOURCE_EXHAUSTED`, `PerDay` | daily quota gone for that model | switch the model id, or billing |
| `429`, `PerMinute` | 5 per minute burst | wait a minute, or spread across ids |
| `404 NOT_FOUND` on a model | closed to new keys | `python3 docs/check_models.py` |
| Five minute stall, no output | default retry budget | already bounded to 2 attempts in `model.py` |
| `the greenlet library is required` | greenlet missing | `pip install greenlet` |
| A script finishes but never exits | session service not closed | `await session_service.close()` |
| Weather tool times out | conference wifi | `USE_LIVE_WEATHER = False` in `weather.py` |
| A2A server dies at startup | `sse_starlette` missing | `pip install sse-starlette` |
| Phase 7 shows four researchers | expert service not running | `python3 -m local_expert_service.server` |

## Two slide accuracy guards

1. **Pin the model id and name it.** `gemini-2.5-flash` is 404 for new keys and
   still shows in `models.list()`. ADK 2.5's own default was 503 during this build.
   Say which id you actually tested on.
2. **Own the deprecation.** `SequentialAgent`, `ParallelAgent` and `LoopAgent` are
   deprecated in ADK 2.5 in favour of `Workflow`. Say it before the room does, then
   show `workflow_graph.py` and explain why the demo uses the classic ones anyway.

Also: `google-adk>=2.0.0`, demoed on 2.5.0, Python 3.10 or newer.
