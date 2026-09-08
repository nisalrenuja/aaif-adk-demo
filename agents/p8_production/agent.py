"""Phase 7: distributed. One of these agents is not in this process.

Everything from Phase 6 still stands. What changes is where `local_expert` lives.

It is not in this repository's import graph. It runs in its own process, on its own
port, from `local_expert_service/`, and the trip planner reaches it over the A2A
protocol with one line:

    RemoteA2aAgent(name="local_expert", agent_card="http://localhost:8001/...")

From there it behaves like any other sub agent in the fan out. This planner never
imports its code, never sees its tools and does not know what model it runs on.

The story for the slide: different teams own different agents, deploy on their own
schedule, and still compose into one product.

If the service is not running the pipeline drops that agent and carries on. See
`remote.py` for why that is deliberate.

The original Phase 6 docstring follows.

Phase 6: safety. The agent stops and asks before it spends money.

Everything from Phase 5 still stands. What is new is one step at the end of the
pipeline and one argument on one tool.

`booking_agent` runs after the presenter and offers to book. Its `book_trip` tool
is wrapped as:

    FunctionTool(func=book_trip, require_confirmation=True)

ADK intercepts that call before the function body runs, emits a confirmation
request, and pauses. A human answers. Only then does the booking happen.

The property worth stating plainly: the model cannot approve itself. The gate lives
in the framework, not in a prompt, so it cannot be argued with, prompt injected
around, or forgotten by whoever writes the next instruction. See `booking.py`.

The original Phase 5 docstring follows.

Phase 5: model diversity. One pipeline, more than one provider.

Everything from Phase 4 still stands. What changes is which model each agent runs
on, and it changes on two agents only.

Most of these agents do structured lookups: call a tool, read a dict, emit a line.
Flights, hotels, events, the budget check. That work rewards being cheap and fast,
and small Gemini Flash models do it well.

`activity_researcher` is different. Deciding what is actually worth doing with
three days, given someone's interests and the weather, is judgement rather than
lookup, and it is the part of the plan a traveller feels. So it is the one agent
that leaves Gemini, through LiteLLM, which makes the swap a one line change:

    Agent(model=LiteLlm(model="anthropic/claude-sonnet-4-5"), ...)

Cheap where it is repeated, strong where it matters.

Moving it forced a split that is worth more than the swap itself. In Phase 4 the
activity agent held three tool sources at once, including `google_search`. That
tool is built into the Gemini model rather than sent over the wire, so it cannot
follow the agent to Claude: ADK raises `ValueError: Google search tool is not
supported for model anthropic/...` at request time, not at startup. The search
work therefore moved to its own agent, which stays on Gemini because it has to.
Provider bound capabilities pin an agent to a provider.

If no third party key is present, `build_creative_model()` returns Gemini and says
so, so the pipeline still runs. See `providers.py`.

The original Phase 4 docstring follows.

Phase 4: richer tools. Built in, and third party.

Everything from Phase 3 still stands. What changes is where the tools come from.

Until now every tool was a function in `tools.py`. This phase adds two that are
not:

`activity_researcher` now holds all three kinds at once:

- **its own function tool**, `research_activities`, the kind from Phase 0.
- **an OpenAPI spec**, turned into a callable toolset by one line in `weather.py`,
  so it checks the forecast before an outdoor activity lands on a rainy day.
  open-meteo needs no key and no account, which is what makes it usable in front
  of a room.
- **`google_search`**, built into the Gemini model itself. It answers "what is on
  that week", which no amount of mock data can know. It runs inside the model, so
  there is no HTTP for you to write.

One agent, three tool sources, which is the point. ADK 2.5 wraps the built in tool
automatically when other tools are present; older versions could not mix them at
all and needed an AgentTool wrapper.

The original Phase 3 docstring follows, because none of it stopped being true.

Phase 3: workflow agents. All three, in one pipeline.

Phases 1 and 2 let an LLM decide what happens next. That is flexible and it is also
non deterministic, which is exactly wrong for the parts of a flow that must always
happen in the same order. Workflow agents move that decision out of the model and
into code.

Three primitives, one pipeline:

    SequentialAgent   run these in order, every time
      1. preference_agent          normalise the request into state
      2. ParallelAgent             fan out three researchers at once, fan back in
      3. LoopAgent                 assemble, check budget, repeat until it fits
      4. presenter                 write up the final plan

The important detail is that none of the orchestration is a prompt. `SequentialAgent`
does not ask the model what comes next. `LoopAgent` does not ask the model whether to
stop, because `check_budget` sets `escalate` itself, from arithmetic.

On the deprecation warnings: in ADK 2.5 these three classes are deprecated in favour
of the newer graph based `Workflow` runtime. They still work, and they teach the
concept far more clearly, which is why the demo uses them. `workflow_graph.py` next
to this file builds the same pipeline the new way. See the README.
"""

