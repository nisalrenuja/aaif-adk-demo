# Phase 6: Human in the Loop

**Teaches:** `require_confirmation`, and where a safety property should live.
**Stage status:** spine. This one demos beautifully, so give it a proper beat.

## The one idea

```python
book_trip_tool = FunctionTool(func=book_trip, require_confirmation=True)
```

That is the whole gate. ADK intercepts the call before the function body runs,
emits a confirmation request, and pauses the invocation until a human answers.

Nothing inside `book_trip` knows this is happening. It is an ordinary function with
an ordinary docstring. The safety property does not depend on the tool author
remembering to implement it, which is the entire argument for putting it in the
framework.

## Say this part out loud

**The model cannot approve itself.** It cannot be talked into approving itself, it
cannot be prompt injected around the gate, and nobody can accidentally delete the
gate while rewording an instruction. That is only true because the gate is a
framework argument rather than a line in a prompt. If your approval step is a
sentence in an instruction, you do not have an approval step, you have a
suggestion.

## Run it

Both paths, without paying for a whole pipeline run:

```bash
python3 -m agents.p6_safety.run_booking approve
python3 -m agents.p6_safety.run_booking reject
python3 -m agents.p6_safety.run_booking            # asks you at the terminal
```

The script seeds a finished trip into state and runs only `booking_agent`, so it
costs two or three model calls rather than fifteen. On a quota limited key that is
the difference between demoing this and not.

**Show the reject path.** Approving is the boring half. The half worth watching is
the agent being told no and handling it:

```
  It wants to call: book_trip
      traveller_name: A. Traveller
      email: traveller@example.com

  This will charge: 112.0 USD
  This tool is irreversible. Nothing has been charged yet.

  [rejected]

  The booking request was rejected. Please let me know what you would like changed.

[bookings in state: 0]
```

That last line is the proof. Nothing was charged.

## What happens on the wire

1. The model calls `book_trip(...)`.
2. ADK sees `require_confirmation`, finds no confirmation, and instead of running
   the function emits a function call named `adk_request_confirmation` carrying the
   pending call, then stops.
3. A human decides. This step is outside the model's reach.
4. The client sends back a `FunctionResponse` with the same id and a
   `ToolConfirmation` payload.
5. Approved, the body runs. Rejected, the tool returns `This tool call is rejected`
   and the model has to deal with it.

The confirmation call carries `originalFunctionCall`, which is the exact call being
held. A real product renders its approval screen from that. `run_booking.py` is the
terminal version of the same idea, and it is why the prompt can show the amount and
the hotel rather than a generic "approve?".

## Details worth knowing

**Do not gate everything.** `cancel_booking` sits right next to `book_trip` with no
gate, because it is reversible and in the traveller's favour. Gate what is
irreversible. Gate everything and people stop reading the prompts and start
clicking approve on reflex, which is worse than no gate at all because it looks
like one.

**`require_confirmation` also takes a callable.** `FunctionTool(func=..., require_confirmation=fn)`
where `fn` receives the call arguments, so you can gate on value: confirm over 500
USD, wave through anything smaller. Worth one sentence on the slide.

**A paused tool pauses whichever runtime is driving it.** The gate is in the tool,
so it works identically under `SequentialAgent` and under the `Workflow` graph.
`workflow_graph.py` chains booking after the presenter and needed no special
handling.

**It pauses the invocation, so state must survive.** Combine this with Phase 2's
`DatabaseSessionService` and a trip can sit waiting for approval across a restart.
That is what makes it usable in a real product rather than only in a demo.

## Verified

Both paths were run live end to end. Approve produced a booking reference and one
entry in state. Reject produced zero entries and a sensible reply from the agent.

## Next

Phase 7 moves one agent out of this process entirely.
