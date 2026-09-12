"""The tools, checked as the pure functions they are.

`tools.py` is dict in, dict out, with the session state passed in explicitly. That
makes every branch in it reachable from a test with no API key, no model and no
network, which is the same argument `test_budget_loop.py` makes on stage.

What is pinned here is the arithmetic and the edge cases, because those are the
bugs that do not announce themselves. A trip costed with one night too many still
renders as a perfectly plausible plan.
"""

from __future__ import annotations

from agents.p8_production.tools import (
    check_budget,
    choose_hotel,
    evaluate_budget,
    research_activities,
    research_flights,
    research_hotels,
    save_preferences,
    set_itinerary_day,
)

# --- save_preferences ------------------------------------------------------


def test_days_floor_at_one(ctx):
    """A zero or negative day count is clamped, not stored."""
    result = save_preferences("Kandy", 0, 250, "culture", "none", ctx)
    assert result["preferences"]["days"] == 1


def test_interests_split_and_stripped(ctx):
    result = save_preferences("Kandy", 3, 250, " culture , food ,, ", "none", ctx)
    assert result["preferences"]["interests"] == ["culture", "food"]


# --- research_flights: the skip path ---------------------------------------


def test_missing_origin_skips_rather_than_guessing(ctx):
    """No origin means no flight, and the state says so explicitly.

    The alternative, inventing an origin, produces a trip with a 600 dollar flight
    the traveller never asked for, and nothing downstream can tell it was invented.
    """
    result = research_flights("none", "CMB", "2026-10-02", ctx)
    assert result["status"] == "skipped"
    assert ctx.state["chosen_flight"] == {}
    assert ctx.state["flight_options"] == []


def test_every_spelling_of_no_origin_skips(ctx):
    for origin in ("none", "None", " NONE ", "unknown", ""):
        ctx.state.clear()
        assert research_flights(origin, "CMB", "2026-10-02", ctx)["status"] == "skipped"


def test_known_route_picks_the_cheapest(ctx):
    result = research_flights("lhr", "cmb", "2026-10-02", ctx)
    assert result["chosen_flight"]["price_usd"] == 587  # QR 004, not the 640
    assert ctx.state["chosen_flight"] == result["chosen_flight"]


def test_unknown_route_falls_back_without_dead_ending(ctx):
    """An unknown pair must still produce a flight, or the pipeline stalls."""
    result = research_flights("ZZZ", "YYY", "2026-10-02", ctx)
    assert result["status"] == "success"
    assert result["chosen_flight"]["price_usd"] == 205


# --- research_activities ---------------------------------------------------


def test_interests_sort_first_without_dropping_the_rest(ctx):
    """Ranking, not filtering. A three day trip needs more than the matches."""
    result = research_activities("Kandy", "food", ctx)
    names = [a["category"] for a in result["activities"]]
    assert names[0] == "food"
    assert len(result["activities"]) == 9  # everything is still there


def test_any_interest_leaves_the_order_alone(ctx):
    ranked = research_activities("Kandy", "any", ctx)["activities"]
    assert ranked[0]["name"] == "Temple of the Sacred Tooth Relic"


# --- choose_hotel ----------------------------------------------------------


def test_unknown_hotel_names_the_alternatives(kandy):
    """The error has to be actionable: the model's next call depends on it."""
    result = choose_hotel("The Ritz", kandy)
    assert result["status"] == "error"
    assert "Kandy Hills Rest" in result["error_message"]
    assert "chosen_hotel" not in kandy.state


def test_hotel_match_is_case_insensitive(kandy):
    assert choose_hotel("  kandy hills rest  ", kandy)["status"] == "success"


def test_stay_cost_is_nights_not_days(kandy):
    """Three days is two nights. 42 * 2, not 42 * 3."""
    result = choose_hotel("Kandy Hills Rest", kandy)
    assert result["nights"] == 2
    assert result["stay_cost_usd"] == 84