from __future__ import annotations

import warnings

# ADK 2.5 deprecates these in favour of Workflow. We use them on purpose. Silenced
# so the stage terminal stays readable, not because the warning is wrong.
warnings.filterwarnings(
    "ignore", message=r".*deprecated in favor of Workflow.*", category=DeprecationWarning
)

from google.adk import Agent
from google.adk.agents import LoopAgent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search

from .resilience import degrade_gracefully
from .providers import (
    ASSEMBLER_MODEL_ID,
    PRIMARY_MODEL_ID,
    SECOND_MODEL_ID,
    THIRD_MODEL_ID,
    build_creative_model,
    build_model,
)
from .booking import book_trip_tool, cancel_booking_tool
from .remote import build_local_expert
from .weather import build_weather_tools
from .tools import (
    check_budget,
    choose_hotel,
    research_activities,
    research_flights,
    research_hotels,
    save_preferences,
    set_itinerary_day,
)


# --- 1. Preferences --------------------------------------------------------

preference_agent = Agent(
    name="preference_agent",
    model=build_model(PRIMARY_MODEL_ID),
    description="Turns a free text travel request into structured preferences.",
    instruction=(
        "Read the traveller's request and call save_preferences exactly once.\n"
        "\n"
        "Pull out the destination city, the number of days, the total budget in USD "
        "and their interests. If they did not give a budget, use 500 per person and "
        "say that you assumed it. If they did not say where they are flying from, "
        "pass the word none as the origin. Never invent an origin.\n"
        "\n"
        "Reply with one short sentence confirming what you recorded."
    ),
    tools=[save_preferences],
)


# --- 2. Research, in parallel ----------------------------------------------
# Three agents, three different model ids. Partly because the free tier quota is
# counted per model, and partly because it is honest: these are three independent
# lookups and nothing forces them to share a model. See model.py.

flight_researcher = Agent(
    name="flight_researcher",
    # This agent reads its inputs from state, above, so it does not need the
    # conversation history. ADK still passes this turn's own tool calls and
    # results, which is all it actually uses. This one line is the single
    # biggest cost saving in the pipeline. See the cost note in the README.
    include_contents="none",
    model=build_model(PRIMARY_MODEL_ID),
    description="Shortlists flights to the destination.",
    instruction=(
        "Trip preferences: {preferences?}\n"
        "\n"
        "Call research_flights once. Convert city names to IATA codes, for example "
        "Colombo is CMB and London is LHR. Kandy has no airport, so fly into CMB. "
        "If the origin in the preferences is none, pass none straight through and "
        "do not ask anyone for it.\n"
        "\n"
        "Use any date the traveller mentioned, otherwise 2026-10-02. Reply with one "
        "line naming the flight you shortlisted and its price."
    ),
    tools=[research_flights],
    output_key="flight_summary",
    # Research is best effort. A transient model failure here degrades to an
    # honest empty result rather than cancelling the whole parallel fan out.
    on_model_error_callback=degrade_gracefully,
)

