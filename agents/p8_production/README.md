# Phase 8: Production

**Branch:** `phase-8-production`
**Teaches:** `adk web`, `adk eval`, `adk deploy cloud_run`.
**Stage status:** spine for `adk web` and `adk eval`. Deploy is a recording or a
pre deployed URL, never a live build.

## The one idea

Everything so far has been code. This phase is the three things that turn it into
something a team can operate: **see it**, **test it**, **ship it**.

## See it: `adk web`

```bash
adk web agents
```

Every phase appears in the dropdown, so the whole talk is one server:

```
p0_seed  p1_delegation  p2_state  p3_workflow  p4_tools
p5_models  p6_safety  p7_a2a  p8_production
```

Open the **Events** panel and run the pipeline. This is the highest ratio of impact
to effort in the entire talk: the parallel fan out draws itself as overlapping
spans rather than a staircase, and the refinement loop visibly repeats until the
total drops under budget. You wrote no instrumentation to get that.

Add persistence with the flag from Phase 2:

```bash
adk web agents --session_service_uri="sqlite:///./trip.db"
```

## Test it: `adk eval`

```bash
adk eval agents/p8_production agents/p8_production/trip_planning.evalset.json \
    --config_file_path agents/p8_production/test_config.json \
    --print_detailed_results
```

Two cases in `trip_planning.evalset.json`, and what they assert is the **tool
trajectory**, not the prose:

| Case | Pins |
| --- | --- |
| `kandy_tight_budget` | preferences are recorded before anything is researched, and the budget is actually checked |
| `colombo_comfortable_budget` | the same shape holds for a different city and a budget that fits on the first pass |

`test_config.json` sets the thresholds:

```json
{"criteria": {"tool_trajectory_avg_score": 0.6, "response_match_score": 0.2}}
```

**Assert trajectory, not wording.** The final response of an LLM pipeline varies
between runs and always will. What must not vary is that `save_preferences` runs
before `research_activities`, and that `check_budget` runs at all. A test suite
that asserts prose is a test suite your team will delete within a month.

That is why `response_match_score` is set low. It is there to catch an agent that
has stopped answering the question, not to demand identical sentences.

Run one case rather than all of them:

```bash
adk eval agents/p8_production \
    "agents/p8_production/trip_planning.evalset.json:kandy_tight_budget"
```

**Cost warning.** Each case runs the whole pipeline, so the full eval set is
roughly 30 model calls. On a free key that exceeds the daily quota on its own. Use
the single case form while rehearsing. See [docs/MODELS.md](../../docs/MODELS.md).

## Ship it: `adk deploy cloud_run`

```bash
adk deploy cloud_run \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --region=us-central1 \
    --service_name=trip-planner \
    --with_ui \
    agents/p8_production
```

`--with_ui` ships the same web interface you have been demoing, so the deployed
thing is the thing the room just watched.

**Do not run this live.** It builds a container and waits on Cloud Build. Record
the terminal beforehand, or deploy in advance and open the URL. A progress bar is
not a demo.

Flags worth knowing:

| Flag | Why |
| --- | --- |
| `--with_ui` | ships the web UI, not just the API |
| `--session_service_uri` | point at a real database instead of in memory, the Phase 2 swap again |
| `--trace_to_cloud` | the Events panel view, in Cloud Trace |
| `--a2a` | expose the A2A endpoint, the Phase 7 story in production |

There is also `adk deploy agent_engine` and `adk deploy gke` for the same agent.

## What deploy actually needs

This is the only phase with real third party cost, so be honest about it on the
slide:

- a Google Cloud project with **billing enabled**
- the **gcloud CLI** installed and authenticated (`gcloud auth login`). It was not
  installed on the machine this was built on, which is worth checking before you
  are standing up
- Cloud Run and Cloud Build APIs enabled on the project

Everything else in these eight phases runs on a free key and a laptop.

## Verified, and not verified

**Verified.** `adk web agents` starts and loads all nine phases; `list-apps`
returns every one and each root agent instantiates. The eval set and the config
both validate against ADK's own schemas.

**Not verified.** The eval set has not been executed, because a full run exceeds
the free daily quota. The Cloud Run deploy has not been run, because gcloud is not
installed here and the project has no billing. Both commands are correct as
written; neither has been observed to succeed. Do one rehearsal of each before the
talk, or present them from a slide and say so.

## Next

Nothing. This is the last phase, and this branch contains all nine.
