"""The same pipeline on ADK 2.5's graph runtime, for the "what comes next" slide.

`agent.py` builds this flow out of `SequentialAgent`, `ParallelAgent` and
`LoopAgent`. In ADK 2.5 those three are deprecated in favour of `Workflow`, a graph
of nodes and edges. This file is the same trip planner expressed that way, so the
claim on the slide has running code behind it.

Why the demo still uses the classic agents:

- Three named classes map onto three ideas: in order, at the same time, until done.
  A graph makes you learn edges, routes and joins before you have learned anything
  about agents.
- `Workflow` cannot yet be used as an `LlmAgent` sub agent, so it is not a drop in
  replacement for the earlier phases.

Why the graph is genuinely better once you need it:

- **Deterministic steps do not need a model.** `budget_gate` below is a plain
  function node. The classic pipeline needed a whole `budget_checker` LlmAgent
  wrapped around the same arithmetic, which is one model call per loop iteration
  spent on a decision that was never the model's to make.
- **Fan in is explicit.** `JoinNode` waits for all three researchers. Without it a
  downstream node runs once per incoming edge, which is a real bug that this file
  ran into during the build.
- **Routing is data.** `{"again": ..., "done": ...}` is an edge map you can read,
  not a control flow rule buried in an agent class.

Run it with:

    python3 -m agents.p3_workflow.run_graph "Plan me 3 days in Kandy, budget 250"
"""

from __future__ import annotations

from google.adk.workflow import JoinNode, START, Workflow, node

from .agent import (
    activity_researcher,
    flight_researcher,
    hotel_researcher,
    itinerary_assembler,
    preference_agent,
    presenter,
)
from .tools import FEEDBACK, STATUS, TOTAL, evaluate_budget

# How many refinement passes before we give up and present what we have.
MAX_PASSES = 3


@node(name="budget_gate")
def budget_gate(ctx) -> dict:
    """Total the trip and decide whether to refine again or present.

    This is the whole argument for the graph runtime in one function. No model, no
    prompt, no tool call. It reads state, does arithmetic, and sets `ctx.route`,
    which the edge map below turns into control flow.
    """
    result = evaluate_budget(ctx.state)

    passes = int(ctx.state.get("budget_passes", 0)) + 1
    ctx.state["budget_passes"] = passes
    ctx.state[TOTAL] = result["total_cost_usd"]
    ctx.state[FEEDBACK] = result["feedback"]
    ctx.state[STATUS] = result["verdict"]

    if result["verdict"] == "under_budget":
        ctx.route = "done"
    elif passes >= MAX_PASSES:
        # Always bound the loop. An unbounded refine burns quota until someone
        # notices, which is not a thing you want happening on stage.
        ctx.state[FEEDBACK] = (
            result["feedback"] + f" Giving up after {passes} passes and presenting "
            "the closest plan, clearly marked as over budget."
        )
        ctx.route = "done"
    else:
        ctx.route = "again"

    return {"pass": passes, **result}


def _as_node(agent, name: str):
    """Wrap one of the Phase 3 agents as a graph node.

    Two adjustments are needed, and both are worth knowing before you port a
    working pipeline onto the graph runtime.

    `mode="single_turn"`: an LlmAgent defaults to chat mode, which reads the
    conversation history. A graph node is fed by its predecessors instead, and the
    runtime rejects a chat mode agent that follows another node with a very clear
    error. Single turn is what a pipeline step actually is.

    `parent_agent=None`: these same agent objects are already parented by the
    SequentialAgent in agent.py. Copying detaches them so both runtimes can be
    imported in the same process, which is how this repo runs the comparison.
    """
    return node(
        agent.model_copy(update={"mode": "single_turn", "parent_agent": None}),
        name=name,
    )


# Wrap each agent once and reuse the object. `node(...)` builds a new wrapper every
# call, and two wrappers around the same agent are two nodes with the same name,
# which fails graph validation. The assembler in particular is referenced twice,
# once in the main chain and once on the loop back edge.
_preferences = _as_node(preference_agent, "preferences")
_flights = _as_node(flight_researcher, "flights")
_hotels = _as_node(hotel_researcher, "hotels")
_activities = _as_node(activity_researcher, "activities")
_assemble = _as_node(itinerary_assembler, "assemble")
_present = _as_node(presenter, "present")

# JoinNode is what makes the fan in correct. Drop it and `budget_gate` fires once
# per researcher instead of once per round.
research_complete = JoinNode(name="research_complete")

root_agent = Workflow(
    name="trip_graph",
    description="The Phase 3 trip pipeline expressed as a graph.",
    edges=[
        # preferences, then three researchers at once, then wait for all three,
        # then assemble, then the gate.
        (START, _preferences, (_flights, _hotels, _activities),
         research_complete, _assemble, budget_gate),
        # The loop back, and the way out. Routing as data.
        (budget_gate, {"again": _assemble, "done": _present}),
    ],
)
