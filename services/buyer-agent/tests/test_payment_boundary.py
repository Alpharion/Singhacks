"""The boundary onto Person 4's PaymentExecutor.

The important behaviour here is recovery. Person 4's errors split into failures
where nothing was signed (another provider may be tried) and failures where a
payment may already be in flight or settled (the run must stop and be
reconciled). Confusing the two is how an agent pays twice.
"""

from __future__ import annotations

import threading

import pytest
from surplusflow_payments.errors import (
    DuplicatePaymentError,
    PaymentExecutionError,
    PaymentInProgressError,
    PaymentReceiptError,
    PolicyViolation,
    WalletConfigurationError,
)
from surplusflow_payments.models import PaymentExecutionResult
from surplusflow_payments.models import PaymentReceipt as PaymentsReceipt

from buyer_agent import timeutil
from buyer_agent.intents import food_intent
from buyer_agent.models import PurchaseIntent
from buyer_agent.payments import ExecutorPaymentClient, Recovery
from buyer_agent.policy import WalletPolicy

from conftest import DEMO_NOW

# Deterministic addresses with real base58check checksums. The contract fixtures
# use synthetic placeholders, which the payment boundary rejects on sight.
SELLER = "rBXVQRYBGNMG4qW1BJHTpuSyyrJDtQe9pE"
BUYER = "rBXVQRYBGNMG4qW1BHxuFvHQ5NKdSnaoYt"


@pytest.fixture
def payable_policy() -> WalletPolicy:
    return WalletPolicy(
        wallet_policy_id="policy_demo_001",
        max_order_spend_drops=120_000_000,
        max_transaction_spend_drops=70_000_000,
        allowed_payees=(SELLER,),
    )


@pytest.fixture
def intent(goal, offers, payable_policy) -> PurchaseIntent:
    offer = offers[0].model_copy(update={"pay_to": SELLER})
    allocation_source = offer
    from buyer_agent.models import FoodAllocation

    allocation = FoodAllocation(
        seller_id=offer.seller_id,
        offer_id=offer.offer_id,
        quantity=60,
        unit_price_drops=allocation_source.unit_price_drops,
        line_total_drops="36000000",
        reliability_score=offer.reliability_score,
    )
    return food_intent(
        run_id="run_test_001",
        goal=goal,
        offer=offer,
        allocation=allocation,
        policy=payable_policy,
        rationale="Test purchase.",
        now=DEMO_NOW,
    )


def receipt_for(intent: PurchaseIntent, **overrides) -> PaymentsReceipt:
    payload = {
        "success": True,
        "transaction": "A" * 64,
        "network": "xrpl:1",
        "payer": BUYER,
        "payee": intent.pay_to,
        "amountDrops": intent.amount_drops,
        "invoiceId": intent.invoice_id,
        "validated": True,
        "validatedAt": timeutil.iso(DEMO_NOW),
        "explorerUrl": f"https://testnet.xrpl.org/transactions/{'A' * 64}",
    }
    payload.update(overrides)
    return PaymentsReceipt.model_validate(payload)


def reservation_body(intent: PurchaseIntent) -> dict:
    return {
        "reservationId": "reservation_test_001",
        "runId": intent.run_id,
        "sellerId": intent.provider_id,
        "offerId": intent.resource_id,
        "quantity": intent.quantity,
        "status": "confirmed",
        "pickupWindow": {"start": "2026-09-05T07:00:00Z", "end": "2026-09-05T08:30:00Z"},
        "pickupToken": "pickup_test_001",
        "paymentReceipt": receipt_for(intent).model_dump(mode="json", by_alias=True),
        "createdAt": "2026-09-05T06:02:31Z",
        "expiresAt": "2026-09-05T08:30:00Z",
    }


class FakeExecutor:
    """Stands in for PaymentExecutor: records the call, then raises or returns."""

    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict] = []
        self.thread_names: list[str] = []

    def execute(self, intent, *, already_spent_drops, **kwargs):
        self.calls.append({"intent": intent, "already_spent_drops": already_spent_drops})
        self.thread_names.append(threading.current_thread().name)
        if self.error is not None:
            raise self.error
        return self.result


async def test_a_settled_purchase_returns_the_reservation_and_receipt(intent):
    executor = FakeExecutor(
        result=PaymentExecutionResult(
            receipt=receipt_for(intent), status_code=201, resource=reservation_body(intent)
        )
    )
    outcome = await ExecutorPaymentClient(executor).purchase(intent)

    assert outcome.ok
    assert outcome.status_code == 201
    assert outcome.reservation is not None
    assert outcome.reservation.quantity == 60
    assert outcome.receipt is not None
    assert outcome.receipt.transaction == "A" * 64
    assert outcome.simulated is False


