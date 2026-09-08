# Phase 3: Workflow Agents

**Branch:** `phase-3-workflow`
**Teaches:** `SequentialAgent`, `ParallelAgent`, `LoopAgent`, all three in one
pipeline, plus the graph runtime that replaces them.

This is the centre of the talk. Give it the most stage time.

## The one idea

Phases 1 and 2 let a model decide what happens next. Workflow agents take that
decision away from the model and put it in code.

```
SequentialAgent  trip_pipeline          run these in order, every time
  LlmAgent         preference_agent     normalise the request into state
  ParallelAgent    research_team        fan out, then fan back in
    LlmAgent         flight_researcher
    LlmAgent         hotel_researcher
    LlmAgent         activity_researcher
  LoopAgent        refinement_loop      repeat until it fits, max 3 passes
    LlmAgent         itinerary_assembler
    LlmAgent         budget_checker
  LlmAgent         presenter            write it up
```

Three primitives, three questions: **in what order**, **what at the same time**,
**how do we know when to stop**. None of those are prompts here.

## The line that matters

```python
def check_budget(tool_context: ToolContext) -> dict:
    ...
    if result["verdict"] == "under_budget":
        tool_context.actions.escalate = True   # this ends the LoopAgent
```

The loop does not ask a model whether the trip fits the budget. It subtracts. The
model chooses which activities go on which day; the tool does every sum and sets
`escalate` itself. That is why the loop terminates, and it is the difference
between a demo and something you would ship.

`max_iterations=3` is the second half of that. Always bound a loop. An unbounded
refine burns quota until a human notices.

## Run it

```bash
adk web agents      # pick p3_workflow, then watch the Events panel
```

Or from the terminal, which narrates each step:

```bash
python3 -m agents.p3_workflow.run_pipeline "Plan me 3 days in Kandy, budget 250 USD, I like culture and food"
```

Budget 250 is chosen deliberately, and the assembler is instructed to plan the trip
it would actually recommend on the first pass rather than the cheapest one that
fits. Those two together are what make the loop fire.

That instruction is not decoration. The first live run of this pipeline had the
assembler pick the cheapest hotel immediately, come in at 175 against 250, and exit
the loop on pass one. Correct behaviour, useless demo. Telling it to propose the
good trip first and let the budget check do the cutting is both more realistic and
what makes the refinement visible.

## Prove the loop without spending a request

```bash
python3 -m agents.p3_workflow.test_budget_loop
```

No API key, no model, no quota. It builds an over budget plan, asserts the loop
does **not** exit, applies the cut, and asserts it does. Because the budget gate is
arithmetic rather than a prompt, it can be unit tested like any other function.
Showing this right before the live run is a strong beat: this part cannot flake.

## The graph runtime, honestly

In ADK 2.5 all three of these classes are **deprecated in favour of `Workflow`**,
a graph of nodes and edges. Say this on the slide before someone in the room says
it to you.

The demo still uses the classic agents because three named classes map onto three
ideas, while a graph makes you learn edges, routes and joins first. Also `Workflow`
cannot yet be an `LlmAgent` sub agent, so it is not a drop in replacement for
Phases 1 and 2.

`workflow_graph.py` builds the identical pipeline the new way, so the claim has
running code behind it:

```bash
python3 -m agents.p3_workflow.run_graph "Plan me 3 days in Kandy, budget 250 USD"
```

The scripts differ by one word, `agent=` versus `node=`.

Where the graph is genuinely better:

- **Deterministic steps stop needing a model.** `budget_gate` is a plain function
  node. The classic pipeline needed a whole `budget_checker` LlmAgent wrapped
  around the same arithmetic, which is a model call per iteration spent on a
  decision that was never the model's to make.
- **Fan in is explicit.** `JoinNode` waits for all three researchers. Leave it out
  and the next node fires once per incoming edge. This build hit exactly that bug.
- **Routing is data.** `{"again": assemble, "done": present}` is an edge map you
  can read.

## Verified live, end to end

The full pipeline was run and completed, exit code 0:

```
[preference_agent]     -> save_preferences
[hotel_researcher]     -> research_hotels      \
[flight_researcher]    -> research_flights      |  all three at once
[activity_researcher]  -> research_activities  /
[itinerary_assembler]  -> choose_hotel
[itinerary_assembler]  -> set_itinerary_day  x3
[budget_checker]       -> check_budget
[presenter]            finished
```

Eight activities across three days, a hotel, 175.0 USD against a 250 USD budget,
all of it in session state at the end.

Two defects surfaced in that run, both now fixed:

1. **The presenter emitted empty day headings.** The itinerary was in state with
   eight entries and it rendered `Day 1`, `Day 2`, `Day 3` with nothing under them.
   State injection puts a list of dicts into the prompt and a small model will
   happily skim it. The instruction now says explicitly that a day heading with
   nothing under it is a bug.