def test_one_day_trip_still_charges_one_night(ctx):
    """A deliberate floor, pinned because it is a choice and not an accident.

    `max(days - 1, 1)` means a single day trip is costed with one night rather than
    zero. Someone arriving and leaving the same day probably has no hotel at all,
    but costing it at zero silently produces a trip with a hotel in the itinerary
    and nothing in the total, which is the worse of the two wrong answers.

    If this ever changes, `evaluate_budget` has to change with it. The next test is
    what makes sure of that.
    """
    save_preferences("Kandy", 1, 250, "culture", "none", ctx)
    research_hotels("Kandy", ctx)
    assert choose_hotel("Kandy Hills Rest", ctx)["nights"] == 1


def test_choose_hotel_and_evaluate_budget_agree_on_nights(ctx):
    """The same `max(days - 1, 1)` is written out in both functions.

    They are two expressions that have to stay equal, so this walks a range of trip
    lengths and asserts the hotel line in the budget equals what `choose_hotel`
    quoted. An off by one in either place fails here rather than on stage.
    """
    for days in (1, 2, 3, 7, 14):
        ctx.state.clear()
        save_preferences("Kandy", days, 100_000, "culture", "none", ctx)
        research_hotels("Kandy", ctx)
        quoted = choose_hotel("Kandy Hills Rest", ctx)["stay_cost_usd"]
        assert evaluate_budget(ctx.state)["breakdown"]["hotel_usd"] == quoted, days


# --- set_itinerary_day -----------------------------------------------------


def test_repeated_name_in_one_call_is_counted_once(kandy):
    """Listing the same activity twice is a slip, not a request to do it twice."""
    result = set_itinerary_day(1, ["Kandy Lake walk", "Kandy Lake walk"], kandy)
    assert len(result["activities"]) == 1
    assert len(kandy.state["itinerary"]) == 1


def test_dedup_is_case_insensitive(kandy):
    result = set_itinerary_day(1, ["Kandy Lake walk", "KANDY LAKE WALK"], kandy)
    assert len(result["activities"]) == 1


def test_setting_a_day_again_replaces_it(kandy):
    """This is what makes the refinement loop safe to run twice."""
    set_itinerary_day(1, ["Ambuluwawa Tower day trip"], kandy)  # 25
    set_itinerary_day(1, ["Kandy Lake walk"], kandy)  # 0
    assert [i["activity"] for i in kandy.state["itinerary"]] == ["Kandy Lake walk"]
    assert evaluate_budget(kandy.state)["breakdown"]["activities_usd"] == 0


def test_replacing_one_day_leaves_the_others_alone(kandy):
    set_itinerary_day(1, ["Kandy Lake walk"], kandy)
    set_itinerary_day(2, ["Udawattakele forest hike"], kandy)
    set_itinerary_day(1, ["Temple of the Sacred Tooth Relic"], kandy)
    assert sorted(i["day"] for i in kandy.state["itinerary"]) == [1, 2]


def test_unknown_activity_is_reported_not_invented(kandy):
    """An unrecognised name must not become a zero cost line in the plan.

    Silently dropping it would leave the presenter describing a day that costs
    nothing. Silently pricing it would be worse. It is dropped *and* named.
    """
    result = set_itinerary_day(1, ["Kandy Lake walk", "Helicopter tour"], kandy)
    assert result["ignored_unknown_names"] == ["Helicopter tour"]
    assert len(result["activities"]) == 1


def test_no_unknown_key_when_everything_matched(kandy):
    result = set_itinerary_day(1, ["Kandy Lake walk"], kandy)
    assert "ignored_unknown_names" not in result


def test_day_cost_is_the_tools_own_arithmetic(kandy):
    """The prices come from the shortlist, not from the caller."""
    result = set_itinerary_day(
        1, ["Temple of the Sacred Tooth Relic", "Ceylon tea factory tour, Hantana"], kandy
    )
    assert result["day_cost_usd"] == 30  # 12 + 18
    assert result["day_hours"] == 5


