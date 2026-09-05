"""Hard filters.

These are rules, not preferences, and they are never delegated to the language
model. An offer that fails any of them is removed from consideration with a
reason the buyer can read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import timeutil
from .models import DeliveryQuote, FoodOffer, ProcurementGoal


@dataclass(frozen=True)
class Rejection:
    option_id: str
    reasons: list[str]


def filter_offers(
    goal: ProcurementGoal, offers: list[FoodOffer], now: datetime
) -> tuple[list[FoodOffer], list[Rejection]]:
    """Split discovered offers into what may be bought and what may not."""
    deadline = timeutil.parse(goal.delivery_deadline)
    required = set(goal.dietary_tags)
    approved = set(goal.approved_seller_ids or [])

    eligible: list[FoodOffer] = []
    rejections: list[Rejection] = []

    for offer in offers:
        reasons: list[str] = []
        expires_at = timeutil.parse(offer.expires_at)
        pickup_start = timeutil.parse(offer.pickup_window.start)
        pickup_end = timeutil.parse(offer.pickup_window.end)

        if offer.status != "available":
            reasons.append(f"Offer is {offer.status.replace('_', ' ')}.")
        if offer.quantity_available < 1:
            reasons.append("No portions remain on this offer.")
        if expires_at <= now:
            reasons.append(f"Food expired at {offer.expires_at}.")
        if expires_at < pickup_start:
            reasons.append("Food expires before its own pickup window opens.")
        if pickup_end <= now:
            reasons.append("Pickup window has already closed.")
        if pickup_start >= deadline:
            reasons.append("Pickup cannot start before the delivery deadline.")

        missing = sorted(required - set(offer.dietary_tags))
        if missing:
            reasons.append(
                "Missing required dietary tag: " + ", ".join(tag.replace("_", " ") for tag in missing) + "."
            )
        if offer.reliability_score < goal.min_seller_reliability:
            reasons.append(
                f"Seller reliability {offer.reliability_score:.2f} is below the "
                f"{goal.min_seller_reliability:.2f} floor."
            )
        if approved and offer.seller_id not in approved:
            reasons.append(f"Seller {offer.seller_id} is not on the approved seller list.")

        if reasons:
            rejections.append(Rejection(option_id=offer.offer_id, reasons=reasons))
        else:
            eligible.append(offer)

    return eligible, rejections


def filter_quotes(
    goal: ProcurementGoal,
    quotes: list[DeliveryQuote],
    now: datetime,
    *,
    meals_required: int,
) -> tuple[list[DeliveryQuote], list[Rejection]]:
    """Same treatment for courier quotes. Pickup coverage is checked per plan."""
    deadline = timeutil.parse(goal.delivery_deadline)
    approved = set(goal.approved_courier_ids or [])
    destination = goal.destination.zone.strip().lower()

    eligible: list[DeliveryQuote] = []
    rejections: list[Rejection] = []

    for quote in quotes:
        reasons: list[str] = []
        if quote.status != "available":
            reasons.append(f"Courier quote is {quote.status}.")
        if timeutil.parse(quote.valid_until) <= now:
            reasons.append(f"Quote expired at {quote.valid_until}.")
        if timeutil.parse(quote.delivery_eta) > deadline:
            reasons.append(
                f"Arrives {quote.delivery_eta}, after the {goal.delivery_deadline} deadline."
            )
        if quote.capacity_meals < meals_required:
            reasons.append(
                f"Capacity {quote.capacity_meals} is below the {meals_required} meals required."
            )
        if quote.destination_zone.strip().lower() != destination:
            reasons.append(
                f"Quote delivers to {quote.destination_zone}, not {goal.destination.zone}."
            )
        if approved and quote.provider_id not in approved:
            reasons.append(f"Courier {quote.provider_id} is not on the approved courier list.")

        if reasons:
            rejections.append(Rejection(option_id=quote.quote_id, reasons=reasons))
        else:
            eligible.append(quote)

    return eligible, rejections
