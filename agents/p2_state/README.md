# Phase 2: State and Services

**Branch:** `phase-2-state`
**Teaches:** `tool_context.state`, instruction templating, and swapping the session
service.

## The one idea, twice

**Agents share a dict.** Add one parameter to a tool:

```python
def add_to_itinerary(day: int, activity: str, price_usd: float,
                     tool_context: ToolContext) -> dict:
    tool_context.state["itinerary"].append(...)
```

`tool_context.state` is shared by every agent in the session. The hotel agent reads
what the flight agent wrote. Nobody passes messages. ADK strips `tool_context` out
of the declaration the model sees, so the model never knows it is there.

**Where that dict lives is a separate decision.** The agents in `agent.py` never
mention storage. `session_services.py` picks the backing store, and it is one line:

```python
InMemorySessionService()                     # gone when the process exits
DatabaseSessionService(db_url=SQLITE_URL)    # survives a restart
VertexAiSessionService(...)                  # managed, in the cloud
```

Same interface. Local demo, laptop persistence and a cloud deployment differ by that
one line and nothing else.

## Instructions are templates too

```python
instruction="What is already known about this trip: {preferences?}"
```

ADK substitutes `{preferences}` from state before the request goes out. The trailing
`?` marks it optional, which is what stops the first turn dying with a `KeyError`.
Drop the `?` and your agent breaks on turn one, every time. That is worth saying out
loud, because everyone hits it.

## Run it

Persistent from the web UI:

```bash
adk web agents --session_service_uri="sqlite:///./trip.db"
```

Or from the terminal, which makes the restart story sharper:

```bash
python3 -m agents.p2_state.run_cli "Plan me 3 days in Kandy, budget 600, I like culture"
python3 -m agents.p2_state.show_state       # no API key needed, reads the db
python3 -m agents.p2_state.run_cli "what does my plan look like so far?"
```

The second `run_cli` prints `[resumed session kandy_trip with N events]`. Different
process, same trip.

## The move that lands

Run `run_cli`, kill the terminal, run `show_state`. The preferences, the itinerary
and the running cost are all still on disk. Then point at the one line in
`session_services.py` and say: swapping that for `VertexAiSessionService` is the
entire difference between this laptop and production.

## Three things that will bite you

**`greenlet` is not optional.** `DatabaseSessionService` uses SQLAlchemy's async
engine, which fails at runtime with `the greenlet library is required to use this
function` if greenlet is missing. It is not pulled in automatically. It is pinned in
`requirements.txt` for this reason.

**Close the session service or your script never exits.** This one cost real time
during the build. The work completes, the output is correct, and the process just
sits there, because the SQLAlchemy engine keeps a thread alive. Both scripts here
end with:

```python
await session_service.close()
```

Without it, a demo script looks like it hung when it actually finished.

**Watch your quota.** Every transfer plus every specialist answer is a model call.
On the free tier that is 5 per minute, per model, and a full trip plan is 10 to 15
calls. See [docs/MODELS.md](../../docs/MODELS.md). `model.py` here bounds the retry
budget so a failure shows up in seconds instead of stalling for five minutes.

## Details worth knowing

**State key prefixes.** `user:` scopes a value to the user across all their
sessions, `app:` to every user of the app, and `temp:` is never persisted. No prefix
means this session only, which is what everything here uses.

**Write through tools, not by hand.** State changes are recorded as event deltas, so
the trip has an audit trail. This is why `add_to_itinerary` exists as a tool instead
of the agent just describing a plan in prose: an activity that was only mentioned in
a reply is not in the plan.

## Next

Phase 3 stops trusting the model to run these steps in the right order.