hotel_researcher = Agent(
    name="hotel_researcher",
    # This agent reads its inputs from state, above, so it does not need the
    # conversation history. ADK still passes this turn's own tool calls and
    # results, which is all it actually uses. This one line is the single
    # biggest cost saving in the pipeline. See the cost note in the README.
    include_contents="none",
    model=build_model(SECOND_MODEL_ID),
    description="Shortlists places to stay at the destination.",
    instruction=(
        "Trip preferences: {preferences?}\n"
        "\n"
        "Call research_hotels once with the destination city. Do not pick a hotel. "
        "Your job is only to put the shortlist into state, because the step that "
        "picks is the one that knows what is left in the budget.\n"
        "\n"
        "Reply with one line giving the nightly price range you found."
    ),
    tools=[research_hotels],
    output_key="hotel_summary",
    # Research is best effort. A transient model failure here degrades to an
    # honest empty result rather than cancelling the whole parallel fan out.
    on_model_error_callback=degrade_gracefully,
)

activity_researcher = Agent(
    name="activity_researcher",
    # This agent reads its inputs from state, above, so it does not need the
    # conversation history. ADK still passes this turn's own tool calls and
    # results, which is all it actually uses. This one line is the single
    # biggest cost saving in the pipeline. See the cost note in the README.
    include_contents="none",
    # The creative one, and the agent that leaves Gemini. Suggesting what is worth
    # doing with three days is judgement, not lookup. See providers.py.
    model=build_creative_model(),
    description="Shortlists things to do at the destination.",
    instruction=(
        "Trip preferences: {preferences?}\n"
        "\n"
        "Do two things.\n"
        "1. Call research_activities with the destination city and the traveller's "
        "interests.\n"
        "2. Check the forecast for the trip. Kandy is latitude 7.2906, longitude "
        "80.6337, timezone Asia/Colombo. Ask for "
        "temperature_2m_max,precipitation_sum,precipitation_probability_max.\n"
        "\n"
        "Reply with one line on how many options you found and which interests "
        "they lean towards, then one line flagging any day with a high chance of "
        "rain so the assembler can keep outdoor activities off it."
    ),
    # research_activities is ours and the forecast comes from an OpenAPI spec.
    # Both are ordinary tools, so both travel to another provider. google_search
    # does not, which is why it moved to its own agent below.
    tools=[research_activities, *build_weather_tools()],
    output_key="activity_summary",
    # Research is best effort. A transient model failure here degrades to an
    # honest empty result rather than cancelling the whole parallel fan out.
    on_model_error_callback=degrade_gracefully,
)


# In Phase 4 this agent's work was part of activity_researcher, three tool sources
# on one agent. It had to split here, and the reason is the lesson:
#
#   google_search is built into the Gemini model. It is not a tool ADK sends over
#   the wire, it is a capability of the model itself. Move an agent to Claude or
#   GPT through LiteLLM and ADK raises
#
#       ValueError: Google search tool is not supported for model anthropic/...
#
#   at request time, not at startup, so it looks fine until you demo it.
#
# So the split is not tidiness. Provider bound capabilities pin an agent to a
# provider, and the way to keep both is to put them in different agents. This one
# stays on Gemini precisely because it needs Gemini.
events_researcher = Agent(
    name="events_researcher",
    # This agent reads its inputs from state, above, so it does not need the
    # conversation history. ADK still passes this turn's own tool calls and
    # results, which is all it actually uses. This one line is the single
    # biggest cost saving in the pipeline. See the cost note in the README.
    include_contents="none",
    model=build_model(SECOND_MODEL_ID),
    description="Finds festivals and events happening during the trip dates.",
    instruction=(
        "Trip preferences: {preferences?}\n"
        "\n"
        "Search for festivals, processions, public holidays and events happening "
        "in the destination city around the trip dates. Reply with at most three, "
        "one line each, with the date if you can find it.\n"
        "\n"
        "If you find nothing specific, say so plainly. Do not invent an event, "
        "because someone may plan a trip around it."
    ),
    tools=[google_search],
    output_key="events_summary",
    on_model_error_callback=degrade_gracefully,
)


