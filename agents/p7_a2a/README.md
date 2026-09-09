# Phase 7: Agent to Agent

**Teaches:** `to_a2a`, `RemoteA2aAgent`, and composing across team boundaries.
**Stage status:** flex. Needs a second terminal, so only if the room is fast.

## The one idea

`local_expert` is not in this repository's import graph. It runs in its own
process, on its own port, from `local_expert_service/`. The trip planner reaches it
with one line:

```python
RemoteA2aAgent(name="local_expert",
               agent_card="http://localhost:8001/.well-known/agent-card.json")
```

From there it sits in the parallel fan out next to four agents defined thirty lines
above it, and nothing else changes. The planner never imports its code, never sees
its tools, and does not know what model it runs on.

The other half is just as short. `local_expert_service/server.py`:

```python
app = to_a2a(root_agent, host=HOST, port=PORT)
uvicorn.run(app, host=HOST, port=PORT)
```

The agent in `local_expert_service/agent.py` has no A2A imports, no server code and
no protocol awareness. **Publishing an agent is a deployment decision, not a
rewrite.** That is the sentence for the slide.

## Run it

Two terminals.

```bash
# terminal 1
python3 -m local_expert_service.server

# terminal 2
adk web agents        # pick p7_a2a
```

Or check the service by hand first, which is the better demo:

```bash
curl -s http://localhost:8001/.well-known/agent-card.json | python3 -m json.tool
```

## The move that lands

Show the agent card before showing any agent code.

```json
{
  "name": "local_expert",
  "description": "A local who actually lives at the destination...",
  "skills": ["model", "get_local_tips"]
}
```

That is a machine readable contract, generated from the agent's `description` and
its tools, that another team can discover and call without reading your source.
Then start the planner and watch `local_expert` appear as a fifth branch in the
parallel fan out.

Then stop the service and run again. The pipeline drops that agent and carries on
with four, which is the next section.

## Failing well is part of the demo

`build_local_expert()` returns `None` when the card is unreachable, and `agent.py`
leaves the agent out of the fan out. A local expert is a nice to have, not a
dependency.

This is not defensive padding. A distributed system where one team's outage takes
down another team's product is a distributed system nobody wants to join. And on a
practical level, a demo that hard fails because you forgot a second terminal is a
bad demo.

## Verified

Run live, end to end. The server started, served a real agent card with discovered
skills, and answered a question about Kandy temples over the protocol from a
separate process. The fallback path was verified too: with the service down the
pipeline builds with four researchers instead of five.

## Things that will bite you

**Start the expert before `adk web`.** ADK imports each agent module once and
caches it. `build_local_expert()` runs at import time, so a planner loaded while
the service is down builds with four researchers and stays that way until you
restart `adk web`. Correct order:

```bash
python3 -m local_expert_service.server   # first
adk web agents                           # then this
```

**`http://localhost:8001` returns 405 Method Not Allowed.** That is correct, not a
failure. The A2A root is a JSON-RPC endpoint that only accepts POST, so browsing to
it looks broken on a projector. Point people at the card instead:

```
http://localhost:8001/.well-known/agent-card.json
```


**`sse-starlette` is missing from the extra.** `pip install "google-adk[a2a]"` does
not pull it in, and the server dies at startup with
`ModuleNotFoundError: No module named 'sse_starlette'`. Install it explicitly.
This is in `requirements.txt` with a note.

**Installing the a2a extra upgrades pydantic.** On this machine it moved pydantic
and requests up, which pip flagged as breaking two unrelated packages already
installed. Use a virtualenv rather than a base conda environment, and check
`pip check` after installing if you share the environment with other projects.

**The card path is `/.well-known/agent-card.json`.** Some older documentation says
`/.well-known/agent.json`. ADK falls back to the old name if the a2a SDK is not
importable, which makes for a confusing 404. Take the constant from
`a2a.utils.constants.AGENT_CARD_WELL_KNOWN_PATH` rather than typing it.

**A `RemoteA2aAgent` has no `output_key`.** It is a `BaseAgent`, not an `LlmAgent`,
so it cannot write its answer into state the way the local researchers do. Its
response lives in the conversation instead, which later steps in the sequence can
still read. The assembler's instruction was written accordingly. If you need it in
state, use `after_agent_callback`.

**Two processes means two quotas and two `.env` reads.** The local expert runs its
own model on its own key. That is realistic, and it is also a second thing that can
be rate limited.

## Next

Phase 8 puts all of this behind `adk web`, an eval set and a deploy.
