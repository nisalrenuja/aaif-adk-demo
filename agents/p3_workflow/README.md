# Phase 3: Workflow Agents

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

## What one run costs, and how it got halved

```bash
python3 -m agents.p3_workflow.measure_cost
```

Every ADK event carries `usage_metadata`, so this is measured rather than guessed.
That matters, because the first measurement immediately showed the cost was not
where anyone would have looked for it.

### The measurement

Same scenario, same 17 model calls, before and after one afternoon of tuning:

| | Before | After | Change |
| --- | --- | --- | --- |
| Input tokens | 43,107 | **18,414** | **57% less** |
| Output tokens | 1,608 | 1,442 | 10% less |
| Thinking tokens | 4,177 | 4,527 | slightly more |
| **Billable total** | **48,892** | **24,383** | **50% less** |

Per agent, where the input tokens went:

| Agent | Before | After | Cut |
| --- | --- | --- | --- |
| `itinerary_assembler` | 20,232 | 11,603 | 43% |
| `budget_checker` | 13,474 | 2,671 | **80%** |
| `presenter` | 4,558 | 642 | 86% |
| `activity_researcher` | 1,362 | 941 | 31% |
| `flight_researcher` | 1,359 | 881 | 35% |
| `hotel_researcher` | 1,128 | 786 | 30% |
| `preference_agent` | 994 | 890 | unchanged, by design |

### The one line that did it

```python
include_contents="none",
```

Seven of these agents read every input they use from state, through the
`{preferences?}` style templating in their instructions. They were also being sent
the entire conversation history on every call, and none of them looked at it.

`budget_checker` is the clearest case: **13,474 input tokens down to 2,671**, an
80% cut, for an agent whose whole job is calling one deterministic tool. It was
paying to re-read the transcript four times in order to say "call check_budget".

ADK still passes each turn's own function calls and results under
`include_contents="none"`, so tool use keeps working. Only history is dropped.

`preference_agent` deliberately keeps the default, because it is the one agent
that genuinely needs to read what the traveller typed.

### The model swap did less than you would think

The defaults also moved to lite tier ids. That lowers the price per token but
changes no token counts, and it is the more obvious of the two moves.
**The config line saved more than the cheaper models did.** Worth a slide: before
you shop for a cheaper model, check whether you are paying to send context nobody
reads.

### Two things the numbers say

**The loop dominates.** The assembler and budget checker run twice and carry state
each time. Even after tuning they are 78% of input. When an agent pipeline needs to
get cheaper, look at what repeats, not at how many agents you have.

**Input dwarfs output, roughly 13 to 1 after tuning, 27 to 1 before.** That is
normal for agent pipelines, and it means context size rather than verbosity drives
the bill. It is also good news, since input is the cheaper half of every price
sheet.

### The regression this nearly shipped

The first optimised run was 50% cheaper, produced a correct itinerary, and
**broke the demo**. The assembler started second guessing itself inside a single
turn, calling `choose_hotel` twice before any budget check ran, so the loop
completed in one pass and the refinement step became invisible. Cheaper, correct,
and useless for teaching the thing this phase exists to teach.

The fix was to tell the assembler to make exactly one pass and let the budget gate
decide. That is better design as well as a better demo: the agent proposes, the
deterministic gate disposes.

The lesson generalises. **A cost optimisation that is measured only in tokens can
pass every check and still ruin the behaviour you cared about.** Re-run the thing
end to end and look at what it does, not only at what it spent.

### Free tier

Unchanged at roughly **3 runs a day**, because that is governed by calls per model,
not tokens, and the call count did not move. Raising it means more distinct model
ids, not cheaper ones. On a paid key, you now pay half.

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