2. **The loop exited on the first pass**, described above.

A third thing was fixed before that run rather than after. A transient 503 on one
researcher killed the entire pipeline, because `ParallelAgent` uses an
`asyncio.TaskGroup` and a TaskGroup cancels its siblings when any task raises. See
`resilience.py`. In a later run the callback did its job:

```
[!] flight_researcher could not complete because the model's quota was exhausted.
[flight_researcher] finished
```

The other two researchers finished normally and the pipeline carried on.

## What one run actually costs

```bash
python3 -m agents.p3_workflow.measure_cost
```

Every ADK event carries `usage_metadata`, so this is measured rather than guessed.
One full run, with the loop taking two passes:

| Agent | Calls | Input tokens | Output |
| --- | --- | --- | --- |
| `itinerary_assembler` | 4 | 20,232 | 987 |
| `budget_checker` | 4 | 13,474 | 94 |
| `presenter` | 1 | 4,558 | 303 |
| `activity_researcher` | 2 | 1,362 | 56 |
| `flight_researcher` | 2 | 1,359 | 59 |
| `hotel_researcher` | 2 | 1,128 | 37 |
| `preference_agent` | 2 | 994 | 72 |
| **Total** | **17** | **43,107** | **1,608** |

Plus 4,177 thinking tokens. **48,892 billable tokens for one run.**

Two things worth saying out loud:

**The loop is 78% of your input tokens.** The assembler and budget checker run
twice and carry the full state each time. If you ever need to make an agent
pipeline cheaper, the loop is where you look first, not the number of agents.

**Input dwarfs output, 27 to 1.** That is normal for agent pipelines and it is good
news, because input is the cheaper half of every price sheet. It also means context
size, not verbosity, is what drives your bill.

For the free tier, what matters is calls per model, not tokens. This run spread 17
calls over four models, worst case 6 on one model, so roughly **3 runs a day**
before that model hits its 20 per day cap. The script prints that verdict for you.

## Things that will bite you

**Quota is the real constraint, not the code.** One full run is 10 to 15 model
calls, and a parallel fan out fires three at once. On the free tier that runs into
`429 RESOURCE_EXHAUSTED` mid pipeline, and because `ParallelAgent` uses an
`asyncio.TaskGroup`, one researcher failing takes the whole run down with an
`ExceptionGroup`. Two mitigations are already in this phase:

- the three researchers point at three different model ids, because the quota is
  counted per model, which roughly triples free tier headroom
- `build_model()` bounds retries to 2 attempts, so a failure is visible in seconds
  rather than stalling for five minutes

Getting one clean end to end run on a free key took five attempts and burned the
daily quota on four separate model ids. The model ids are environment overridable
for exactly this reason:

```bash
TRIP_PRIMARY_MODEL=gemini-3.5-flash-lite \
TRIP_ASSEMBLER_MODEL=gemini-3.1-flash-lite-preview \
python3 -m agents.p3_workflow.run_pipeline "Plan me 3 days in Kandy, budget 250 USD"
```

`python3 docs/check_models.py` tells you which ids still have headroom. The real fix
for a live talk is billing on the key. See [docs/MODELS.md](../../docs/MODELS.md).

**Bounding retries is not enough, you need a timeout.** A 503 on an overloaded
model does not refuse quickly, it hangs: one took 72 seconds to come back. Two
attempts plus backoff was a five minute stall with no output. `build_model()` sets
both `attempts=2` and a 25 second request timeout, and only the timeout actually
caps that.

**The assembler needs its own model id on a free key.** It makes the most calls of
anything here: a hotel, one per day, a summary, then possibly all of it again on
the next pass. That is more than 5 requests in a minute on one model, which is the
free per minute limit, so it rate limits itself even when nothing else is running.
`TRIP_ASSEMBLER_MODEL` exists for this.

**Porting to the graph needs `mode="single_turn"`.** An `LlmAgent` defaults to chat
mode, which reads conversation history. A graph node is fed by its predecessors
instead, and the runtime refuses a chat mode agent that follows another node. The
error message is clear, which is more than most frameworks manage.

**`node(agent)` twice makes two nodes.** Wrapping the same agent in two `node()`
calls produces two nodes with the same name and fails graph validation. Wrap once,
bind it to a variable, reuse the variable. The assembler needs this because it is
referenced twice, once in the chain and once on the loop back edge.

**Each parallel agent needs its own `output_key`.** They share one state dict, so
two agents writing the same key means the slower one wins. The three researchers
here write `flight_summary`, `hotel_summary` and `activity_summary`.

## The move that lands

Open the Events panel in `adk web` and run it. The three researchers appear as
overlapping spans rather than a staircase, and the assemble and check pair repeats
visibly until the total drops under budget. That picture costs nothing to produce
and explains the whole phase without a word.

## Next

Phase 4 gives the activity researcher tools it did not have to write.
