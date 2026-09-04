"""Pydantic v2 models mirroring `packages/contracts/schemas/*.schema.json`.

Field names are snake_case in Python and serialize to the frozen camelCase
wire format via `alias_generator=to_camel`. Keep every field, enum value,
and pattern in lockstep with the JSON Schemas -- this module does not
introduce new shapes, it mirrors the frozen ones.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
Drops = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$")]
PositiveDrops = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]
XrplAddress = Annotated[str, StringConstraints(pattern=r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")]
TransactionHash = Annotated[str, StringConstraints(pattern=r"^[A-Fa-f0-9]{64}$")]
IdempotencyKeyStr = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{8,128}$")]
PickupToken = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{12,256}$")]
TrackingCode = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")]

DietaryTag = Literal[
    "vegetarian", "vegan", "halal", "kosher", "gluten_free", "nut_free", "dairy_free"
]
ResourceType = Literal["food_reservation", "delivery_booking"]
OfferStatus = Literal["available", "reserved", "sold_out", "expired", "withdrawn"]
QuoteStatus = Literal["available", "unavailable", "expired"]
ReservationStatus = Literal["confirmed", "expired", "cancelled", "failed"]
BookingStatus = Literal["confirmed", "collecting", "in_transit", "delivered", "cancelled", "failed"]
ApiErrorCode = Literal[
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


class ContractModel(BaseModel):
    """Base model producing frozen camelCase field names on the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class Location(ContractModel):
    zone: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    address_line: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class TimeWindow(ContractModel):
    start: datetime
    end: datetime


class FoodOffer(ContractModel):
    offer_id: Identifier
    seller_id: Identifier
    seller_name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    reservation_endpoint: str
    pay_to: XrplAddress
    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    description: Annotated[str, StringConstraints(max_length=500)] | None = None
    dietary_tags: list[DietaryTag] = Field(min_length=1)
    quantity_available: int = Field(ge=0, le=10000)
    unit_price_drops: PositiveDrops
    location: Location
    prepared_at: datetime
    expires_at: datetime
    pickup_window: TimeWindow
    reliability_score: float = Field(ge=0, le=1)
    status: OfferStatus
    updated_at: datetime


class FoodOffersResponse(ContractModel):
    offers: list[FoodOffer]
    generated_at: datetime


class DeliveryQuote(ContractModel):
    quote_id: Identifier
    provider_id: Identifier
    provider_name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    booking_endpoint: str
    pay_to: XrplAddress
    pickup_seller_ids: list[Identifier] = Field(min_length=1)
    destination_zone: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    capacity_meals: int = Field(ge=1, le=10000)
    price_drops: PositiveDrops
    pickup_eta: datetime
    delivery_eta: datetime
    valid_until: datetime
    reliability_score: float = Field(ge=0, le=1)
    status: QuoteStatus


class DeliveryQuotesResponse(ContractModel):
    quotes: list[DeliveryQuote]
    generated_at: datetime


class DeliveryPickup(ContractModel):
    seller_id: Identifier
    offer_id: Identifier
    quantity: int = Field(ge=1)
    location: Location


class DeliveryQuoteRequest(ContractModel):
    goal_id: Identifier
    pickups: list[DeliveryPickup] = Field(min_length=1)
    destination: Location
    delivery_deadline: datetime


class PolicySnapshot(ContractModel):
    wallet_policy_id: Identifier
    max_order_spend_drops: PositiveDrops
    max_transaction_spend_drops: PositiveDrops
    allowed_payees: list[XrplAddress] = Field(min_length=1)


class PurchaseIntent(ContractModel):
    intent_id: Identifier
    run_id: Identifier
    goal_id: Identifier
    resource_type: ResourceType
    provider_id: Identifier
    resource_id: Identifier
    target_url: str
    quantity: int | None = Field(default=None, ge=1)
    amount_drops: PositiveDrops
    pay_to: XrplAddress
    network: Literal["xrpl:1"]
    asset: Literal["XRP"]
    invoice_id: IdempotencyKeyStr
    idempotency_key: IdempotencyKeyStr
    expires_at: datetime
    rationale: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    policy_snapshot: PolicySnapshot


class PaymentReceipt(ContractModel):
    success: Literal[True]
    transaction: TransactionHash
    network: Literal["xrpl:1"]
    payer: XrplAddress
    payee: XrplAddress
    amount_drops: PositiveDrops
    invoice_id: IdempotencyKeyStr
    validated: Literal[True]
    validated_at: datetime
    explorer_url: str


class Reservation(ContractModel):
    reservation_id: Identifier
    run_id: Identifier
    seller_id: Identifier
    offer_id: Identifier
    quantity: int = Field(ge=1)
    status: ReservationStatus
    pickup_window: TimeWindow
    pickup_token: PickupToken | None = None
    payment_receipt: PaymentReceipt
    created_at: datetime
    expires_at: datetime


class DeliveryBooking(ContractModel):
    booking_id: Identifier
    run_id: Identifier
    provider_id: Identifier
    quote_id: Identifier
    status: BookingStatus
    pickup_eta: datetime
    delivery_eta: datetime
    tracking_code: TrackingCode
    payment_receipt: PaymentReceipt
    created_at: datetime


class PaymentRequirementExtra(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    invoice_id: IdempotencyKeyStr = Field(alias="invoiceId")
    source_tag: int = Field(alias="sourceTag", ge=0, le=4294967295)
    destination_tag: int | None = Field(default=None, alias="destinationTag", ge=0, le=4294967295)


class PaymentRequirementAccept(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    scheme: Literal["exact"]
    network: Literal["xrpl:1"]
    asset: Literal["XRP"]
    pay_to: XrplAddress = Field(alias="payTo")
    amount: PositiveDrops
    max_timeout_seconds: int = Field(alias="maxTimeoutSeconds", ge=1, le=3600)
    extra: PaymentRequirementExtra


class PaymentRequirement(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    x402_version: Literal[2] = Field(alias="x402Version", default=2)
    accepts: list[PaymentRequirementAccept] = Field(min_length=1)


class ApiError(ContractModel):
    error: ApiErrorCode
    message: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    retryable: bool
    request_id: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    details: dict | None = None
