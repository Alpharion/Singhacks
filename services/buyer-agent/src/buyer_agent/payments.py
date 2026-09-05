"""The payment boundary.

The only place the agent touches a paid endpoint, and deliberately thin. It
never builds, signs, or inspects an XRPL transaction and never reads a wallet
seed: the x402 challenge, local signing, settlement, and the paid retry all live
in `packages/payments` (Person 4).

`PaymentExecutor.execute` is synchronous and uses `requests`, so it runs on a
worker thread rather than blocking the agent's event loop.

Recovery is the part that matters here. Person 4's errors divide into two
groups, and treating them alike would risk paying twice:

* no money moved, so another provider can be tried -- `Recovery.REPLAN`;
* a payment may already be in flight or settled, so the run must stop and be
  reconciled against the stored transaction hash -- `Recovery.HALT`.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from . import config, drops, ids, timeutil
from .models import (
    ApiError,
    DeliveryBooking,
    DeliveryQuote,
    ErrorCode,
    FoodOffer,
    PaymentReceipt,
    PurchaseIntent,
    Reservation,
)

log = logging.getLogger(__name__)

SIMULATED_PAYER = "rBuyer1111111111111111111111111"


class Recovery(StrEnum):
    """What the state machine may safely do after a failed purchase."""

    REPLAN = "replan"
    HALT = "halt"


@dataclass(frozen=True)
class PurchaseOutcome:
    ok: bool
    status_code: int
    receipt: PaymentReceipt | None = None
    reservation: Reservation | None = None
    booking: DeliveryBooking | None = None
    error: ApiError | None = None
    simulated: bool = False
    recovery: Recovery = Recovery.REPLAN


class PaymentClient(Protocol):
    async def purchase(
        self,
        intent: PurchaseIntent,
        *,
        offer: FoodOffer | None = None,
        quote: DeliveryQuote | None = None,
        already_spent_drops: int = 0,
        now: datetime | None = None,
    ) -> PurchaseOutcome: ...

    async def aclose(self) -> None: ...


def _failure(
    error: ErrorCode,
    message: str,
    *,
    status_code: int,
    recovery: Recovery,
    retryable: bool,
    details: dict[str, Any] | None = None,
) -> PurchaseOutcome:
    return PurchaseOutcome(
        ok=False,
        status_code=status_code,
        recovery=recovery,
        error=ApiError(
            error=error,
            message=message,
            retryable=retryable,
            request_id=ids.unique("request"),
            details=details,
        ),
    )


def _synthetic_hash(invoice_id: str) -> str:
    """A hash that cannot be mistaken for a real one: sixteen leading zeros."""
    digest = hashlib.sha256(invoice_id.encode()).hexdigest().upper()
    return "0" * 16 + digest[:48]


class SimulatedPaymentClient:
    """Offline stand-in for development and tests.

    It settles nothing. Receipts carry a hash with sixteen leading zeros and a
    localhost explorer URL, so a simulated run can never be shown as evidence of
    an XRPL payment.
    """

    def __init__(self, failing_provider_ids: frozenset[str] | None = None) -> None:
        if failing_provider_ids is None:
            raw = os.getenv("BUYER_AGENT_SIMULATED_FAILURES", "")
            failing_provider_ids = frozenset(
                item.strip() for item in raw.split(",") if item.strip()
            )
        self._failing = failing_provider_ids

    async def aclose(self) -> None:
        return None

    def _receipt(self, intent: PurchaseIntent, now: datetime) -> PaymentReceipt:
        transaction = _synthetic_hash(intent.invoice_id)
        return PaymentReceipt(
            success=True,
            transaction=transaction,
            network="xrpl:1",
            payer=SIMULATED_PAYER,
            payee=intent.pay_to,
            amount_drops=intent.amount_drops,
            invoice_id=intent.invoice_id,
            validated=True,
            validated_at=timeutil.iso(now),
            explorer_url=f"http://localhost:8001/api/simulated/{transaction}",
        )

    async def purchase(
        self,
        intent: PurchaseIntent,
        *,
        offer: FoodOffer | None = None,
        quote: DeliveryQuote | None = None,
        already_spent_drops: int = 0,
        now: datetime | None = None,
    ) -> PurchaseOutcome:
        now = now or timeutil.now()
        if intent.provider_id in self._failing:
            return PurchaseOutcome(
                ok=False,
                status_code=503,
                simulated=True,
                recovery=Recovery.REPLAN,
                error=ApiError(
                    error="provider_unavailable",
                    message=f"{intent.provider_id} cannot fulfil this request right now.",
                    retryable=True,
                    request_id=ids.unique("request"),
                    details={
                        "providerId": intent.provider_id,
                        "resourceId": intent.resource_id,
                    },
                ),
            )

        receipt = self._receipt(intent, now)

        if intent.resource_type == "food_reservation":
            if offer is None:
                raise ValueError("simulated food purchase requires the source offer")
            reservation = Reservation(
                reservation_id=ids.identifier("reservation", intent.resource_id),
                run_id=intent.run_id,
                seller_id=intent.provider_id,
                offer_id=intent.resource_id,
                quantity=intent.quantity or 0,
                status="confirmed",
                pickup_window=offer.pickup_window,
                pickup_token=f"pickup_{intent.resource_id}",
                payment_receipt=receipt,
                created_at=timeutil.iso(now),
                expires_at=offer.pickup_window.end,
            )
            return PurchaseOutcome(
                ok=True,
                status_code=201,
                receipt=receipt,
                reservation=reservation,
                simulated=True,
            )

        if quote is None:
            raise ValueError("simulated delivery purchase requires the source quote")
        booking = DeliveryBooking(
            booking_id=ids.identifier("booking", intent.resource_id),
            run_id=intent.run_id,
            provider_id=intent.provider_id,
            quote_id=intent.resource_id,
            status="confirmed",
            pickup_eta=quote.pickup_eta,
            delivery_eta=quote.delivery_eta,
            tracking_code=f"track_{intent.resource_id}",
            payment_receipt=receipt,
            created_at=timeutil.iso(now),
        )
        return PurchaseOutcome(
            ok=True, status_code=201, receipt=receipt, booking=booking, simulated=True
        )


class ExecutorPaymentClient:
    """Drives Person 4's `PaymentExecutor` for real XRPL Testnet settlement."""

    def __init__(self, executor: Any | None = None, timeout_seconds: float = 30.0) -> None:
        config.assert_no_seed_access()
        self._timeout = timeout_seconds
        self._executor = executor if executor is not None else self._build_executor()

    @staticmethod
    def _build_executor() -> Any:
        try:
            from surplusflow_payments import PaymentExecutor, PaymentJournal, PaymentSettings
        except ImportError as exc:
            raise RuntimeError(
                "x402 payment mode needs the payments package. Install it with "
                "`uv pip install -e ../../packages/payments`, or run with "
                "BUYER_AGENT_PAYMENT_MODE=simulated."
            ) from exc
        settings = PaymentSettings()
        return PaymentExecutor(settings, PaymentJournal(settings.payment_journal_path))

    async def aclose(self) -> None:
        return None

    async def purchase(
        self,
        intent: PurchaseIntent,
        *,
        offer: FoodOffer | None = None,
        quote: DeliveryQuote | None = None,
        already_spent_drops: int = 0,
        now: datetime | None = None,
    ) -> PurchaseOutcome:
        try:
            payment_intent = self._to_payment_intent(intent)
        except Exception as exc:  # noqa: BLE001 - a rejected intent must not crash the run
            return _failure(
                "invalid_request",
                f"The purchase intent was rejected by the payment boundary: {exc}",
                status_code=422,
                recovery=Recovery.REPLAN,
                retryable=False,
            )

        # execute() is synchronous and network-bound; keep the event loop free.
        return await asyncio.to_thread(
            self._execute, intent, payment_intent, already_spent_drops
        )

    @staticmethod
    def _to_payment_intent(intent: PurchaseIntent) -> Any:
        from surplusflow_payments.models import PurchaseIntent as PaymentPurchaseIntent

        return PaymentPurchaseIntent.model_validate(intent.wire())

    def _execute(
        self, intent: PurchaseIntent, payment_intent: Any, already_spent_drops: int
    ) -> PurchaseOutcome:
        from surplusflow_payments.errors import (
            DuplicatePaymentError,
            PaymentExecutionError,
            PaymentInProgressError,
            PaymentReceiptError,
            PolicyViolation,
            WalletConfigurationError,
        )

        try:
            result = self._executor.execute(
                payment_intent,
                already_spent_drops=already_spent_drops,
                timeout_seconds=self._timeout,
            )
        except PolicyViolation as exc:
            # Rejected before the journal opened, so nothing was signed.
            return _failure(
                "policy_rejected",
                f"The payment boundary refused this purchase: {exc}",
                status_code=409,
                recovery=Recovery.REPLAN,
                retryable=False,
            )
        except PaymentExecutionError as exc:
            # No signed hash, so the same requirement may be met elsewhere.
            return _failure(
                "payment_failed",
                f"Payment did not settle: {exc}",
                status_code=502,
                recovery=Recovery.REPLAN,
                retryable=True,
            )
        except PaymentInProgressError as exc:
            return self._halt(
                "payment_timeout",
                f"A payment for this invoice is already in flight: {exc}. The run stops "
                "so the stored transaction hash can be reconciled rather than paid twice.",
                intent,
            )
        except DuplicatePaymentError as exc:
            return self._halt(
                "payment_replayed",
                f"This invoice was already settled or its identity fields were reused: {exc}. "
                "Reconcile before spending again.",
                intent,
            )
        except PaymentReceiptError as exc:
            return self._halt(
                "payment_failed",
                f"Settlement outcome is uncertain after signing: {exc}. Reconcile the stored "
                "transaction hash before any further payment.",
                intent,
            )
        except WalletConfigurationError as exc:
            return self._halt(
                "internal_error",
                f"The buyer wallet is not usable: {exc}.",
                intent,
            )

        return self._normalize(intent, result)

    @staticmethod
    def _halt(error: ErrorCode, message: str, intent: PurchaseIntent) -> PurchaseOutcome:
        log.error("halting run %s on invoice %s: %s", intent.run_id, intent.invoice_id, message)
        return _failure(
            error,
            message,
            status_code=409,
            recovery=Recovery.HALT,
            retryable=False,
            details={"invoiceId": intent.invoice_id, "resourceId": intent.resource_id},
        )

    def _normalize(self, intent: PurchaseIntent, result: Any) -> PurchaseOutcome:
        receipt = PaymentReceipt.model_validate(
            result.receipt.model_dump(mode="json", by_alias=True)
        )
        mismatch = self._receipt_mismatch(intent, receipt)
        if mismatch:
            # Money moved but not as authorized: stop rather than build on it.
            return self._halt("invoice_mismatch", mismatch, intent)

        resource = result.resource
        if not isinstance(resource, dict):
            return self._halt(
                "payment_failed",
                "The provider settled the payment but returned no usable resource body.",
                intent,
            )

        try:
            if intent.resource_type == "food_reservation":
                return PurchaseOutcome(
                    ok=True,
                    status_code=result.status_code,
                    receipt=receipt,
                    reservation=Reservation.model_validate(resource),
                )
            return PurchaseOutcome(
                ok=True,
                status_code=result.status_code,
                receipt=receipt,
                booking=DeliveryBooking.model_validate(resource),
            )
        except Exception as exc:  # noqa: BLE001
            return self._halt(
                "payment_failed",
                f"Paid, but the provider's response does not match the frozen contract: {exc}",
                intent,
            )

    @staticmethod
    def _receipt_mismatch(intent: PurchaseIntent, receipt: PaymentReceipt) -> str | None:
        if receipt.invoice_id != intent.invoice_id:
            return (
                f"Receipt invoice {receipt.invoice_id} does not match the authorized "
                f"invoice {intent.invoice_id}."
            )
        if receipt.payee != intent.pay_to:
            return "Receipt payee does not match the authorized recipient."
        if drops.to_int(receipt.amount_drops) != drops.to_int(intent.amount_drops):
            return (
                f"Receipt amount {drops.to_xrp_label(receipt.amount_drops)} does not match "
                f"the authorized {drops.to_xrp_label(intent.amount_drops)}."
            )
        if receipt.network != intent.network:
            return f"Receipt settled on {receipt.network}, not {intent.network}."
        return None


def build_payment_client(settings: config.Settings) -> PaymentClient:
    if settings.payment_mode == "x402":
        return ExecutorPaymentClient(timeout_seconds=settings.request_timeout_seconds)
    if settings.payment_mode == "simulated":
        log.warning(
            "payment mode is 'simulated': no XRPL transaction is submitted and receipts "
            "are synthetic. Set BUYER_AGENT_PAYMENT_MODE=x402 for real settlement."
        )
        return SimulatedPaymentClient()
    raise RuntimeError(f"unknown BUYER_AGENT_PAYMENT_MODE: {settings.payment_mode}")
