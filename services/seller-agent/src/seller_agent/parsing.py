"""One sentence from a seller to a typed `SellingGoal`.

Mirrors the buyer agent's parser, including its refusal to guess: a floor price
the seller did not state is not a floor, and inventing one would risk selling
their food under cost. Anything missing is an error, never a default.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from . import drops, ids, timeutil
from .models import DietaryTag, SellingGoal

QUANTITY = re.compile(r"\b(\d{1,5})\b(?=(?:\s+[a-z][a-z-]*){0,4}\s+(?:meals?|boxes|portions|units)\b)", re.I)

#: "no less than 1.20 XRP", "floor of 1.2 XRP", "at least 1.20 XRP each".
FLOOR = re.compile(
    r"\b(?:no\s+less\s+than|not\s+below|at\s+least|floor(?:\s+of)?|minimum(?:\s+of)?)\s+"
    r"(\d+(?:\.\d+)?)\s*xrp",
    re.I,
)
#: An explicit opening ask: "asking 2 XRP", "start at 2.5 XRP".
OPENING = re.compile(
    r"\b(?:asking|ask|start(?:ing)?(?:\s+at)?|list(?:ed)?\s+at)\s+(\d+(?:\.\d+)?)\s*xrp",
    re.I,
)
DEADLINE_CLOCK = re.compile(
    r"\b(?:by|before|until|collection\s+by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I
)

DIETARY_PATTERNS: dict[DietaryTag, re.Pattern[str]] = {
    "vegetarian": re.compile(r"\bvegetarian\b"),
    "vegan": re.compile(r"\bvegan\b"),
    "halal": re.compile(r"\bhalal\b"),
    "kosher": re.compile(r"\bkosher\b"),
    "nut_free": re.compile(r"\bnut[\s-]?free\b"),
    "gluten_free": re.compile(r"\bgluten[\s-]?free\b"),
}

#: What the agent opens at when the seller states only a floor. A listing that
#: opens at its floor has delegated nothing - there is no band to work in.
DEFAULT_OPENING_MULTIPLIER = 1.6


class ParseError(ValueError):
    """The sentence is missing something the agent refuses to invent."""


def _deadline_from_clock(
    hour: int, minute: int, meridiem: str | None, reference: datetime, *, explicit_minutes: bool
) -> datetime:
    if meridiem:
        meridiem = meridiem.lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
    elif hour < 7 and not explicit_minutes:
        # Surplus food is collected in the evening, not at dawn.
        hour += 12

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ParseError(f"Could not read the collection time {hour}:{minute:02d}.")

    zone = timeutil.local_zone()
    local_reference = reference.astimezone(zone)
    candidate = local_reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_reference:
        candidate += timedelta(days=1)
    return candidate.astimezone(timeutil.UTC)


def _describe(text: str) -> str:
    """A short label for the listing, taken from the seller's own words."""
    cleaned = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return cleaned[:200]


def build_goal(*, seller_id: str, request_text: str, now: datetime | None = None) -> SellingGoal:
    reference = now or timeutil.now()

    quantity_match = QUANTITY.search(request_text)
    if not quantity_match:
        raise ParseError("Could not find how many units are for sale.")
    quantity = int(quantity_match.group(1))
    if quantity < 1:
        raise ParseError("Quantity must be at least 1.")

    floor_match = FLOOR.search(request_text)
    if not floor_match:
        raise ParseError(
            "Could not find a floor price. State the lowest unit price you will "
            'accept, for example "no less than 1.20 XRP each".'
        )
    floor_drops = drops.from_xrp(floor_match.group(1))
    if floor_drops <= 0:
        raise ParseError("The floor price must be greater than zero.")

    deadline_match = DEADLINE_CLOCK.search(request_text)
    if not deadline_match:
        raise ParseError("Could not find a collection deadline.")
    deadline = _deadline_from_clock(
        int(deadline_match.group(1)),
        int(deadline_match.group(2) or 0),
        deadline_match.group(3),
        reference,
        explicit_minutes=deadline_match.group(2) is not None,
    )

    opening_match = OPENING.search(request_text)
    if opening_match:
        opening_drops = drops.from_xrp(opening_match.group(1))
        if opening_drops < floor_drops:
            raise ParseError(
                "The opening price is below the floor price; the agent would have "
                "nothing to work with."
            )
    else:
        opening_drops = int(floor_drops * DEFAULT_OPENING_MULTIPLIER)

    tags = [tag for tag, pattern in DIETARY_PATTERNS.items() if pattern.search(request_text.lower())]

    return SellingGoal(
        goal_id=ids.unique("goal"),
        seller_id=seller_id,
        description=_describe(request_text),
        quantity=quantity,
        dietary_tags=tags,
        collection_deadline=timeutil.iso(deadline),
        floor_unit_price_drops=drops.to_str(floor_drops),
        opening_unit_price_drops=drops.to_str(opening_drops),
    )
