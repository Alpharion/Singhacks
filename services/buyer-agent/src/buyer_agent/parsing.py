"""Objective parsing: free text to a typed ProcurementGoal.

A deterministic parser always runs. When a model is configured its structured
output is merged on top, field by field, and every merged value is re-validated
here. Anything the parser cannot establish with confidence raises rather than
guessing, because a wrong budget or meal count is a wrong purchase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import drops, ids, timeutil
from .config import Settings
from .llm import ParsedConstraints, parse_constraints
from .models import DietaryTag, Location, OptimizationPriority, ProcurementGoal

DEFAULT_MIN_RELIABILITY = 0.85
DEFAULT_PRIORITY: OptimizationPriority = "balanced"

DIETARY_PATTERNS: dict[DietaryTag, re.Pattern[str]] = {
    "vegetarian": re.compile(r"\bvegetarian\b"),
    "vegan": re.compile(r"\bvegan\b"),
    "halal": re.compile(r"\bhalal\b"),
    "kosher": re.compile(r"\bkosher\b"),
    "gluten_free": re.compile(r"\bgluten[\s-]?free\b"),
    "nut_free": re.compile(r"\bnut[\s-]?free\b"),
    "dairy_free": re.compile(r"\bdairy[\s-]?free\b"),
}

PRIORITY_PATTERNS: dict[OptimizationPriority, re.Pattern[str]] = {
    "lowest_cost": re.compile(r"\b(cheapest|lowest cost|as cheap|minimi[sz]e (?:the )?cost)\b"),
    "highest_reliability": re.compile(r"\b(most reliable|highest reliability|safest bet)\b"),
    "lowest_waste": re.compile(r"\b(least waste|lowest waste|most perishable|expiring soonest)\b"),
}

MEAL_COUNT = re.compile(r"\b(\d{1,5})\b(?=(?:\s+[a-z][a-z-]*){0,3}\s+meals?\b)", re.I)
BUDGET = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:xrp|drops)\b", re.I)
DEADLINE_CLOCK = re.compile(
    r"\b(?:by|before|no later than)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I
)
DESTINATION = re.compile(
    r"\b(?:deliver(?:ed|y)?|ship(?:ped)?|send)\s+(?:them\s+)?to\s+(?:the\s+)?([A-Z][\w'’-]*(?:\s+[A-Z][\w'’-]*)*)"
)
RELIABILITY = re.compile(r"\b(?:reliability|reliable)\D{0,20}?(\d{1,3})\s*%")


class ParseError(ValueError):
    """The request does not contain enough information to act on."""


@dataclass(frozen=True)
class ParsedRequest:
    meal_count: int
    dietary_tags: list[DietaryTag]
    destination_zone: str
    destination_address: str | None
    deadline: datetime
    max_spend_drops: int
    min_seller_reliability: float
    optimization_priority: OptimizationPriority


def _deadline_from_clock(
    hour: int,
    minute: int,
    meridiem: str | None,
    reference: datetime,
    *,
    explicit_minutes: bool = False,
) -> datetime:
    """Resolve a wall-clock phrase to an absolute UTC instant.

    A bare early hour with no am/pm marker is read as the evening, because a
    same-day surplus run asking for delivery "by 6" never means 6 in the morning.
    A 24-hour time such as "by 02:00" is taken literally.
    """
    if meridiem:
        meridiem = meridiem.lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
    elif hour < 7 and not explicit_minutes:
        hour += 12
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ParseError(f"Could not read the deadline time {hour}:{minute:02d}.")

    zone = timeutil.local_zone()
    local_reference = reference.astimezone(zone)
    candidate = local_reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_reference:
        candidate += timedelta(days=1)
    return candidate.astimezone(timeutil.UTC)


def parse_text(text: str, reference: datetime) -> ParsedRequest:
    """Deterministic extraction. Raises ParseError when a hard constraint is absent."""
    meal_match = MEAL_COUNT.search(text)
    if not meal_match:
        raise ParseError("Could not find how many meals are required.")
    meal_count = int(meal_match.group(1))
    if meal_count < 1:
        raise ParseError("Meal count must be at least 1.")

    tags: list[DietaryTag] = [
        tag for tag, pattern in DIETARY_PATTERNS.items() if pattern.search(text.lower())
    ]
    if not tags:
        raise ParseError("Could not find a dietary requirement; the contract requires at least one.")

    budget_match = BUDGET.search(text)
    if not budget_match:
        raise ParseError("Could not find a maximum spend.")
    max_spend_drops = drops.from_xrp(budget_match.group(1))
    if max_spend_drops <= 0:
        raise ParseError("Maximum spend must be greater than zero.")

    deadline_match = DEADLINE_CLOCK.search(text)
    if not deadline_match:
        raise ParseError("Could not find a delivery deadline.")
    deadline = _deadline_from_clock(
        int(deadline_match.group(1)),
        int(deadline_match.group(2) or 0),
        deadline_match.group(3),
        reference,
        explicit_minutes=deadline_match.group(2) is not None,
    )

    destination_match = DESTINATION.search(text)
    zone = destination_match.group(1).strip() if destination_match else ""
    if not zone:
        raise ParseError("Could not find a delivery destination.")

    priority: OptimizationPriority = DEFAULT_PRIORITY
    for candidate, pattern in PRIORITY_PATTERNS.items():
        if pattern.search(text.lower()):
            priority = candidate
            break

    reliability_match = RELIABILITY.search(text.lower())
    min_reliability = (
        int(reliability_match.group(1)) / 100 if reliability_match else DEFAULT_MIN_RELIABILITY
    )

    return ParsedRequest(
        meal_count=meal_count,
        dietary_tags=tags,
        destination_zone=zone,
        destination_address=None,
        deadline=deadline,
        max_spend_drops=max_spend_drops,
        min_seller_reliability=min_reliability,
        optimization_priority=priority,
    )


def _merge(base: ParsedRequest, model: ParsedConstraints, reference: datetime) -> ParsedRequest:
    """Overlay validated model output on the deterministic result."""
    meal_count = base.meal_count
    if model.meal_count and 1 <= model.meal_count <= 10000:
        meal_count = model.meal_count

    tags = base.dietary_tags
    if model.dietary_tags:
        tags = sorted(set(model.dietary_tags))

    deadline = base.deadline
    if model.deadline_local_time:
        hour, _, minute = model.deadline_local_time.partition(":")
        deadline = _deadline_from_clock(
            int(hour), int(minute), None, reference, explicit_minutes=True
        )

    max_spend_drops = base.max_spend_drops
    if model.max_spend_xrp and model.max_spend_xrp > 0:
        max_spend_drops = drops.from_xrp(model.max_spend_xrp)

    return ParsedRequest(
        meal_count=meal_count,
        dietary_tags=list(tags),
        destination_zone=(model.destination_zone or base.destination_zone).strip(),
        destination_address=model.destination_address or base.destination_address,
        deadline=deadline,
        max_spend_drops=max_spend_drops,
        min_seller_reliability=(
            model.min_seller_reliability
            if model.min_seller_reliability is not None
            else base.min_seller_reliability
        ),
        optimization_priority=model.optimization_priority or base.optimization_priority,
    )


def build_goal(
    *,
    buyer_id: str,
    request_text: str,
    wallet_policy_id: str,
    config: Settings,
    reference: datetime | None = None,
    approved_seller_ids: list[str] | None = None,
    approved_courier_ids: list[str] | None = None,
) -> ProcurementGoal:
    """Parse a request into the typed goal the rest of the agent works from."""
    reference = reference or timeutil.now()
    parsed = parse_text(request_text, reference)

    model_output = parse_constraints(request_text, config)
    if model_output is not None:
        parsed = _merge(parsed, model_output, reference)

    if parsed.deadline <= reference:
        raise ParseError("The delivery deadline has already passed.")

    return ProcurementGoal(
        goal_id=ids.unique("goal"),
        buyer_id=buyer_id,
        meal_count=parsed.meal_count,
        dietary_tags=parsed.dietary_tags,
        destination=Location(
            zone=parsed.destination_zone, address_line=parsed.destination_address
        ),
        delivery_deadline=timeutil.iso(parsed.deadline),
        max_total_spend_drops=drops.to_str(parsed.max_spend_drops),
        min_seller_reliability=parsed.min_seller_reliability,
        optimization_priority=parsed.optimization_priority,
        wallet_policy_id=wallet_policy_id,
        approved_seller_ids=approved_seller_ids,
        approved_courier_ids=approved_courier_ids,
        created_at=timeutil.iso(reference),
    )
