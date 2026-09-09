# Trip Planner: a Google ADK live demo

A multi agent trip planner built in nine phases, one ADK concept per phase. Built
for a live talk, so every phase runs on mock data and never depends on a live third
party service to succeed.

![Architecture](docs/architecture.png)

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then paste a Gemini API key into it
adk web agents            # every phase shows up in the dropdown
```

Requires Python 3.10 or newer. Built and demoed on google-adk 2.5.0. The model
ids default to the lite tier and are overridable from the environment, because
model availability turned out to be the least predictable part of the whole build:
see [docs/MODELS.md](docs/MODELS.md).

**Before a live demo, enable billing on the API key.** The Gemini free tier allows
20 requests per day per model, and one full pipeline run costs 10 to 15. That is
about four runs a day, total. It is the single thing most likely to end the demo.
[docs/RUNBOOK.md](docs/RUNBOOK.md) has the rest.

## The phases

| Phase | Teaches | Folder |
| --- | --- | --- |
| 0 Seed | one Agent, one function tool | `agents/p0_seed` |
| 1 Delegation | sub agents and LLM routing | `agents/p1_delegation` |
| 2 State | session state and session services | `agents/p2_state` |
| 3 Workflow | Sequential, Parallel and Loop agents | `agents/p3_workflow` |
| 4 Tools | built in and third party tools | `agents/p4_tools` |
| 5 Models | LiteLLM, mixing model providers | `agents/p5_models` |
| 6 Safety | human in the loop confirmation | `agents/p6_safety` |
| 7 A2A | agent to agent over the wire | `agents/p7_a2a` |
| 8 Production | adk web, adk eval, adk deploy | `agents/p8_production` |

Each phase folder builds on the one before it and has its own README explaining
what changed and why. Every phase is present at once, so `adk web agents` lists
them all and you can step through them in order.

## Two extra files per phase

Alongside the agent, most phases ship something you can run **without spending a
model call**, because the best demo is one that cannot flake:

| Phase | Zero cost prop |
| --- | --- |
| 0 | `inspect_tool.py` prints the declaration ADK generated from a docstring |
| 2 | `show_state.py` reads the trip back out of SQLite |
| 3 | `test_budget_loop.py` asserts the loop's exit condition offline |
| 5 | `show_models.py` prints which model every agent runs on |
| 6 | `run_booking.py` drives the approval gate for two or three calls, not fifteen |

One more, which does spend quota because it has to: `measure_cost.py` runs the
pipeline and reports exactly what it cost in calls and tokens, per agent and per
model, read from ADK's own `usage_metadata`. Available from Phase 3 onward.

## What each file is

Every phase folder is self contained, so the same filenames recur as the project
grows. What they mean:

| File | Role | From |
| --- | --- | --- |
| `agent.py` | the agents and how they are wired. `root_agent` lives here | phase 0 |
| `mock_data.py` | fake inventory, so nothing depends on wifi | phase 0 |
| `tools.py` | the function tools | phase 1 |
| `model.py` | model ids, retry budget and request timeout | phase 2 |
| `session_services.py` | where state is stored, the one line swap | phase 2 |
| `workflow_graph.py` | the same pipeline on ADK 2.5's newer graph runtime | phase 3 |
| `resilience.py` | keeps one failing agent from cancelling the parallel fan out | phase 3 |
| `_runner.py` | shared plumbing for the run scripts | phase 3 |
| `weather.py` | the OpenAPI toolset, with a cached offline fallback | phase 4 |
| `providers.py` | picks the third party model when a key is present | phase 5 |
| `booking.py` | `book_trip` and its confirmation gate | phase 6 |
| `remote.py` | the client half of A2A | phase 7 |
| `*.evalset.json`, `test_config.json` | the regression suite | phase 8 |

Scripts you can run directly, all `python3 -m agents.<phase>.<name>`:

| Script | Does |
| --- | --- |
| `inspect_tool` | prints the declaration ADK generated from a docstring |
| `show_state` | reads the trip back out of SQLite |
| `run_cli` | talks to the concierge against the persistent session |
| `run_pipeline` / `run_graph` | runs the pipeline on each of the two runtimes |
| `test_budget_loop` | asserts the loop's exit condition, offline |
| `show_models` | prints which model every agent runs on |
| `run_booking` | drives the approval gate, `approve` or `reject` |
| `measure_cost` | runs the pipeline and reports calls and tokens |

## Docs

| File | What it is |
| --- | --- |
| [docs/PLAN.md](docs/PLAN.md) | the build plan, verified environment and per phase third party cost |
| [docs/MODELS.md](docs/MODELS.md) | which model ids actually work, and the quota walls |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | day of the talk checklist and the failure table |
| [docs/check_models.py](docs/check_models.py) | which model ids work and how much quota is left; run `--headroom` the morning of |

## Findings worth a slide

Things this build ran into that are not in the getting started guide:

- `gemini-2.5-flash` returns **404 for new API keys** while still appearing in
  `models.list()`. Listing a model is not proof you can call it.
- The free tier is **20 requests per day, per model**, not just 5 per minute.
- `SequentialAgent`, `ParallelAgent` and `LoopAgent` are **deprecated in ADK 2.5**
  in favour of `Workflow`. Phase 3 ships both so the slide can be accurate.
- `DatabaseSessionService` needs `greenlet`, which nothing pulls in, and needs
  `await service.close()` or your script finishes and never exits.
- The `[a2a]` extra does not pull in `sse-starlette`, and the server dies at
  startup without it.
- A transient 503 with the default retry budget stalls for five minutes with no
  output. Every agent here bounds it to two attempts.
