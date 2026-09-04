from __future__ import annotations

from buyer_agent import timeutil
from buyer_agent.filtering import filter_offers, filter_quotes


def rejection_for(rejections, option_id):
    return next(item for item in rejections if item.option_id == option_id)


def test_non_vegetarian_offer_is_rejected(goal, offers, now):
    eligible, rejections = filter_offers(goal, offers, now)
    assert {offer.offer_id for offer in eligible} == {"offer_bakery_001", "offer_hotel_001"}
    reasons = rejection_for(rejections, "offer_grill_001").reasons
    assert any("vegetarian" in reason for reason in reasons)


def test_expired_food_is_rejected(goal, offers, now):
    stale = offers[0].model_copy(update={"expires_at": "2026-09-05T05:00:00Z"})
    eligible, rejections = filter_offers(goal, [stale], now)
    assert eligible == []
    assert any("expired" in reason.lower() for reason in rejections[0].reasons)


def test_unreliable_seller_is_rejected(goal, offers, now):
    flaky = offers[0].model_copy(update={"reliability_score": 0.5})
    eligible, rejections = filter_offers(goal, [flaky], now)
    assert eligible == []
    assert any("reliability" in reason for reason in rejections[0].reasons)


def test_unapproved_seller_is_rejected(goal, offers, now):
    restricted = goal.model_copy(update={"approved_seller_ids": ["seller_hotel_001"]})
    eligible, _ = filter_offers(restricted, offers, now)
    assert {offer.seller_id for offer in eligible} == {"seller_hotel_001"}


def test_unavailable_courier_is_rejected(goal, quotes, now):
    eligible, rejections = filter_quotes(goal, quotes, now, meals_required=goal.meal_count)
    assert [quote.quote_id for quote in eligible] == ["quote_fast_001"]
    assert any("unavailable" in reason for reason in rejection_for(rejections, "quote_economy_001").reasons)


def test_courier_that_misses_the_deadline_is_rejected(goal, quotes, now):
    late = quotes[0].model_copy(update={"delivery_eta": "2026-09-05T11:00:00Z"})
    eligible, rejections = filter_quotes(goal, [late], now, meals_required=goal.meal_count)
    assert eligible == []
    assert any("deadline" in reason for reason in rejections[0].reasons)


def test_courier_without_capacity_is_rejected(goal, quotes, now):
    small = quotes[0].model_copy(update={"capacity_meals": 10})
    eligible, rejections = filter_quotes(goal, [small], now, meals_required=goal.meal_count)
    assert eligible == []
    assert any("Capacity" in reason for reason in rejections[0].reasons)


def test_expired_quote_is_rejected(goal, quotes, now):
    stale = quotes[0].model_copy(update={"valid_until": "2026-09-05T05:59:00Z"})
    eligible, rejections = filter_quotes(goal, [stale], now, meals_required=goal.meal_count)
    assert eligible == []
    assert any("expired" in reason.lower() for reason in rejections[0].reasons)