# The remote agent, or None when its service is not running.
local_expert = build_local_expert()

_researchers = [
    flight_researcher,
    hotel_researcher,
    activity_researcher,
    events_researcher,
]

if local_expert is not None:
    # A process on the other end of an HTTP call, sitting in the fan out next to
    # four agents defined thirty lines above it. Nothing else changes.
    _researchers.append(local_expert)


research_team = ParallelAgent(
    name="research_team",
    description="Runs every destination lookup at the same time.",
    sub_agents=_researchers,
)


# --- 3. Assemble and check, in a loop --------------------------------------

itinerary_assembler = Agent(
    name="itinerary_assembler",
    # This agent reads its inputs from state, above, so it does not need the
    # conversation history. ADK still passes this turn's own tool calls and
    # results, which is all it actually uses. This one line is the single
    # biggest cost saving in the pipeline. See the cost note in the README.
    include_contents="none",
    # Its own model id. It makes the most calls of anything here. See model.py.
    model=build_model(ASSEMBLER_MODEL_ID),
    description="Builds the day by day plan and picks the hotel.",
    instruction=(
        "You build the plan. Everything you need is already in state.\n"
        "\n"
        "Preferences: {preferences?}\n"
        "Hotel shortlist: {hotel_options?}\n"
        "Activity shortlist: {activity_options?}\n"
        "Weather and activity notes: {activity_summary?}\n"
        "What is on in town: {events_summary?}\n"
        # A RemoteA2aAgent has no output_key, so its answer is not in state. It is
        # in the conversation, which every later step in the sequence can see.
        "If a local_expert has spoken earlier in this conversation, use its advice "
        "on timing and queues when placing activities.\n"
        "Current plan: {itinerary?}\n"
        "Budget feedback from the last check: {budget_feedback?}\n"
        "\n"
        "On your first pass, plan the trip you would actually recommend rather "
        "than the cheapest one that fits. Take the best rated hotel and the "
        "activities that best match their interests. The budget check runs after "
        "you and will tell you what to cut, and cutting a good plan gives a better "
        "trip than padding a cheap one.\n"
        "\n"
        "Make exactly one pass and then stop. One choose_hotel call, one "
        "set_itinerary_day call per day, then report. Do not re-check your own "
        "arithmetic and do not revise a choice you already made in this pass. The "
        "budget check runs after you and it is the only thing that decides whether "
        "the plan is affordable. Second guessing yourself here costs a model call "
        "and hides the refinement step that follows.\n"
        "\n"
        "Do this every time you run:\n"
        "1. Call choose_hotel with one name from the shortlist.\n"
        "2. Call set_itinerary_day once per day of the trip, passing the exact "
        "activity names from the shortlist. Roughly six to seven hours a day. "
        "Respect best_time, so sunrise hikes in the morning and viewpoints in the "
        "evening. Do not repeat an activity across days. Keep outdoor activities "
        "off any day the weather notes flagged as likely to rain, and if an event "
        "above falls inside the trip, leave room in that day for it.\n"
        "\n"
        "If the budget feedback above says you are over budget, this is a second "
        "pass and you must actually cut. Move to a cheaper hotel first, since that "
        "is usually the largest line, then drop the most expensive activities. "
        "set_itinerary_day replaces a day rather than adding to it, so simply call "
        "it again for the days you changed.\n"
        "\n"
        "Reply with the plan as a short day by day list."
    ),
    tools=[choose_hotel, set_itinerary_day],
    output_key="draft_itinerary",
)

