"""Phase 4: richer tools. Built in, and third party.

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

from .model import (
    ASSEMBLER_MODEL_ID,
    PRIMARY_MODEL_ID,
    SECOND_MODEL_ID,
    THIRD_MODEL_ID,
    build_model,
)
from .resilience import degrade_gracefully
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
    model=build_model(THIRD_MODEL_ID),
    description="Shortlists things to do at the destination.",
    instruction=(
        "Trip preferences: {preferences?}\n"
        "\n"
        "Do three things.\n"
        "1. Call research_activities with the destination city and the traveller's "
        "interests.\n"
        "2. Check the forecast for the trip. Kandy is latitude 7.2906, longitude "
        "80.6337, timezone Asia/Colombo. Ask for "
        "temperature_2m_max,precipitation_sum,precipitation_probability_max.\n"
        "3. Search for festivals, processions, public holidays and events on in "
        "the city around the trip dates.\n"
        "\n"
        "Reply with one line on how many activity options you found, one line "
        "flagging any day with a high chance of rain so the assembler can keep "
        "outdoor activities off it, and at most three events with dates.\n"
        "\n"
        "If you find no events, say so plainly. Do not invent one, because someone "
        "may plan a trip around it."
    ),
    # Three sources in one agent: our own function tool, a toolset generated from
    # an OpenAPI spec, and google_search which runs inside the model itself.
    # ADK 2.5 wraps the built in tool automatically when other tools are present.
    tools=[research_activities, *build_weather_tools(), google_search],
    output_key="activity_summary",
    # Research is best effort. A transient model failure here degrades to an
    # honest empty result rather than cancelling the whole parallel fan out.
    on_model_error_callback=degrade_gracefully,
)



research_team = ParallelAgent(
    name="research_team",
    description="Runs the flight, hotel and activity lookups at the same time.",
    sub_agents=[flight_researcher, hotel_researcher, activity_researcher],
)


# --- 3. Assemble and check, in a loop --------------------------------------

itinerary_assembler = Agent(
    name="itinerary_assembler",
    # Its own model id. It makes the most calls of anything here. See model.py.
    model=build_model(ASSEMBLER_MODEL_ID),
    description="Builds the day by day plan and picks the hotel.",
    instruction=(
        "You build the plan. Everything you need is already in state.\n"
        "\n"
        "Preferences: {preferences?}\n"
        "Hotel shortlist: {hotel_options?}\n"
        "Activity shortlist: {activity_options?}\n"
        "Weather, events and activity notes: {activity_summary?}\n"
        "Current plan: {itinerary?}\n"
        "Budget feedback from the last check: {budget_feedback?}\n"
        "\n"
        "On your first pass, plan the trip you would actually recommend rather "
        "than the cheapest one that fits. Take the best rated hotel and the "
        "activities that best match their interests. The budget check runs after "
        "you and will tell you what to cut, and cutting a good plan gives a better "
        "trip than padding a cheap one.\n"
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


# --- The pipeline ----------------------------------------------------------

root_agent = SequentialAgent(
    name="trip_pipeline",
    description=(
        "Plans a trip end to end: preferences, parallel research, budget "
        "constrained assembly, then a write up."
    ),
    sub_agents=[preference_agent, research_team, refinement_loop, presenter],
)
