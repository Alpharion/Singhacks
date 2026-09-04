"""The payment boundary.

This module is the only place the agent touches a paid endpoint, and it is
deliberately thin. It never builds, signs, or inspects an XRPL transaction and
never reads a wallet seed; the x402 challenge/settle/retry cycle belongs to the
payments package owned by Person 4.

Integration contract expected from that package (configurable with
``BUYER_AGENT_PAYMENT_ADAPTER=module:factory``, default
``surplusflow_payments:build_client``): a zero-argument factory returning an
object with

    async def purchase(intent: dict) -> dict

where ``intent`` is the wire form of a PurchaseIntent and the result is
``{"statusCode": int, "body": dict, "receipt": dict | None}``. ``body`` is the
provider's Reservation, DeliveryBooking, or ApiError payload; ``receipt`` is the
normalized PAYMENT-RESPONSE. Any other shape is treated as a payment failure.
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from . import config, drops, ids, timeutil
from .models import (
    ApiError,
    DeliveryBooking,
    DeliveryQuote,
    FoodOffer,
    PaymentReceipt,
    PurchaseIntent,
    Reservation,
)

log = logging.getLogger(__name__)

SIMULATED_PAYER = "rBuyer1111111111111111111111111"


@dataclass(frozen=True)
class PurchaseOutcome:
    ok: bool
    status_code: int
    receipt: PaymentReceipt | None = None
    reservation: Reservation | None = None
    booking: DeliveryBooking | None = None
    error: ApiError | None = None
    simulated: bool = False


class PaymentClient(Protocol):
    async def purchase(
        self,
        intent: PurchaseIntent,
        *,
        offer: FoodOffer | None = None,
        quote: DeliveryQuote | None = None,
        now: datetime | None = None,
    ) -> PurchaseOutcome: ...

    async def aclose(self) -> None: ...


def _synthetic_hash(invoice_id: str) -> str:
    """A hash that cannot be mistaken for a real one: sixteen leading zeros."""
    digest = hashlib.sha256(invoice_id.encode()).hexdigest().upper()
    return "0" * 16 + digest[:48]


class SimulatedPaymentClient:
    """Offline stand-in for Phase 1 development and tests.

    It settles nothing. Receipts it returns carry a hash with sixteen leading
    zeros and a localhost explorer URL, so a simulated run can never be shown as
    evidence of an XRPL payment.
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
        now: datetime | None = None,
    ) -> PurchaseOutcome:
        now = now or timeutil.now()
        if intent.provider_id in self._failing:
            return PurchaseOutcome(
                ok=False,
                status_code=503,
                simulated=True,
                error=ApiError(
                    error="provider_unavailable",
                    message=f"{intent.provider_id} cannot fulfil this request right now.",
                    retryable=True,
                    request_id=ids.unique("request"),
                    details={"providerId": intent.provider_id, "resourceId": intent.resource_id},
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


class X402PaymentClient:
    """Delegates the real 402 challenge, settlement, and retry to Person 4."""

    def __init__(self, adapter: object | None = None) -> None:
        config.assert_no_seed_access()
        self._adapter = adapter or self._load_adapter()

    @staticmethod
    def _load_adapter() -> object:
        target = os.getenv("BUYER_AGENT_PAYMENT_ADAPTER", "surplusflow_payments:build_client")
        module_name, _, attribute = target.partition(":")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(
                f"x402 payment mode needs the payments package ({target}); it is not "
                "installed yet. Run with BUYER_AGENT_PAYMENT_MODE=simulated until "
                "Person 4 publishes the adapter."
            ) from exc
        return getattr(module, attribute)()

    async def aclose(self) -> None:
        closer = getattr(self._adapter, "aclose", None)
        if closer is not None:
            await closer()

    async def purchase(
        self,
        intent: PurchaseIntent,
        *,
        offer: FoodOffer | None = None,
        quote: DeliveryQuote | None = None,
        now: datetime | None = None,
    ) -> PurchaseOutcome:
        try:
            raw = await self._adapter.purchase(intent.wire())
        except Exception as exc:  # noqa: BLE001 - a failed payment must become a replan
            log.exception("payment adapter raised for intent %s", intent.intent_id)
            return PurchaseOutcome(
                ok=False,
                status_code=502,
                error=ApiError(
                    error="payment_failed",
                    message=f"Payment could not be completed: {exc}",
                    retryable=True,
                    request_id=ids.unique("request"),
                ),
            )
        return self._normalize(intent, raw)

    def _normalize(self, intent: PurchaseIntent, raw: dict) -> PurchaseOutcome:
        status = int(raw.get("statusCode", 0))
        body = raw.get("body") or {}
        receipt_body = raw.get("receipt")

        if status not in (200, 201) or not receipt_body:
            return PurchaseOutcome(
                ok=False,
                status_code=status or 502,
                error=self._as_error(body, status),
            )

        receipt = PaymentReceipt.model_validate(receipt_body)
        mismatch = self._receipt_mismatch(intent, receipt)
        if mismatch:
            # Settled money must match the authorized intent or the run stops here.
            return PurchaseOutcome(
                ok=False,
                status_code=status,
                error=ApiError(
                    error="invoice_mismatch",
                    message=mismatch,
                    retryable=False,
                    request_id=ids.unique("request"),
                ),
            )

        if intent.resource_type == "food_reservation":
            return PurchaseOutcome(
                ok=True,
                status_code=status,
                receipt=receipt,
                reservation=Reservation.model_validate(body),
            )
        return PurchaseOutcome(
            ok=True,
            status_code=status,
            receipt=receipt,
            booking=DeliveryBooking.model_validate(body),
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

    @staticmethod
    def _as_error(body: dict, status: int) -> ApiError:
        try:
            return ApiError.model_validate(body)
        except Exception:  # noqa: BLE001 - providers may return an unmapped body
            return ApiError(
                error="payment_failed" if status >= 500 else "provider_unavailable",
                message=f"Provider returned HTTP {status}.",
                retryable=status >= 500 or status == 503,
                request_id=ids.unique("request"),
            )


def build_payment_client(settings: config.Settings) -> PaymentClient:
    if settings.payment_mode == "x402":
        return X402PaymentClient()
    if settings.payment_mode == "simulated":
        log.warning(
            "payment mode is 'simulated': no XRPL transaction is submitted and receipts "
            "are synthetic. Set BUYER_AGENT_PAYMENT_MODE=x402 for real settlement."
        )
        return SimulatedPaymentClient()
    raise RuntimeError(f"unknown BUYER_AGENT_PAYMENT_MODE: {settings.payment_mode}")