budget_checker = Agent(
    name="budget_checker",
    # This agent reads its inputs from state, above, so it does not need the
    # conversation history. ADK still passes this turn's own tool calls and
    # results, which is all it actually uses. This one line is the single
    # biggest cost saving in the pipeline. See the cost note in the README.
    include_contents="none",
    model=build_model(THIRD_MODEL_ID),
    description="Totals the trip and decides whether the loop keeps going.",
    instruction=(
        "Call check_budget exactly once, then report its verdict in one sentence "
        "with the total and the budget.\n"
        "\n"
        "Do not do the arithmetic yourself and do not argue with the result. The "
        "tool ends the loop on its own when the trip fits. If it says over budget, "
        "state plainly what needs to come out so the next pass can cut it."
    ),
    tools=[check_budget],
    output_key="budget_verdict",
)

refinement_loop = LoopAgent(
    name="refinement_loop",
    description="Rebuilds the plan until it fits the budget.",
    sub_agents=[itinerary_assembler, budget_checker],
    # Always bound a loop. Without this an unlucky run burns quota until it is
    # stopped by hand, which is not a thing you want happening on stage.
    max_iterations=3,
)


# --- 4. Present ------------------------------------------------------------

presenter = Agent(
    name="presenter",
    # This agent reads its inputs from state, above, so it does not need the
    # conversation history. ADK still passes this turn's own tool calls and
    # results, which is all it actually uses. This one line is the single
    # biggest cost saving in the pipeline. See the cost note in the README.
    include_contents="none",
    model=build_model(PRIMARY_MODEL_ID),
    description="Writes up the finished trip for the traveller.",
    instruction=(
        "Write up the finished trip.\n"
        "\n"
        "Preferences: {preferences?}\n"
        "Flight: {chosen_flight?}\n"
        "Hotel: {chosen_hotel?}\n"
        "Itinerary: {itinerary?}\n"
        "Total cost in USD: {total_cost_usd?}\n"
        "Budget outcome: {budget_feedback?}\n"
        "Steps that failed and returned nothing: {degraded_agents?}\n"
        "\n"
        "The itinerary above is a list of entries, each with a day number, an "
        "activity name and a price. Group them by day and write every single one "
        "out with its name and price. A day heading with nothing under it is a "
        "bug, not a plan: if a day genuinely has no activities, say so in words.\n"
        "\n"
        "After the days, give the flight and hotel, then the total against the "
        "budget. Use only what is above. If the budget outcome says the plan is "
        "still over budget after three passes, say so honestly and name what would "
        "have to go, rather than quietly presenting it as if it fits.\n"
        "\n"
        "If any step above is listed as failed, say which part of the plan is "
        "missing because of it. Do not fill the gap from your own knowledge."
    ),
)


# --- 5. Book, but only with a human in the loop ----------------------------

booking_agent = Agent(
    name="booking_agent",
    model=build_model(SECOND_MODEL_ID),
    description="Offers to book the finished trip, and books it once approved.",
    instruction=(
        "The trip is planned and written up. Your job is the booking.\n"
        "\n"
        "Plan: flight {chosen_flight?}, hotel {chosen_hotel?}, itinerary "
        "{itinerary?}, total {total_cost_usd?} USD.\n"
        "\n"
        "If the traveller has clearly asked to book and has given you a name and "
        "an email, call book_trip with them.\n"
        "\n"
        "If they have not asked to book, do not call anything. Say the plan is "
        "ready, state the total, and ask whether they want it booked and under "
        "what name and email. Never guess a name or an email.\n"
        "\n"
        "book_trip pauses for human approval before it runs, so do not treat "
        "calling it as the booking being done. If it comes back rejected, say so "
        "plainly and ask what they would like changed. Do not call it again on the "
        "same details."
    ),
    tools=[book_trip_tool, cancel_booking_tool],
)


# --- The pipeline ----------------------------------------------------------

root_agent = SequentialAgent(
    name="trip_pipeline",
    description=(
        "Plans a trip end to end: preferences, parallel research, budget "
        "constrained assembly, then a write up."
    ),
    sub_agents=[
        preference_agent,
        research_team,
        refinement_loop,
        presenter,
        booking_agent,
    ],
)
