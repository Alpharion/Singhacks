from __future__ import annotations

import pytest

from buyer_agent import drops, timeutil
from buyer_agent.config import Settings
from buyer_agent.parsing import ParseError, build_goal, parse_text

from conftest import DEMO_NOW, load_fixture

DEMO_TEXT = load_fixture("procurement-request.json")["requestText"]


def test_parses_the_demo_request():
    parsed = parse_text(DEMO_TEXT, DEMO_NOW)
    assert parsed.meal_count == 100
    assert parsed.dietary_tags == ["vegetarian"]
    assert parsed.destination_zone == "Queenstown"
    assert parsed.max_spend_drops == 120_000_000
    assert parsed.optimization_priority == "balanced"
    assert parsed.min_seller_reliability == 0.85


def test_six_pm_resolves_to_the_buyers_evening(monkeypatch):
    monkeypatch.setenv("SURPLUSFLOW_TIMEZONE", "Asia/Singapore")
    parsed = parse_text(DEMO_TEXT, DEMO_NOW)
    # 6 PM in Singapore on the fixture's demo day is 10:00 UTC.
    assert timeutil.iso(parsed.deadline) == "2026-09-05T10:00:00Z"


def test_twenty_four_hour_time_is_taken_literally(monkeypatch):
    monkeypatch.setenv("SURPLUSFLOW_TIMEZONE", "UTC")
    parsed = parse_text("Need 20 vegan meals delivered to Bedok by 02:30 for 40 XRP", DEMO_NOW)
    assert timeutil.iso(parsed.deadline) == "2026-09-06T02:30:00Z"


def test_soft_priority_is_recognised():
    text = "Get the cheapest 50 halal meals delivered to Bedok by 8 PM for under 60 XRP"
    assert parse_text(text, DEMO_NOW).optimization_priority == "lowest_cost"


@pytest.mark.parametrize(
    "text",
    [
        "Deliver vegetarian meals to Queenstown by 6 PM for 120 XRP",  # no quantity
        "Secure 100 meals delivered to Queenstown by 6 PM for 120 XRP",  # no diet
        "Secure 100 vegetarian meals delivered to Queenstown by 6 PM",  # no budget
        "Secure 100 vegetarian meals delivered to Queenstown for 120 XRP",  # no deadline
    ],
)
def test_missing_hard_constraints_are_refused(text):
    with pytest.raises(ParseError):
        parse_text(text, DEMO_NOW)


def test_goal_is_built_without_a_model(monkeypatch):
    monkeypatch.setenv("SURPLUSFLOW_TIMEZONE", "Asia/Singapore")
    goal = build_goal(
        buyer_id="buyer_kitchen_001",
        request_text=DEMO_TEXT,
        wallet_policy_id="policy_demo_001",
        config=Settings(openai_api_key="", openai_model=""),
        reference=DEMO_NOW,
    )
    assert goal.meal_count == 100
    assert drops.to_int(goal.max_total_spend_drops) == 120_000_000
    assert goal.delivery_deadline == "2026-09-05T10:00:00Z"
    assert goal.goal_id.startswith("goal_")


def test_a_deadline_already_past_today_rolls_to_tomorrow(monkeypatch):
    """"By 6 PM" asked at 7 PM means tomorrow evening, not an impossible deadline."""
    monkeypatch.setenv("SURPLUSFLOW_TIMEZONE", "Asia/Singapore")
    goal = build_goal(
        buyer_id="buyer_kitchen_001",
        request_text=DEMO_TEXT,
        wallet_policy_id="policy_demo_001",
        config=Settings(openai_api_key="", openai_model=""),
        # 12:00 UTC is 8 PM in Singapore, past the 6 PM the text asks for.
        reference=timeutil.parse("2026-09-05T12:00:00Z"),
    )
    assert goal.delivery_deadline == "2026-09-06T10:00:00Z"
