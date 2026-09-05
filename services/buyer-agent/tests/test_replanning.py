"""Failure recovery: a provider that drops out must not sink the run."""

from __future__ import annotations

import pytest

from buyer_agent import drops
from buyer_agent.payments import SimulatedPaymentClient
from buyer_agent.policy import load_policy
from buyer_agent.state_machine import ProcurementAgent, new_state

from conftest import DEMO_NOW, clock_from
from stubs import StubDiscovery

ALL_SELLERS = ["seller_bakery_001", "seller_hotel_001", "seller_backup_001"]


@pytest.fixture
def backup_offer(offers):
    """A third vegetarian seller, so a failure has somewhere to go."""
    hotel = next(offer for offer in offers if offer.offer_id == "offer_hotel_001")
    return hotel.model_copy(
        update={
            "offer_id": "offer_backup_001",
            "seller_id": "seller_backup_001",
            "seller_name": "Backup Kitchen",
            "pay_to": "rFoodB1111111111111111111111111",
            "quantity_available": 60,
        }
    )


@pytest.fixture
def wide_quotes(quotes):
    """Both couriers available and able to collect from every seller."""
    return [
        quote.model_copy(
            update={"status": "available", "pickup_seller_ids": ALL_SELLERS, "capacity_meals": 150}
        )
        for quote in quotes
    ]


@pytest.fixture
def open_goal(goal):
    return goal.model_copy(
        update={"approved_seller_ids": ALL_SELLERS, "approved_courier_ids": None}
    )


async def run(goal, offers, quotes, settings, failures):
    agent = ProcurementAgent(
        discovery=StubDiscovery(offers, quotes),
        payments=SimulatedPaymentClient(failing_provider_ids=frozenset(failures)),
        settings=settings,
        clock=clock_from(DEMO_NOW),
    )
    policy = load_policy(goal.wallet_policy_id, goal.max_total_spend_drops, settings)
    state = new_state(run_id="run_replan_001", goal=goal, policy=policy, now=DEMO_NOW)
    return await agent.execute(state)


async def test_a_seller_failing_before_any_payment_is_replanned_around(
    open_goal, offers, backup_offer, wide_quotes, settings
):
    state = await run(
        open_goal, offers + [backup_offer], wide_quotes, settings, {"seller_bakery_001"}
    )

    assert state.status == "fulfilled"
    assert state.secured_meals == open_goal.meal_count
    assert "seller_bakery_001" not in {item.seller_id for item in state.reservations}
    assert any(event.event_type == "replanning_started" for event in state.events)
    assert any(decision.decision_type == "replan" for decision in state.decisions)


async def test_a_partial_order_replans_only_the_missing_meals(
    open_goal, offers, backup_offer, wide_quotes, settings
):
    state = await run(
        open_goal, offers + [backup_offer], wide_quotes, settings, {"seller_hotel_001"}
    )

    assert state.status == "fulfilled"
    assert state.secured_meals == open_goal.meal_count

    paid = [(item.seller_id, item.quantity) for item in state.reservations]
    assert ("seller_bakery_001", 60) in paid
    assert ("seller_backup_001", 40) in paid
    # The seller already paid is never charged twice.
    assert len(paid) == len(set(item[0] for item in paid))


async def test_a_courier_failing_at_booking_falls_back_to_the_other(
    open_goal, offers, backup_offer, wide_quotes, settings
):
    """FastRoute wins the plan on reliability and ETA; when it drops out at
    booking time the food is already paid for, so the agent must find another
    courier rather than abandon the order."""
    state = await run(
        open_goal, offers + [backup_offer], wide_quotes, settings, {"courier_fast_001"}
    )

    assert state.status == "fulfilled"
    assert [booking.provider_id for booking in state.delivery_bookings] == ["courier_economy_001"]
    assert any(
        event.event_type == "provider_failed" and event.related_id == "quote_fast_001"
        for event in state.events
    )
    # Exactly one delivery was paid for, at the fallback courier's price.
    assert state.delivery_spent_drops == 10_000_000


