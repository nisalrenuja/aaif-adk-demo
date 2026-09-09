# Phase 1: Delegation

**Teaches:** `sub_agents`, and why `description` is routing logic.

## The one idea

You never write a router.

`sub_agents=[...]` is the whole multi agent primitive. The concierge is an ordinary
LLM agent with no tools of its own. ADK gives it a built in `transfer_to_agent` tool
and shows it each sub agent's `description`. The model picks. That is the mechanism,
end to end.

The consequence is the thing worth saying out loud: **`description` stops being
documentation and becomes behaviour.** It is the only text the concierge sees when
choosing. Compare the two fields on `flight_agent` in `agent.py`:

- `description` is written for a reader who has to choose between three options.
- `instruction` is written for the agent once it has already been chosen.

Get those backwards and routing silently degrades.

## What changed from Phase 0

| Phase 0 | Phase 1 |
| --- | --- |
| one agent, one tool | three specialists, one tool each |
| the agent answers | a concierge routes, specialists answer |
| `get_flights` | plus `get_hotels`, `get_activities` |

Tools moved out to `tools.py` so `agent.py` is only about agent structure.

## Run it

```bash
adk web agents          # from the repo root, then pick p1_delegation
```

The demo query:

> Plan me 3 days in Kandy

Watch the concierge transfer to `activity_agent`. Then follow up with:

> Where should I stay?

## Watch the transfer happen

In `adk web`, open the Events panel. You will see a `transfer_to_agent` function
call with `agent_name: activity_agent` before any real work happens. That single
event is the proof that routing is a model decision, not code you wrote.

## Details worth knowing

**Control stays where it lands.** After the concierge transfers to `flight_agent`,
that agent handles the next turn too. It is not a one shot dispatch. Ask about
hotels straight after a flight question and `flight_agent` has to hand off, which is
why its instruction ends by telling it to do exactly that.

**Peers can transfer to peers.** By default a sub agent may transfer to a sibling or
back to its parent. Set `disallow_transfer_to_peers=True` or
`disallow_transfer_to_parent=True` on an agent to lock it down. Worth knowing before
a routing loop surprises you on stage.

**The concierge has zero tools.** That is deliberate. Give it a tool and it will
start answering things itself instead of routing. Keeping it empty makes the
delegation visible.

**Routing is a prompt, so it can be wrong.** This is the honest caveat for the room.
Phase 3 replaces this soft routing with deterministic workflow agents for the parts
of the flow that must always run in the same order.

## Next

Phase 2 gives the specialists somewhere to write their findings, so they stop
talking only to the transcript.