async def test_running_spend_is_passed_to_the_boundary(intent):
    executor = FakeExecutor(
        result=PaymentExecutionResult(
            receipt=receipt_for(intent), status_code=201, resource=reservation_body(intent)
        )
    )
    await ExecutorPaymentClient(executor).purchase(intent, already_spent_drops=26_000_000)
    assert executor.calls[0]["already_spent_drops"] == 26_000_000


async def test_the_synchronous_executor_runs_off_the_event_loop(intent):
    executor = FakeExecutor(
        result=PaymentExecutionResult(
            receipt=receipt_for(intent), status_code=201, resource=reservation_body(intent)
        )
    )
    await ExecutorPaymentClient(executor).purchase(intent)
    assert executor.thread_names[0] != threading.main_thread().name


@pytest.mark.parametrize(
    ("error", "expected_code", "expected_recovery"),
    [
        (PolicyViolation("outside authority"), "policy_rejected", Recovery.REPLAN),
        (PaymentExecutionError("no signed hash"), "payment_failed", Recovery.REPLAN),
        (PaymentInProgressError("already in flight"), "payment_timeout", Recovery.HALT),
        (DuplicatePaymentError("already settled"), "payment_replayed", Recovery.HALT),
        (PaymentReceiptError("uncertain"), "payment_failed", Recovery.HALT),
        (WalletConfigurationError("no wallet"), "internal_error", Recovery.HALT),
    ],
    ids=lambda value: getattr(value, "__class__", type(value)).__name__,
)
async def test_each_payment_error_maps_to_the_right_recovery(
    intent, error, expected_code, expected_recovery
):
    outcome = await ExecutorPaymentClient(FakeExecutor(error=error)).purchase(intent)

    assert outcome.ok is False
    assert outcome.error is not None
    assert outcome.error.error == expected_code
    assert outcome.recovery is expected_recovery


async def test_an_in_flight_payment_never_looks_retryable(intent):
    outcome = await ExecutorPaymentClient(
        FakeExecutor(error=PaymentInProgressError("in flight"))
    ).purchase(intent)
    assert outcome.error is not None
    assert outcome.error.retryable is False
    assert "reconcile" in outcome.error.message


async def test_a_receipt_for_the_wrong_amount_halts_the_run(intent):
    executor = FakeExecutor(
        result=PaymentExecutionResult(
            receipt=receipt_for(intent, amountDrops="1000000"),
            status_code=201,
            resource=reservation_body(intent),
        )
    )
    outcome = await ExecutorPaymentClient(executor).purchase(intent)

    assert outcome.ok is False
    assert outcome.error is not None
    assert outcome.error.error == "invoice_mismatch"
    assert outcome.recovery is Recovery.HALT


async def test_a_receipt_for_the_wrong_invoice_halts_the_run(intent):
    executor = FakeExecutor(
        result=PaymentExecutionResult(
            receipt=receipt_for(intent, invoiceId="inv:someone:else:v1"),
            status_code=201,
            resource=reservation_body(intent),
        )
    )
    outcome = await ExecutorPaymentClient(executor).purchase(intent)
    assert outcome.error is not None
    assert outcome.error.error == "invoice_mismatch"
    assert outcome.recovery is Recovery.HALT


async def test_a_paid_but_unparseable_response_halts_rather_than_replans(intent):
    executor = FakeExecutor(
        result=PaymentExecutionResult(
            receipt=receipt_for(intent), status_code=201, resource={"unexpected": "shape"}
        )
    )
    outcome = await ExecutorPaymentClient(executor).purchase(intent)

    assert outcome.ok is False
    assert outcome.recovery is Recovery.HALT
    assert "does not match the frozen contract" in outcome.error.message


async def test_a_synthetic_fixture_address_is_refused_before_any_payment(
    goal, offers, payable_policy
):
    """The contract's placeholder addresses are not real XRPL addresses."""
    from buyer_agent.models import FoodAllocation

    offer = offers[0]  # keeps the synthetic rFoodA... payee
    allocation = FoodAllocation(
        seller_id=offer.seller_id,
        offer_id=offer.offer_id,
        quantity=60,
        unit_price_drops=offer.unit_price_drops,
        line_total_drops="36000000",
        reliability_score=offer.reliability_score,
    )
    bad_intent = food_intent(
        run_id="run_test_001",
        goal=goal,
        offer=offer,
        allocation=allocation,
        policy=payable_policy,
        rationale="Test purchase.",
        now=DEMO_NOW,
    )
    executor = FakeExecutor()
    outcome = await ExecutorPaymentClient(executor).purchase(bad_intent)

    assert outcome.ok is False
    assert outcome.error.error == "invalid_request"
    assert executor.calls == [], "no payment should be attempted for an invalid intent"