async def test_replanning_never_exceeds_the_delegated_budget(
    open_goal, offers, backup_offer, wide_quotes, settings
):
    state = await run(
        open_goal, offers + [backup_offer], wide_quotes, settings, {"seller_hotel_001"}
    )
    assert state.total_spent_drops <= drops.to_int(open_goal.max_total_spend_drops)
    assert state.remaining_drops >= 0


async def test_when_every_seller_fails_the_run_stops_without_spending(
    open_goal, offers, backup_offer, wide_quotes, settings
):
    state = await run(
        open_goal,
        offers + [backup_offer],
        wide_quotes,
        settings,
        {"seller_bakery_001", "seller_hotel_001", "seller_backup_001"},
    )

    assert state.status == "failed"
    assert state.total_spent_drops == 0
    assert state.failure is not None
    assert state.failure.error in {"offer_sold_out", "provider_unavailable", "budget_exceeded"}


async def test_a_courier_that_cannot_reach_every_paid_seller_is_not_booked(
    open_goal, offers, backup_offer, quotes, settings
):
    """The courier must still collect from sellers that were already paid."""
    narrow = [
        quotes[0].model_copy(
            update={
                "status": "available",
                "pickup_seller_ids": ["seller_bakery_001", "seller_hotel_001"],
            }
        )
    ]
    state = await run(
        open_goal, offers + [backup_offer], narrow, settings, {"seller_hotel_001"}
    )

    assert state.status == "failed"
    assert state.delivery_bookings == []


class HaltingPaymentClient:
    """Fails one provider in a way that must never be retried."""

    def __init__(self, provider_id: str, inner) -> None:
        self._provider_id = provider_id
        self._inner = inner
        self.attempts: list[str] = []

    async def aclose(self) -> None:
        return None

    async def purchase(self, intent, *, offer=None, quote=None, already_spent_drops=0, now=None):
        from buyer_agent.models import ApiError
        from buyer_agent.payments import PurchaseOutcome, Recovery

        self.attempts.append(intent.provider_id)
        if intent.provider_id == self._provider_id:
            return PurchaseOutcome(
                ok=False,
                status_code=409,
                recovery=Recovery.HALT,
                error=ApiError(
                    error="payment_timeout",
                    message="A payment for this invoice is already in flight; reconcile it.",
                    retryable=False,
                    request_id="request_halt_001",
                ),
            )
        return await self._inner.purchase(
            intent,
            offer=offer,
            quote=quote,
            already_spent_drops=already_spent_drops,
            now=now,
        )


async def test_an_in_flight_payment_stops_the_run_instead_of_replanning(
    open_goal, offers, backup_offer, wide_quotes, settings
):
    """A payment that may already be settled must not be replanned around:
    trying another seller for the same meals could pay for them twice."""
    from buyer_agent.payments import SimulatedPaymentClient
    from buyer_agent.state_machine import ProcurementAgent, new_state

    payments = HaltingPaymentClient("seller_bakery_001", SimulatedPaymentClient(frozenset()))
    agent = ProcurementAgent(
        discovery=StubDiscovery(offers + [backup_offer], wide_quotes),
        payments=payments,
        settings=settings,
        clock=clock_from(DEMO_NOW),
    )
    policy = load_policy(open_goal.wallet_policy_id, open_goal.max_total_spend_drops, settings)
    state = await agent.execute(
        new_state(run_id="run_halt_001", goal=open_goal, policy=policy, now=DEMO_NOW)
    )

    assert state.status == "failed"
    assert state.failure is not None
    assert state.failure.error == "payment_timeout"
    assert state.failure.retryable is False

    # The run stopped: no replan decision, and the failing seller was tried once.
    assert not any(decision.decision_type == "replan" for decision in state.decisions)
    assert payments.attempts.count("seller_bakery_001") == 1
    assert state.reservations == []
    assert state.delivery_bookings == []

    stop = next(decision for decision in state.decisions if decision.decision_type == "stop")
    assert any("pay twice" in reason for reason in stop.reasons)
