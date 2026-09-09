# Phase 0: The Seed

**Teaches:** `Agent`, and what a tool actually is in ADK.

## The one idea

A tool in ADK is just a typed Python function with a good docstring.

There is no decorator, no registry, no schema file, no JSON to hand write. ADK reads
the type hints and the docstring and generates the function declaration the model
sees. That is the whole mechanism.

The practical consequence: **the docstring is the prompt**. A vague docstring gives
you a vague agent. Everything about when to call the tool, what the arguments mean
and what comes back has to live in there, because that text is all the model gets.

## What is in this folder

| File | What it does |
| --- | --- |
| `agent.py` | The `get_flights` tool and the single `root_agent` that uses it |
| `mock_data.py` | Fake flight inventory, so nothing depends on wifi |
| `inspect_tool.py` | Prints the declaration ADK generated from the docstring |

## Run it

```bash
adk web agents          # from the repo root, then pick p0_seed
```

Ask it:

> Find me flights from Colombo to Singapore on 2026-10-02

## The move that lands

Show the Python function. Then run:

```bash
python3 -m agents.p0_seed.inspect_tool
```

Your docstring comes back as `description`, your type hints come back as a JSON
schema with `origin`, `dest` and `date` all marked required. Nobody wrote that
schema. That is the moment the room understands what an ADK tool is.

## Details worth knowing

**`root_agent` is a magic name.** `adk web` and `adk run` look for a module level
variable called exactly `root_agent`. Rename it and the agent disappears from the
dropdown.

**The model id is pinned, and the id matters more than you think.**
`MODEL = "gemini-3.6-flash"` sits at the top of `agent.py`. We started on
`gemini-2.5-flash` and it returned `404 NOT_FOUND, no longer available to new
users`, while still appearing in `models.list()`. ADK 2.5's own default,
`gemini-3.5-flash`, was returning 503 the same afternoon. Send one real request
before you trust an id: `python3 docs/check_models.py` does exactly that.
See [docs/MODELS.md](../../docs/MODELS.md).

**Tools should not raise.** `get_flights` returns `{"status": "error", ...}` instead
of throwing, and falls back to generic inventory for unknown routes. The model can
read an error dict and recover. It cannot recover from a traceback.

**No defaults in the signature.** ADK marks every parameter required. Give the model
instructions about missing values instead, the way the instruction here tells it to
ask for a date rather than guess.

## Next

Phase 1 splits this one agent into three and puts a concierge in front of them.
