"""PurchaseIntent construction.

An intent is the agent's typed request to spend money: what is being bought,
from whom, for how much, under which delegated authority. It is the last thing
the agent produces before the payment boundary takes over, and it carries a
policy snapshot so the boundary can re-check the decoded x402 challenge against
the same limits the agent used.
"""

from __future__ import annotations

from datetime import datetime

from . import drops, ids, timeutil
from .models import (
    DeliveryQuote,
    FoodAllocation,
    FoodOffer,
    ProcurementGoal,
    PurchaseIntent,
)
from .policy import WalletPolicy

DEFAULT_INTENT_TTL_MINUTES = 10


def food_intent(
    *,
    run_id: str,
    goal: ProcurementGoal,
    offer: FoodOffer,
    allocation: FoodAllocation,
    policy: WalletPolicy,
    rationale: str,
    now: datetime,
    ttl_minutes: int = DEFAULT_INTENT_TTL_MINUTES,
) -> PurchaseIntent:
    expiry = min(
        timeutil.plus(now, minutes=ttl_minutes),
        timeutil.parse(offer.pickup_window.end),
    )
    return PurchaseIntent(
        intent_id=ids.identifier("intent", allocation.offer_id),
        run_id=run_id,
        goal_id=goal.goal_id,
        resource_type="food_reservation",
        provider_id=offer.seller_id,
        resource_id=offer.offer_id,
        target_url=offer.reservation_endpoint,
        quantity=allocation.quantity,
        amount_drops=allocation.line_total_drops,
        pay_to=offer.pay_to,
        network="xrpl:1",
        asset="XRP",
        invoice_id=ids.invoice_id(run_id, offer.offer_id),
        idempotency_key=ids.idempotency_key(run_id, offer.offer_id),
        expires_at=timeutil.iso(expiry),
        rationale=rationale,
        policy_snapshot=policy.snapshot(),
    )


def delivery_intent(
    *,
    run_id: str,
    goal: ProcurementGoal,
    quote: DeliveryQuote,
    policy: WalletPolicy,
    rationale: str,
    now: datetime,
    ttl_minutes: int = DEFAULT_INTENT_TTL_MINUTES,
) -> PurchaseIntent:
    expiry = min(
        timeutil.plus(now, minutes=ttl_minutes), timeutil.parse(quote.valid_until)
    )
    return PurchaseIntent(
        intent_id=ids.identifier("intent", quote.quote_id),
        run_id=run_id,
        goal_id=goal.goal_id,
        resource_type="delivery_booking",
        provider_id=quote.provider_id,
        resource_id=quote.quote_id,
        target_url=quote.booking_endpoint,
        quantity=None,
        amount_drops=quote.price_drops,
        pay_to=quote.pay_to,
        network="xrpl:1",
        asset="XRP",
        invoice_id=ids.invoice_id(run_id, quote.quote_id),
        idempotency_key=ids.idempotency_key(run_id, quote.quote_id),
        expires_at=timeutil.iso(expiry),
        rationale=rationale,
        policy_snapshot=policy.snapshot(),
    )


def describe(intent: PurchaseIntent) -> str:
    """Short human line for the timeline. Never includes an address or a seed."""
    what = "reservation" if intent.resource_type == "food_reservation" else "delivery"
    quantity = f"{intent.quantity} meals " if intent.quantity else ""
    return (
        f"{drops.to_xrp_label(intent.amount_drops)} for a {quantity}{what} "
        f"from {intent.provider_id}"
    )
