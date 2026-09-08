# Phase 5: Model Diversity

**Branch:** `phase-5-models`
**Teaches:** `LiteLlm`, and why you would want more than one provider in one
pipeline.
**Stage status:** flex. Two minutes if the room is fast, otherwise a slide.

## The one idea

```python
from google.adk.models.lite_llm import LiteLlm

Agent(model=LiteLlm(model="anthropic/claude-sonnet-4-5"), ...)
```

That is the entire integration. Same `Agent`, same tools, same state, same
pipeline, different provider. LiteLLM reads the provider's key from the
environment itself, so there is no client to construct and nothing else to change.

## The reason, which matters more than the mechanism

Anyone can show that a swap is possible. The interesting question is why you would.

This pipeline has two kinds of work in it:

| Work | Agents | Runs | Wants |
| --- | --- | --- | --- |
| Structured lookup | the four researchers | every request, four at a time | cheap and fast |
| Composition | assembler, presenter | once or twice | judgement and prose |

The researchers call one tool, read a dict and emit a line. That is where the cost
is, and a small Flash model does it well. The assembler balances a budget against
interests, weather and what is on in town. The presenter writes the thing a human
actually reads. Their output is the output.

**Cheap where it is repeated, strong where it is read.** That is the slide.

## Run it

Zero cost, no key, good on stage:

```bash
python3 -m agents.p5_models.show_models
```

It prints every agent, its role and the model it will actually use. Then add
`ANTHROPIC_API_KEY` to `.env`, run it again, and watch two rows change while the
other six stay put.

The full pipeline is unchanged:

```bash
python3 -m agents.p5_models.run_pipeline "Plan me 3 days in Kandy, budget 250 USD"
```

## It works without a second key

If neither `ANTHROPIC_API_KEY` nor `OPENAI_API_KEY` is set, `build_creative_model()`
returns Gemini and says so in `show_models`. The pipeline runs either way. That is
deliberate: most machines only have a Gemini key, quite possibly including yours on
the day, and a demo that hard fails on a missing optional key is a bad demo.

## Verified, and not verified

**Verified.** `litellm` installs, `LiteLlm` constructs, and an `Agent` accepts it
as its `model`. The fallback path was run and reports correctly.

**Not verified live.** No Anthropic or OpenAI key was available during the build, so
no request has actually gone to a third party model. Before showing this live, set a
key and run `show_models` followed by one `run_pipeline`. If you are not going to
do that, show the code on a slide and say so rather than running it and hoping.

## Details worth knowing

**Change the model id to match your key.** `ANTHROPIC_MODEL` and `OPENAI_MODEL` are
constants at the top of `providers.py`. LiteLLM model ids are `provider/model`, and
the provider prefix is what decides which environment variable gets read.

**Built in tools do not travel.** `google_search` from Phase 4 runs inside Gemini.
It is not available through LiteLLM, so `events_researcher` has to stay on Gemini.
Worth knowing before you move an agent and wonder where its tool went.

**This also buys quota headroom.** The free Gemini tier is counted per model, so
spreading agents across providers spreads the limits too. That is a side effect
rather than the reason, but on a free key it is a welcome one. See
[docs/MODELS.md](../../docs/MODELS.md).

**Install it.** `pip install litellm`. It is not part of the base `google-adk`
install, and it is a large dependency, which is why it is optional in
`requirements.txt`.

## Next

Phase 6 stops the agent from doing anything irreversible without asking.