# --- evaluate_budget -------------------------------------------------------


def test_total_is_flight_plus_nights_plus_activities(ctx):
    save_preferences("Kandy", 3, 1000, "culture", "LHR", ctx)
    research_flights("LHR", "CMB", "2026-10-02", ctx)  # 587
    research_hotels("Kandy", ctx)
    research_activities("Kandy", "culture", ctx)
    choose_hotel("Kandy Hills Rest", ctx)  # 42 * 2 nights = 84
    set_itinerary_day(1, ["Temple of the Sacred Tooth Relic"], ctx)  # 12

    result = evaluate_budget(ctx.state)
    assert result["breakdown"] == {
        "flight_usd": 587.0,
        "hotel_usd": 84.0,
        "activities_usd": 12.0,
    }
    assert result["total_cost_usd"] == 683.0


def test_no_budget_recorded_does_not_claim_a_pass():
    """The branch that exists so the loop cannot hang on a missing budget.

    Nothing was checked, so the verdict lets the loop end, but the feedback has to
    say plainly that nothing was checked. A cheerful "within budget" here is a lie
    that reads as a pass, and it is the presenter who would have to notice.
    """
    result = evaluate_budget({})
    assert result["verdict"] == "under_budget"
    assert result["budget_usd"] == 0.0
    assert "could not be checked" in result["feedback"]
    assert "within budget" not in result["feedback"].lower()


def test_over_budget_carries_what_to_cut(kandy):
    choose_hotel("Temple View Grand", kandy)  # 168 * 2 = 336, over the 250
    set_itinerary_day(1, ["Ambuluwawa Tower day trip"], kandy)

    result = evaluate_budget(kandy.state)
    assert result["verdict"] == "over_budget"
    assert result["overspend_usd"] == result["total_cost_usd"] - 250
    assert result["most_expensive_activities"][0]["activity"] == "Ambuluwawa Tower day trip"
    assert result["cheaper_hotels"][0]["name"] == "Kandy Hills Rest"


def test_evaluate_budget_never_writes_to_state(kandy):
    """Both runtimes call this. It has to be safe to call from either."""
    choose_hotel("Kandy Hills Rest", kandy)
    set_itinerary_day(1, ["Kandy Lake walk"], kandy)
    before = {k: repr(v) for k, v in kandy.state.items()}
    evaluate_budget(kandy.state)
    assert {k: repr(v) for k, v in kandy.state.items()} == before


def test_exactly_on_budget_is_under(ctx):
    """`total > budget` is the comparison, so spending it all still passes."""
    save_preferences("Kandy", 3, 84, "culture", "none", ctx)
    research_hotels("Kandy", ctx)
    choose_hotel("Kandy Hills Rest", ctx)  # exactly 84
    assert evaluate_budget(ctx.state)["verdict"] == "under_budget"


# --- check_budget: the loop's exit condition -------------------------------


def test_under_budget_escalates(kandy):
    choose_hotel("Kandy Hills Rest", kandy)
    set_itinerary_day(1, ["Kandy Lake walk"], kandy)
    check_budget(kandy)
    assert kandy.actions.escalate is True


def test_over_budget_does_not_escalate(kandy):
    choose_hotel("Temple View Grand", kandy)
    set_itinerary_day(1, ["Ambuluwawa Tower day trip"], kandy)
    check_budget(kandy)
    assert kandy.actions.escalate is False


def test_check_budget_records_its_verdict_in_state(kandy):
    """The presenter reads these three keys. They are the only record of the check."""
    choose_hotel("Kandy Hills Rest", kandy)
    set_itinerary_day(1, ["Kandy Lake walk"], kandy)
    result = check_budget(kandy)
    assert kandy.state["total_cost_usd"] == result["total_cost_usd"]
    assert kandy.state["budget_status"] == "under_budget"
    assert kandy.state["budget_feedback"] == result["feedback"]
