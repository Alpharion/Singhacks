"""Pydantic v2 models mirroring Contract Freeze v1.0.0.

Field names are snake_case in Python and camelCase on the wire. Timestamps are
kept as validated ISO-8601 strings rather than ``datetime`` so that fixtures
round-trip byte-for-byte; use ``buyer_agent.timeutil`` to move between the two.
XRP amounts are always integer strings in drops.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
Drops = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$")]
PositiveDrops = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]
XrplAddress = Annotated[str, StringConstraints(pattern=r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")]
TransactionHash = Annotated[str, StringConstraints(pattern=r"^[A-Fa-f0-9]{64}$")]
OpaqueKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{8,128}$")]
Timestamp = Annotated[
    str,
    StringConstraints(
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
    ),
]

DietaryTag = Literal[
    "vegetarian", "vegan", "halal", "kosher", "gluten_free", "nut_free", "dairy_free"
]
ResourceType = Literal["food_reservation", "delivery_booking"]
RunStatus = Literal[
    "queued",
    "parsing",
    "discovering",
    "planning",
    "awaiting_payment",
    "reserving",
    "replanning",
    "fulfilled",
    "failed",
    "cancelled",
]
OptimizationPriority = Literal[
    "balanced", "lowest_cost", "highest_reliability", "lowest_waste"
]
OfferStatus = Literal["available", "reserved", "sold_out", "expired", "withdrawn"]
QuoteStatus = Literal["available", "unavailable", "expired"]
DecisionType = Literal[
    "reject_offer", "select_plan", "authorize_payment", "replan", "stop"
]
EventType = Literal[
    "goal_parsed",
    "offers_discovered",
    "offer_rejected",
    "plans_built",
    "plan_selected",
    "provider_failed",
    "replanning_started",
    "payment_required",
    "payment_authorized",
    "payment_settled",
    "reservation_confirmed",
    "delivery_confirmed",
    "run_fulfilled",
    "run_failed",
]
ErrorCode = Literal[
    "invalid_request",
    "not_found",
    "offer_expired",
    "offer_sold_out",
    "quote_expired",
    "provider_unavailable",
    "budget_exceeded",
    "policy_rejected",
    "payment_required",
    "payment_failed",
    "payment_timeout",
    "payment_replayed",
    "invoice_mismatch",
    "network_mismatch",
    "internal_error",
]

NETWORK: Literal["xrpl:1"] = "xrpl:1"
ASSET: Literal["XRP"] = "XRP"


class Contract(BaseModel):
    """Base for every frozen contract type: camelCase wire names, no extras."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    def wire(self) -> dict[str, Any]:
        """Serialize exactly as the contract expects (camelCase, no nulls)."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class Location(Contract):
    zone: str
    address_line: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class TimeWindow(Contract):
    start: Timestamp
    end: Timestamp


class ApiError(Contract):
    error: ErrorCode
    message: str
    retryable: bool
    request_id: str
    details: dict[str, Any] | None = None


class ProcurementRequest(Contract):
    buyer_id: Identifier
    request_text: str
    wallet_policy_id: Identifier


class ProcurementGoal(Contract):
    goal_id: Identifier
    buyer_id: Identifier
    meal_count: int
    dietary_tags: list[DietaryTag]
    destination: Location
    delivery_deadline: Timestamp
    max_total_spend_drops: PositiveDrops
    min_seller_reliability: float
    optimization_priority: OptimizationPriority
    wallet_policy_id: Identifier
    approved_seller_ids: list[Identifier] | None = None
    approved_courier_ids: list[Identifier] | None = None
    created_at: Timestamp


class FoodOffer(Contract):
    offer_id: Identifier
    seller_id: Identifier
    seller_name: str
    reservation_endpoint: str
    pay_to: XrplAddress
    title: str
    description: str | None = None
    dietary_tags: list[DietaryTag]
    quantity_available: int
    unit_price_drops: PositiveDrops
    location: Location
    prepared_at: Timestamp
    expires_at: Timestamp
    pickup_window: TimeWindow
    reliability_score: float
    status: OfferStatus
    updated_at: Timestamp


class FoodOffersResponse(Contract):
    offers: list[FoodOffer]
    generated_at: Timestamp


class DeliveryQuote(Contract):
    quote_id: Identifier
    provider_id: Identifier
    provider_name: str
    booking_endpoint: str
    pay_to: XrplAddress
    pickup_seller_ids: list[Identifier]
    destination_zone: str
    capacity_meals: int
    price_drops: PositiveDrops
    pickup_eta: Timestamp
    delivery_eta: Timestamp
    valid_until: Timestamp
    reliability_score: float
    status: QuoteStatus


class DeliveryQuotesResponse(Contract):
    quotes: list[DeliveryQuote]
    generated_at: Timestamp


class Pickup(Contract):
    seller_id: Identifier
    offer_id: Identifier
    quantity: int
    location: Location


class DeliveryQuoteRequest(Contract):
    goal_id: Identifier
    pickups: list[Pickup]
    destination: Location
    delivery_deadline: Timestamp


class FoodAllocation(Contract):
    seller_id: Identifier
    offer_id: Identifier
    quantity: int
    unit_price_drops: PositiveDrops
    line_total_drops: PositiveDrops
    reliability_score: float


class ProcurementPlan(Contract):
    plan_id: Identifier
    goal_id: Identifier
    food_allocations: list[FoodAllocation]
    delivery_quote_id: Identifier
    total_meals: int
    food_cost_drops: PositiveDrops
    delivery_cost_drops: Drops
    total_cost_drops: PositiveDrops
    expected_delivery_at: Timestamp
    valid_until: Timestamp
    risk_score: float
    feasible: bool
    rejection_reasons: list[str]


class PolicySnapshot(Contract):
    wallet_policy_id: Identifier
    max_order_spend_drops: PositiveDrops
    max_transaction_spend_drops: PositiveDrops
    allowed_payees: list[XrplAddress]


class PurchaseIntent(Contract):
    intent_id: Identifier
    run_id: Identifier
    goal_id: Identifier
    resource_type: ResourceType
    provider_id: Identifier
    resource_id: Identifier
    target_url: str
    quantity: int | None = None
    amount_drops: PositiveDrops
    pay_to: XrplAddress
    network: Literal["xrpl:1"]
    asset: Literal["XRP"]
    invoice_id: OpaqueKey
    idempotency_key: OpaqueKey
    expires_at: Timestamp
    rationale: str
    policy_snapshot: PolicySnapshot


class PaymentRequirementExtra(Contract):
    invoice_id: OpaqueKey
    source_tag: int
    destination_tag: int | None = None


class PaymentAccept(Contract):
    scheme: Literal["exact"]
    network: Literal["xrpl:1"]
    asset: Literal["XRP"]
    pay_to: XrplAddress
    amount: PositiveDrops
    max_timeout_seconds: int
    extra: PaymentRequirementExtra


class PaymentRequirement(Contract):
    x402_version: Literal[2]
    accepts: list[PaymentAccept]


class PaymentReceipt(Contract):
    success: Literal[True]
    transaction: TransactionHash
    network: Literal["xrpl:1"]
    payer: XrplAddress
    payee: XrplAddress
    amount_drops: PositiveDrops
    invoice_id: OpaqueKey
    validated: Literal[True]
    validated_at: Timestamp
    explorer_url: str


class Reservation(Contract):
    reservation_id: Identifier
    run_id: Identifier
    seller_id: Identifier
    offer_id: Identifier
    quantity: int
    status: Literal["confirmed", "expired", "cancelled", "failed"]
    pickup_window: TimeWindow
    pickup_token: str | None = None
    payment_receipt: PaymentReceipt
    created_at: Timestamp
    expires_at: Timestamp


class DeliveryBooking(Contract):
    booking_id: Identifier
    run_id: Identifier
    provider_id: Identifier
    quote_id: Identifier
    status: Literal["confirmed", "collecting", "in_transit", "delivered", "cancelled", "failed"]
    pickup_eta: Timestamp
    delivery_eta: Timestamp
    tracking_code: str
    payment_receipt: PaymentReceipt
    created_at: Timestamp


class RejectedAlternative(Contract):
    option_id: Identifier
    reasons: list[str]


class AgentDecision(Contract):
    decision_id: Identifier
    run_id: Identifier
    decision_type: DecisionType
    objective: str
    selected_option_id: Identifier | None = None
    alternatives_considered: list[Identifier]
    reasons: list[str]
    rejected_alternatives: list[RejectedAlternative]
    remaining_budget_drops: Drops
    wallet_policy_id: Identifier
    transaction_hash: TransactionHash | None = None
    created_at: Timestamp


class RunEvent(Contract):
    sequence: int
    event_type: EventType
    message: str
    related_id: Identifier | None = None
    created_at: Timestamp


class Spend(Contract):
    food_drops: Drops
    delivery_drops: Drops
    total_drops: Drops
    remaining_drops: Drops


class AgentRun(Contract):
    run_id: Identifier
    status: RunStatus
    goal: ProcurementGoal
    offers: list[FoodOffer]
    delivery_quotes: list[DeliveryQuote]
    plans: list[ProcurementPlan]
    selected_plan_id: Identifier | None = None
    decisions: list[AgentDecision]
    reservations: list[Reservation]
    delivery_bookings: list[DeliveryBooking]
    spend: Spend
    events: list[RunEvent]
    failure: ApiError | None = None
    created_at: Timestamp
    updated_at: Timestamp
