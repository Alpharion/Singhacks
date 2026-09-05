from __future__ import annotations

import pytest

from buyer_agent import drops
from buyer_agent.discovery import FixtureDiscoveryClient
from buyer_agent.payments import SimulatedPaymentClient
from buyer_agent.state_machine import ProcurementAgent, new_state

from conftest import DEMO_NOW, clock_from, load_fixture
from test_contracts import schema_validator

EXPECTED_SPEND = load_fixture("agent-run.json")["spend"]


async def run_demo(goal, policy, settings, *, failures=frozenset()):
    agent = ProcurementAgent(
        discovery=FixtureDiscoveryClient(rebase=False),
        payments=SimulatedPaymentClient(failing_provider_ids=failures),
        settings=settings,
        clock=clock_from(DEMO_NOW),
    )
    state = new_state(run_id="run_test_001", goal=goal, policy=policy, now=DEMO_NOW)
    return await agent.execute(state)


@pytest.fixture
async def fulfilled(goal, policy, settings):
    return await run_demo(goal, policy, settings)


async def test_the_demo_run_reaches_fulfilment(fulfilled):
    assert fulfilled.status == "fulfilled"
    assert fulfilled.failure is None


async def test_every_requested_meal_is_secured(fulfilled, goal):
    assert fulfilled.secured_meals == goal.meal_count
    assert len(fulfilled.reservations) == 2
    assert len(fulfilled.delivery_bookings) == 1


async def test_spend_matches_the_frozen_demo_figures(fulfilled):
    snapshot = fulfilled.snapshot()
    assert snapshot.spend.wire() == EXPECTED_SPEND


async def test_spend_and_remaining_budget_reconcile(fulfilled, goal):
    spend = fulfilled.snapshot().spend
    assert drops.to_int(spend.total_drops) + drops.to_int(spend.remaining_drops) == drops.to_int(
        goal.max_total_spend_drops
    )
    receipts = [item.payment_receipt for item in fulfilled.reservations] + [
        item.payment_receipt for item in fulfilled.delivery_bookings
    ]
    assert drops.total(receipt.amount_drops for receipt in receipts) == drops.to_int(
        spend.total_drops
    )


async def test_the_event_sequence_is_contiguous(fulfilled):
    assert [event.sequence for event in fulfilled.events] == list(
        range(1, len(fulfilled.events) + 1)
    )


async def test_the_timeline_tells_the_whole_story(fulfilled):
    kinds = [event.event_type for event in fulfilled.events]
    for expected in (
        "goal_parsed",
        "offers_discovered",
        "offer_rejected",
        "plans_built",
        "plan_selected",
        "payment_required",
        "payment_authorized",
        "payment_settled",
        "reservation_confirmed",
        "delivery_confirmed",
        "run_fulfilled",
    ):
        assert expected in kinds, f"missing {expected} event"


async def test_the_non_vegetarian_offer_is_rejected_with_a_reason(fulfilled):
    rejection = next(
        decision for decision in fulfilled.decisions if decision.decision_type == "reject_offer"
    )
    grill = next(
        item for item in rejection.rejected_alternatives if item.option_id == "offer_grill_001"
    )
    assert any("vegetarian" in reason for reason in grill.reasons)


async def test_each_payment_is_authorized_and_explained(fulfilled):
    authorizations = [
        decision for decision in fulfilled.decisions if decision.decision_type == "authorize_payment"
    ]
    assert len(authorizations) == 3  # two reservations plus delivery
    for decision in authorizations:
        assert decision.transaction_hash
        assert decision.reasons
        assert decision.wallet_policy_id == "policy_demo_001"


async def test_the_selection_names_the_alternatives_it_beat(fulfilled):
    selection = next(
        decision for decision in fulfilled.decisions if decision.decision_type == "select_plan"
    )
    assert selection.selected_option_id
    assert len(selection.alternatives_considered) >= 2
    assert selection.rejected_alternatives


async def test_the_run_validates_against_the_frozen_schema(fulfilled):
    validator = schema_validator("agent-run.schema.json")
    assert list(validator.iter_errors(fulfilled.snapshot().wire())) == []


async def test_simulated_settlement_is_labelled_as_such(fulfilled):
    settled = [event for event in fulfilled.events if event.event_type == "payment_settled"]
    assert settled
    assert all("Simulated settlement only" in event.message for event in settled)
    for reservation in fulfilled.reservations:
        # Sixteen leading zeros make a placeholder impossible to mistake for a real hash.
        assert reservation.payment_receipt.transaction.startswith("0" * 16)


async def test_an_impossible_budget_stops_the_run_without_spending(goal, settings):
    from buyer_agent.policy import load_policy

    tiny = goal.model_copy(update={"max_total_spend_drops": "20000000"})
    policy = load_policy(tiny.wallet_policy_id, tiny.max_total_spend_drops, settings)
    state = await run_demo(tiny, policy, settings)

    assert state.status == "failed"
    assert state.failure is not None
    assert state.total_spent_drops == 0
    assert state.reservations == []
    stop = next(decision for decision in state.decisions if decision.decision_type == "stop")
    assert "within" in stop.reasons[0]
