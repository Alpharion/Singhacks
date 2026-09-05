"""Seller-side types.

Deliberately shaped like the buyer's `AgentRun`: a listing has a goal, a
timeline of events, a list of explained decisions, and a terminal status. The
frontend renders both from the same idiom, and a reader who has understood one
side has understood the other.

Money is an integer count of drops in a decimal string, exactly as the frozen
contract requires on the buyer side. Nothing here is ever a float.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DietaryTag = Literal["vegetarian", "vegan", "halal", "kosher", "nut_free", "gluten_free"]

ListingStatus = Literal[
    "queued",
    "parsing",
    "listed",
    "repricing",
    "cleared",
    "expired",
    "withdrawn",
]

ListingEventType = Literal[
    "listing_parsed",
    "listing_published",
    "demand_observed",
    "price_reduced",
    "price_raised",
    "price_held",
    "floor_reached",
    "units_sold",
    "listing_cleared",
    "listing_expired",
]

PricingAction = Literal["open", "reduce", "raise", "hold", "floor"]


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(word.capitalize() for word in rest)


class Wire(BaseModel):
    """Base model that speaks camelCase on the wire, as the buyer contract does."""

    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)

    def wire(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class SellingGoal(Wire):
    """What the seller delegated, parsed from one sentence."""

    goal_id: str
    seller_id: str
    description: str
    quantity: int = Field(ge=1)
    dietary_tags: list[DietaryTag] = Field(default_factory=list)
    collection_deadline: str
    #: The price the agent may never go under. The whole point of the delegation.
    floor_unit_price_drops: str
    #: What the agent opens at. Always at or above the floor.
    opening_unit_price_drops: str


class PricingFactors(Wire):
    """The inputs behind one decision, kept so the seller can audit the move.

    Each is a ratio in [0, 1] unless noted, which is what makes the weighted
    sum in `pricing.py` legible rather than a magic number.
    """

    #: How much of the selling window has elapsed.
    time_elapsed: float
    #: Fraction of the original quantity already sold.
    sell_through: float
    #: sell_through minus time_elapsed. Negative means behind schedule.
    pace: float
    #: Recent buyer interest, normalised.
    demand: float
    #: Enquiries seen since the listing opened.
    enquiries: int
    #: Units still unsold.
    remaining: int


class PricingDecision(Wire):
    """One repricing call, with its reasoning. The seller's `AgentDecision`."""

    decision_id: str
    listing_id: str
    action: PricingAction
    objective: str
    previous_unit_price_drops: str
    unit_price_drops: str
    floor_unit_price_drops: str
    factors: PricingFactors
    reasons: list[str]
    #: Plain-language summary. The only field the model may write.
    rationale: str
    created_at: str


class ListingEvent(Wire):
    sequence: int = Field(ge=1)
    event_type: ListingEventType
    message: str
    related_id: str | None = None
    created_at: str


class ListingRevenue(Wire):
    units_sold: int
    gross_drops: str
    #: What the same units would have earned at the floor price.
    floor_value_drops: str
    #: gross minus floor value. The agent's contribution, never negative.
    uplift_drops: str


class SellerListing(Wire):
    """The seller-side counterpart of `AgentRun`."""

    listing_id: str
    status: ListingStatus
    goal: SellingGoal
    unit_price_drops: str
    quantity_remaining: int
    decisions: list[PricingDecision] = Field(default_factory=list)
    events: list[ListingEvent] = Field(default_factory=list)
    revenue: ListingRevenue
    #: How much faster than wall-clock the agent's clock runs, so a listing that
    #: really spans hours can be watched in a demo. 1 means real time.
    time_scale: int = 1
    #: True while buyers are simulated in-process rather than arriving from the
    #: real marketplace. Surfaced so the UI can say so on the page.
    simulated_market: bool = False
    created_at: str
    updated_at: str


class ListingRequest(Wire):
    """What the seller posts. One sentence plus the floor they will not go under."""

    seller_id: str
    request_text: str


class DemandSignal(Wire):
    """A buyer showed interest. Raises the agent's demand estimate."""

    quantity: int = Field(default=1, ge=1)
    source: str = "buyer_agent"


class SaleSignal(Wire):
    """Units actually sold, at the price that was live when they sold."""

    quantity: int = Field(ge=1)


class ApiError(Wire):
    error: str
    message: str
    retryable: bool = False
    request_id: str
