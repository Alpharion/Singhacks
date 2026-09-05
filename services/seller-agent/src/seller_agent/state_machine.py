"""The listing loop: publish, observe, reprice, close.

The agent holds a listing open for the whole collection window, repricing on a
tick. Each tick asks `pricing.py` what the price should be now and records the
answer as an explained decision, so a seller can read back exactly why their
food was ever offered at a given number.

The agent's clock can be scaled so a window that really spans hours can be
watched: `time_scale` is carried on the listing and shown in the UI, because a
compressed clock that is not stated is a lie about how fast the agent works.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from . import drops, ids, timeutil
from .llm import phrase_rationale
from .market import SimulatedMarket
from .models import (
    ListingEvent,
    ListingEventType,
    ListingRevenue,
    PricingDecision,
    SellerListing,
    SellingGoal,
)
from .pricing import quote


class ListingAgent:
    """Owns one listing's lifecycle. Not shared between listings."""

    def __init__(
        self,
        listing: SellerListing,
        *,
        tick_seconds: float,
        llm_enabled: bool,
        market: SimulatedMarket | None = None,
    ) -> None:
        self.listing = listing
        self.tick_seconds = tick_seconds
        self.llm_enabled = llm_enabled
        self.market = market or SimulatedMarket(listing.listing_id, enabled=False)
        self._sequence = len(listing.events)
        self._enquiries = 0
        self._gross_drops = 0
        self._lock = asyncio.Lock()

    # --- timeline -------------------------------------------------------

    def _event(
        self, event_type: ListingEventType, message: str, *, related_id: str | None = None
    ) -> None:
        self._sequence += 1
        self.listing.events.append(
            ListingEvent(
                sequence=self._sequence,
                event_type=event_type,
                message=message,
                related_id=related_id,
                created_at=timeutil.iso(timeutil.now()),
            )
        )
        self.listing.updated_at = timeutil.iso(timeutil.now())

    # --- clock ----------------------------------------------------------

    def elapsed_ratio(self, now: datetime | None = None) -> float:
        """How far through the selling window the agent's clock has run."""
        moment = now or timeutil.now()
        start = timeutil.parse(self.listing.created_at)
        deadline = timeutil.parse(self.listing.goal.collection_deadline)

        window = (deadline - start).total_seconds()
        if window <= 0:
            return 1.0

        elapsed = (moment - start).total_seconds() * self.listing.time_scale
        return max(0.0, min(1.0, elapsed / window))

    # --- lifecycle ------------------------------------------------------

    def publish(self) -> None:
        goal = self.listing.goal
        self.listing.status = "listed"
        self.listing.unit_price_drops = goal.opening_unit_price_drops
        self._event(
            "listing_parsed",
            f"Parsed an offer of {goal.quantity} units for collection by "
            f"{goal.collection_deadline}, never below "
            f"{drops.to_xrp_label(goal.floor_unit_price_drops)} each.",
            related_id=goal.goal_id,
        )
        self._event(
            "listing_published",
            f"Listed {goal.quantity} units at "
            f"{drops.to_xrp_label(goal.opening_unit_price_drops)} each, with a floor of "
            f"{drops.to_xrp_label(goal.floor_unit_price_drops)}.",
        )

    async def record_demand(self, quantity: int, source: str) -> None:
        async with self._lock:
            self._apply_demand(quantity, source)
            self._reprice()

    async def record_sale(self, quantity: int) -> None:
        async with self._lock:
            if self._apply_sale(quantity) and self.listing.status != "cleared":
                self._reprice()

    def _apply_demand(self, quantity: int, source: str) -> None:
        """Record interest. Caller holds the lock."""
        self._enquiries += 1
        self._event(
            "demand_observed",
            f"{source} asked about {quantity} {'unit' if quantity == 1 else 'units'}.",
        )

    def _apply_sale(self, quantity: int) -> bool:
        """Sell units at the live price. Caller holds the lock."""
        sold = min(quantity, self.listing.quantity_remaining)
        if sold <= 0:
            return False

        unit_price = int(self.listing.unit_price_drops)
        self._gross_drops += sold * unit_price
        self.listing.quantity_remaining -= sold
        self._recompute_revenue()

        self._event(
            "units_sold",
            f"Sold {sold} {'unit' if sold == 1 else 'units'} at "
            f"{drops.to_xrp_label(unit_price)} each.",
        )

        if self.listing.quantity_remaining == 0:
            self.listing.status = "cleared"
            self._event(
                "listing_cleared",
                f"All {self.listing.goal.quantity} units sold for "
                f"{drops.to_xrp_label(self._gross_drops)}, "
                f"{drops.to_xrp_label(self.listing.revenue.uplift_drops)} above floor.",
            )
        return True

    def _recompute_revenue(self) -> None:
        goal = self.listing.goal
        units_sold = goal.quantity - self.listing.quantity_remaining
        floor_value = units_sold * int(goal.floor_unit_price_drops)
        self.listing.revenue = ListingRevenue(
            units_sold=units_sold,
            gross_drops=drops.to_str(self._gross_drops),
            floor_value_drops=drops.to_str(floor_value),
            # Never negative: the engine cannot sell under the floor, so a
            # negative uplift would mean a bug rather than a bad trade.
            uplift_drops=drops.to_str(max(0, self._gross_drops - floor_value)),
        )

    # --- pricing --------------------------------------------------------

    def _reprice(self) -> bool:
        """Ask the engine for the current price and record the decision.

        Returns True when the price actually moved.
        """
        goal = self.listing.goal
        previous = int(self.listing.unit_price_drops)

        result = quote(
            floor_drops=int(goal.floor_unit_price_drops),
            opening_drops=int(goal.opening_unit_price_drops),
            current_drops=previous,
            elapsed_ratio=self.elapsed_ratio(),
            quantity_total=goal.quantity,
            quantity_remaining=self.listing.quantity_remaining,
            enquiries=self._enquiries,
        )

        decision = PricingDecision(
            decision_id=ids.unique("decision"),
            listing_id=self.listing.listing_id,
            action=result.action,
            objective=(
                f"Clear {goal.quantity} units before "
                f"{goal.collection_deadline} without going under "
                f"{drops.to_xrp_label(goal.floor_unit_price_drops)}."
            ),
            previous_unit_price_drops=drops.to_str(previous),
            unit_price_drops=drops.to_str(result.unit_price_drops),
            floor_unit_price_drops=goal.floor_unit_price_drops,
            factors=result.factors,
            reasons=result.reasons,
            rationale=phrase_rationale(
                action=result.action,
                previous_drops=previous,
                new_drops=result.unit_price_drops,
                floor_drops=int(goal.floor_unit_price_drops),
                factors=result.factors,
                reasons=result.reasons,
                enabled=self.llm_enabled,
            ),
            created_at=timeutil.iso(timeutil.now()),
        )

        self.listing.decisions.append(decision)
        self.listing.unit_price_drops = decision.unit_price_drops

        # The rationale already names the prices and the reason, so the event
        # message is the rationale rather than a preamble repeating it.
        moved = result.unit_price_drops != previous
        if result.action == "reduce":
            self._event("price_reduced", decision.rationale, related_id=decision.decision_id)
        elif result.action == "raise":
            self._event("price_raised", decision.rationale, related_id=decision.decision_id)
        elif result.action == "floor" and moved:
            self._event("floor_reached", decision.rationale, related_id=decision.decision_id)
        elif not moved and result.action != "floor":
            self._event("price_held", decision.rationale, related_id=decision.decision_id)

        if self.listing.status == "listed":
            self.listing.status = "repricing"
        return moved

    def _run_market(self) -> None:
        """Let the simulated buyers act on the price just set. Caller holds the lock."""
        goal = self.listing.goal
        floor = int(goal.floor_unit_price_drops)
        opening = int(goal.opening_unit_price_drops)
        band = opening - floor
        position = (int(self.listing.unit_price_drops) - floor) / band if band > 0 else 0.0

        trade = self.market.tick(
            position=position,
            elapsed=self.elapsed_ratio(),
            quantity_total=goal.quantity,
            quantity_remaining=self.listing.quantity_remaining,
        )
        if trade.enquiries == 0:
            return

        self._apply_demand(trade.units, "A buyer")
        if trade.units > 0:
            self._apply_sale(trade.units)

    # --- the loop -------------------------------------------------------

    async def run(self) -> None:
        """Reprice until the window closes or the stock clears."""
        try:
            while True:
                await asyncio.sleep(self.tick_seconds)
                async with self._lock:
                    if self.listing.status in ("cleared", "expired", "withdrawn"):
                        return

                    if self.elapsed_ratio() >= 1.0:
                        self.listing.status = (
                            "cleared" if self.listing.quantity_remaining == 0 else "expired"
                        )
                        self._event(
                            "listing_expired",
                            f"Collection window closed with "
                            f"{self.listing.quantity_remaining} units unsold.",
                        )
                        return

                    self._reprice()
                    self._run_market()
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise


def new_listing(goal: SellingGoal, *, time_scale: int) -> SellerListing:
    now = timeutil.iso(timeutil.now())
    return SellerListing(
        listing_id=ids.unique("listing"),
        status="queued",
        goal=goal,
        unit_price_drops=goal.opening_unit_price_drops,
        quantity_remaining=goal.quantity,
        revenue=ListingRevenue(
            units_sold=0,
            gross_drops="0",
            floor_value_drops="0",
            uplift_drops="0",
        ),
        time_scale=time_scale,
        created_at=now,
        updated_at=now,
    )
