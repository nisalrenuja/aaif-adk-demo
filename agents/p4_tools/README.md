# Phase 4: Built in and Third Party Tools

**Teaches:** `google_search`, and turning an OpenAPI spec into a toolset.
**Stage status:** flex. Show it if the room is fast, otherwise the code is here.

## The one idea

Up to now every tool was a function somebody on your team wrote. That is the
smallest interesting case, not the whole story. This phase adds two tools that
nobody here wrote.

**A tool built into the model.** `google_search` runs inside Gemini, so there is no
HTTP client, no key beyond the one already in `.env`, and no parsing. It answers
the question mock data never can: what is actually on in Kandy that week.

**A tool generated from a spec.** `weather.py` holds an OpenAPI document as a
string, and one line turns it into callable tools:

```python
OpenAPIToolset(spec_str=OPEN_METEO_SPEC, spec_str_type="yaml")
```

ADK parses the operations, builds the declarations from the `description` fields
and handles the request. The activity researcher now checks the forecast before
outdoor activities get committed to a rainy day.

open-meteo was chosen because it needs no key and no account. That is a real
constraint for a live demo: a third party you can show without a login on the
projector is worth more than a better one you cannot.

## Three tool sources, one agent

```python
tools=[research_activities, *build_weather_tools(), google_search]
```

`activity_researcher` holds all three kinds at once: a function we wrote, a toolset
generated from a spec, and a capability of the model itself. That single line is
the phase.

Older ADK could not do this. A built in tool had to sit alone on its own agent, and
mixing it with a function tool meant an `AgentTool` wrapper. ADK 2.5 wraps the
built in tool automatically when other tools are present.

Keep that line in view, because Phase 5 breaks it apart again for a reason worth
hearing.

## Run it

```bash
adk web agents      # pick p4_tools
python3 -m agents.p4_tools.run_pipeline "Plan me 3 days in Kandy, budget 250 USD"
```

## When the wifi dies

`weather.py` has one flag:

```python
USE_LIVE_WEATHER = True     # OpenAPIToolset, real HTTP to open-meteo
USE_LIVE_WEATHER = False    # cached function tool, same shape, no network
```

The cached response was captured from a real open-meteo call, so the offline path
returns the same structure rather than something invented. The agent does not
change either way. Flip it and rerun.

## Verified, and not verified

Honesty about what was tested, because a demo you have not run is a demo that will
surprise you.

**Verified live.** The OpenAPI path was run end to end against open-meteo. The
agent called `get_daily_forecast` and came back with real rain probabilities, then
correctly flagged the wet days for the assembler to avoid.

**Not verified live.** `google_search` builds and wires correctly, but the API key
hit its daily quota before that probe ran. Run it once before the talk:

```bash
python3 -m agents.p4_tools.run_pipeline "Plan me 3 days in Kandy, budget 250 USD"
```

## Details worth knowing

**A built in tool needs a Gemini model, and this bites in Phase 5.**
`google_search` runs inside the model rather than being sent over the wire, so it
cannot follow an agent to another provider. Point this agent at Claude and ADK
raises `ValueError: Google search tool is not supported for model anthropic/...`
**at request time, not at startup**, so everything looks fine until you demo it.
That is exactly what happens in Phase 5, and why the search work splits off there.

**The spec is the prompt.** The `description` fields in `OPEN_METEO_SPEC` are what
the model reads, exactly as a docstring is in Phase 0. The latitude and longitude
for Kandy live in that description, which is why the agent can call the endpoint
without anyone hardcoding coordinates in Python.

**Tell it not to invent.** The agent is instructed to say it found
nothing rather than produce a plausible festival. Someone might plan a trip around
that answer.

## Next

Phase 5 stops assuming every agent wants the same model.
