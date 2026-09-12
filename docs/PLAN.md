# ADK Live Demo: Build Plan

A nine phase build of a multi agent trip planner using Google ADK. Every phase adds
one ADK concept, and all nine live side by side, so the repo doubles as a reference
after the talk.

## Verified environment

Checked on this machine before writing a line of code:

| Item | Value |
| --- | --- |
| Python | 3.12.2 |
| google-adk | 2.5.0 |
| adk CLI | present (`web`, `eval`, `deploy`, `run`, `api_server`) |
| sqlalchemy | 2.0.39 (so `DatabaseSessionService` works) |
| litellm | not installed (Phase 5 installs it) |
| a2a-sdk | not installed (Phase 7 installs it) |
| gcloud | not installed (Phase 8 deploy needs it) |
| API key | not set (see Blockers) |

## Blockers and third party involvement

### Hard blocker, resolved: an API key

Nothing that talks to a model runs without a Gemini API key. A key was supplied
during the build and `.env` is in place (gitignored). Verified working.

### Hard blocker, still open: free tier quota

The free tier allows **20 requests per day, per model**, and one Phase 3 pipeline
run costs 17 model calls, measured. That is roughly three full runs a day across
the four model ids this repo uses, and it was hit repeatedly while building.

**Enable billing on the key before the talk.** This is the one remaining thing that
can end the demo, and no amount of code works around it. Full detail in
[MODELS.md](MODELS.md).

### Third party by phase

| Phase | Third party | Cost | Offline fallback |
| --- | --- | --- | --- |
| 0 Seed | Gemini API | free tier | none, needs the key |
| 1 Delegation | Gemini API | free tier | none |
| 2 State | Gemini API, local SQLite file | free | SQLite is local |
| 3 Workflow | Gemini API | free | none |
| 4 Rich tools | `google_search` (same key), open-meteo OpenAPI (no key) | free | cached JSON fixture |
| 5 LiteLLM | `litellm` package plus an Anthropic or OpenAI key | small paid | skip, show code on slide |
| 6 Safety | Gemini API | free | none |
| 7 A2A | `a2a-sdk`, two local processes | free | both processes are local |
| 8 Production | `adk web` and `adk eval` are free. `adk deploy cloud_run` needs a GCP project with billing and the gcloud CLI | billing | pre recorded terminal plus a live URL |

### Known sharp edges, already verified

1. **Workflow agents are deprecated in ADK 2.5.0.** `SequentialAgent`, `ParallelAgent`
   and `LoopAgent` each emit `DeprecationWarning: ... deprecated in favor of Workflow`.
   They still run correctly. Phase 3 therefore ships both: `agent.py` uses the three
   classic primitives because they teach the concept most clearly, and
   `workflow_graph.py` builds the same pipeline on the new graph runtime. The slide
   says which is which. Warnings are silenced in the phase package so the terminal
   stays clean on stage.
2. **`Workflow` cannot yet be an `LlmAgent` sub agent.** So the graph variant is a
   separate root, not a swap inside the concierge.
3. **ADK 2.5.0 defaults to `gemini-3.5-flash`.** Every agent names its model
   explicitly through one constants module, so a single edit changes all of them. The
   shipped defaults are the lite tier, `gemini-3.5-flash-lite` and friends, spread
   across four ids because the free quota is per model. The slide names them.
4. **Built in tools do not mix cleanly, and it only shows at request time.** An
   agent holding `google_search` alongside function tools constructs fine and then
   fails the first real call with `400 INVALID_ARGUMENT: Please enable
   tool_config.include_server_side_tool_invocations`. Setting that in the agent's
   `generate_content_config` fixes it. No AgentTool wrapper is needed, but "verified
   by construction" was not verification: only a real request proves this.

## Repo layout

```
agents/                 the adk web agents directory
  p0_seed/
    __init__.py
    agent.py            root_agent lives here
    mock_data.py        self contained fake data
    inspect_tool.py     prints the generated tool declaration
    README.md           what this phase teaches
  p1_delegation/ ... p8_production/
local_expert_service/   the A2A service, its own process (phase 7)
docs/
  PLAN.md               this file
  MODELS.md             which model ids work, and the quota walls
  RUNBOOK.md            day of the talk checklist
  check_models.py       verifies model ids and remaining quota
README.md
requirements.txt
pyproject.toml          ruff configuration
.env.example
```

Each phase package is deliberately self contained, duplicated mock data included.
A person can copy one folder out of the repo and it runs. That matters more for a
teaching repo than avoiding duplication.

Run every phase with a single command from the repo root:

```
adk web agents
```

The dropdown lists all phases, which makes the "watch it grow" story easy to tell.

## Stage plan

Spine, about 20 to 25 minutes: phases 1, 2, 3, 6, 8.
Flex, only if the room is fast: phases 4, 5, 7. Otherwise flash the code on a slide
and say it is in the repo.
Deploy: show a pre recorded terminal or a live URL, never wait on a build.

## Slide accuracy guards

- Pin `google-adk>=2.0.0`, and say you demoed on 2.5.0.
- Name the exact model ids shipped as defaults, `gemini-3.5-flash-lite`,
  `gemini-3.1-flash-lite`, `gemini-3.1-flash-lite-preview` and
  `gemini-3-flash-preview`, never an alias.
- Say Python 3.10 or newer.
- State that the workflow agents are deprecated as of 2.5 and that `Workflow` is the
  forward path. Owning that beats being corrected from the audience.


## What changed once the code was written

The plan above survived contact, with four additions that were not foreseeable from
the docs.

**Model availability was the biggest surprise.** The pin moved from
`gemini-2.5-flash` to `gemini-3.6-flash` after the first real request came back
404, and then down to the lite tier, `gemini-3.5-flash-lite` and friends, once a
full run proved they handle this work. `docs/MODELS.md` and `docs/check_models.py`
exist entirely because of this.

**Quota shaped the architecture.** The parallel researchers point at different
model ids, and the assembler gets its own, because the free quota is counted per
model. That started as a
workaround and turned into a genuine argument for Phase 5.

**Every phase gained something runnable without a model call.** `inspect_tool.py`,
`show_state.py`, `test_budget_loop.py`, `show_models.py` and the seeded
`run_booking.py`. On a quota limited key these are what make the talk safe, and
they happen to be better teaching than a live run anyway.

**Three undocumented dependency gaps.** `greenlet` for the SQLite session service,
`sse-starlette` for the A2A server, and `await service.close()` or scripts hang
after finishing. All three cost real time and all three are now in
`requirements.txt` or a README.

## What is verified and what is not

| Phase | Live verified |
| --- | --- |
| 0 Seed | tool declaration generation, offline |
| 1 Delegation | structure loads; routing not run live |
| 2 State | full run, both processes, SQLite persistence across restart |
| 3 Workflow | full pipeline end to end, loop fires and cuts; exit condition also proven offline |
| 4 Tools | OpenAPI weather end to end with live data; `google_search` not run live |
| 5 Models | fallback path only, no third party key was available |
| 6 Safety | both approve and reject paths, end to end |
| 7 A2A | server, agent card and remote call end to end, plus the fallback |
| 8 Production | `adk web` loads all nine phases and serves them; `adk eval` passes; deploy not executed |

Every gap is stated in the relevant phase README rather than left implicit.
