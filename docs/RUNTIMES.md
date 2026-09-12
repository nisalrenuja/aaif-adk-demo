# Which runtime to build on

This repo ships the same pipeline twice.

- `agents/*/agent.py` builds it from `SequentialAgent`, `ParallelAgent` and
  `LoopAgent`. Call this the **classic** runtime.
- `agents/*/workflow_graph.py` builds it from `Workflow`, a graph of nodes and
  edges. Call this the **graph** runtime.

Both run. Both are demoed. That is right for a talk, where the point is to show the
deprecation honestly, and it is unhelpful for a reader deciding what to build on
Monday. This file is the recommendation the two files do not give you.

## The short version

**Start on the classic runtime. Move to the graph when you hit one of the four
things below, and not before.**

The classic agents are deprecated in ADK 2.5 in favour of `Workflow`. Deprecated is
not removed, and the migration is mechanical, so learning the concepts on three
named classes and porting later costs less than learning graphs first.

## Move to the graph when

**A step in your flow is a decision, not a judgement.** This is the strongest
reason and it is worth money. `budget_gate` in `workflow_graph.py` is a plain
Python function node: it reads state, does arithmetic, sets a route. The classic
pipeline needs a whole `budget_checker` LlmAgent wrapped around the same call to
`evaluate_budget`, because a `LoopAgent` can only contain agents. That is one model
call per refinement iteration spent asking a model to read out a number that
subtraction already produced. If your flow has several such steps, the graph is
strictly cheaper and strictly more predictable.

**Your control flow is not a tree.** Sequential, parallel and loop compose by
nesting, so anything you build is a tree of those three shapes. A retry that skips
back two steps, a branch that rejoins three steps later, a step reachable from two
different places: these are edges, and the classic runtime has no way to say them.
`(budget_gate, {"again": _assemble, "done": _present})` is routing as data, which is
both readable and inspectable.

**You need fan in that waits.** `JoinNode` is explicit about waiting for every
incoming edge. Building this file ran into the alternative: without it a downstream
node runs once per incoming edge, which looks like the pipeline running three times.

**You want the flow to be inspectable.** A graph is a value you can walk, draw and
assert on before you run it. A nest of agent objects is not.

## Stay on the classic runtime when

**A conversational agent has to delegate into the flow.** This is the blocking one.
`Workflow` cannot currently be an `LlmAgent` sub agent, so a concierge that routes
to a pipeline, which is what Phases 1 and 2 build, cannot route to a graph. If your
root is an LlmAgent with `sub_agents`, that settles it.

**The flow really is a tree, and it is short.** Three named classes map onto three
ideas: in order, at the same time, until done. A graph makes you learn nodes, edges,
routes and joins before you have learned anything about agents. For a five step
pipeline the graph buys you nothing you will notice.

**You are teaching or demoing it.** Which is exactly why this repo's primary path is
the classic one, and the graph sits beside it.

## What porting actually costs

Small, and there are two adjustments that are not obvious. Both are in `_as_node`
in `workflow_graph.py`:

- `mode="single_turn"`. An `LlmAgent` defaults to chat mode, which reads the
  conversation history. A graph node is fed by its predecessors instead, and the
  runtime rejects a chat mode agent that follows another node.
- `parent_agent=None`. Agent objects are parented by whatever contains them, so
  reusing the same objects in both runtimes needs a detached copy.

Everything else transfers unchanged: the agents, the tools, the state keys, the
callbacks. `evaluate_budget` in `tools.py` is deliberately a pure function taking
state, so both runtimes compute the total with the same code and cannot disagree
about what a trip costs.

## Summary

| If | Build on |
| --- | --- |
| An LlmAgent must delegate into the flow | Classic. The graph cannot be a sub agent yet. |
| The flow is a short tree | Classic. Fewer concepts for the same result. |
| Deterministic steps are costing you model calls | Graph. Function nodes are free. |
| Control flow needs edges, not nesting | Graph. |
| Fan in must wait for every branch | Graph. `JoinNode`. |
| You are explaining it to someone | Classic, then show them the graph. |
