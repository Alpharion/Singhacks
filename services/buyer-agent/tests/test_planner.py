from __future__ import annotations

from buyer_agent import drops
from buyer_agent.filtering import filter_offers, filter_quotes
from buyer_agent.planner import build_bundles, build_plans

from conftest import load_fixture

SELECTED_PLAN = load_fixture("selected-plan.json")


def eligible(goal, offers, quotes, now):
    ok_offers, _ = filter_offers(goal, offers, now)
    ok_quotes, _ = filter_quotes(goal, quotes, now, meals_required=goal.meal_count)
    return ok_offers, ok_quotes


def test_no_single_seller_can_cover_the_order(goal, offers, now):
    ok_offers, _ = filter_offers(goal, offers, now)
    singles = [
        bundle
        for bundle in build_bundles(ok_offers, goal.meal_count, now)
        if len(bundle.seller_ids) == 1
    ]
    assert singles, "expected single-seller bundles to be considered"
    assert all(bundle.meals < goal.meal_count for bundle in singles)


def test_selected_plan_matches_the_frozen_fixture(goal, offers, quotes, now):
    ok_offers, ok_quotes = eligible(goal, offers, quotes, now)
    plans = build_plans(goal, ok_offers, ok_quotes, now)
    best = next(plan for plan in plans if plan.feasible)

    assert best.total_meals == SELECTED_PLAN["totalMeals"]
    assert best.food_cost_drops == SELECTED_PLAN["foodCostDrops"]
    assert best.delivery_cost_drops == SELECTED_PLAN["deliveryCostDrops"]
    assert best.total_cost_drops == SELECTED_PLAN["totalCostDrops"]
    assert best.delivery_quote_id == SELECTED_PLAN["deliveryQuoteId"]
    assert [
        (item.offer_id, item.quantity, item.line_total_drops)
        for item in best.food_allocations
    ] == [
        (item["offerId"], item["quantity"], item["lineTotalDrops"])
        for item in SELECTED_PLAN["foodAllocations"]
    ]


def test_a_cheaper_and_a_balanced_split_are_both_offered(goal, offers, quotes, now):
    ok_offers, ok_quotes = eligible(goal, offers, quotes, now)
    feasible = [plan for plan in build_plans(goal, ok_offers, ok_quotes, now) if plan.feasible]
    splits = {
        tuple(sorted((item.offer_id, item.quantity) for item in plan.food_allocations))
        for plan in feasible
    }
    assert (("offer_bakery_001", 60), ("offer_hotel_001", 40)) in splits
    assert (("offer_bakery_001", 50), ("offer_hotel_001", 50)) in splits


def test_line_totals_and_grand_total_reconcile(goal, offers, quotes, now):
    ok_offers, ok_quotes = eligible(goal, offers, quotes, now)
    for plan in build_plans(goal, ok_offers, ok_quotes, now):
        lines = drops.total(item.line_total_drops for item in plan.food_allocations)
        assert lines == drops.to_int(plan.food_cost_drops)
        assert lines + drops.to_int(plan.delivery_cost_drops) == drops.to_int(
            plan.total_cost_drops
        )
        assert sum(item.quantity for item in plan.food_allocations) == plan.total_meals


def test_short_plans_are_marked_infeasible_with_a_reason(goal, offers, quotes, now):
    ok_offers, ok_quotes = eligible(goal, offers, quotes, now)
    plans = build_plans(goal, ok_offers, ok_quotes, now)
    short = [plan for plan in plans if plan.total_meals < goal.meal_count]
    assert short
    for plan in short:
        assert not plan.feasible
        assert any("Covers only" in reason for reason in plan.rejection_reasons)


def test_an_unaffordable_plan_is_marked_infeasible(goal, offers, quotes, now):
    ok_offers, ok_quotes = eligible(goal, offers, quotes, now)
    plans = build_plans(goal, ok_offers, ok_quotes, now, budget_drops=50_000_000)
    assert all(not plan.feasible for plan in plans)
    assert any(
        "exceeds the remaining" in reason
        for plan in plans
        for reason in plan.rejection_reasons
    )


def test_lowest_cost_priority_prefers_the_cheaper_split(goal, offers, quotes, now):
    ok_offers, ok_quotes = eligible(goal, offers, quotes, now)
    cheap_goal = goal.model_copy(update={"optimization_priority": "lowest_cost"})
    plans = build_plans(cheap_goal, ok_offers, ok_quotes, now)
    feasible = [plan for plan in plans if plan.feasible]
    assert drops.to_int(feasible[0].total_cost_drops) <= drops.to_int(
        feasible[1].total_cost_drops
    )


def test_planning_is_deterministic(goal, offers, quotes, now):
    ok_offers, ok_quotes = eligible(goal, offers, quotes, now)
    first = build_plans(goal, ok_offers, ok_quotes, now)
    second = build_plans(goal, ok_offers, ok_quotes, now)
    assert [plan.plan_id for plan in first] == [plan.plan_id for plan in second]


def test_courier_must_cover_every_committed_seller(goal, offers, quotes, now):
    ok_offers, ok_quotes = eligible(goal, offers, quotes, now)
    plans = build_plans(
        goal,
        ok_offers,
        ok_quotes,
        now,
        committed_seller_ids=frozenset({"seller_nowhere_001"}),
    )
    assert plans == []
