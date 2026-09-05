"""`POST /api/delivery/{providerId}/book`.

Payment is fully owned by Person 4's `install_provider_payment`, wired in
`../payment_wiring.py`. By the time this handler runs, the x402 challenge,
trusted request-scoped pricing, and facilitator settlement have already
succeeded for the exact quote in this request -- this handler must not
build a 402 challenge, verify a signature, or compute a price itself, and
it no longer needs to check the Economy Van demo failure (the price
resolver raises that before any challenge is issued). Its only job is the
atomic capacity lock and returning the booking.

The real settlement transaction hash and payer are not available here --
only via the `PAYMENT-RESPONSE` header `install_provider_payment` adds
*after* this handler returns. This handler writes `PENDING_TRANSACTION`/
`PENDING_PAYER` placeholders; `surplusflow_provider_common.receipt_bridge`
(installed after payment_wiring's `install_provider_payment` call) patches
in the real values before the response reaches the client.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from surplusflow_provider_common.converters import booking_to_schema, quote_effective_status
from surplusflow_provider_common.errors import ApiException
from surplusflow_provider_common.ids import new_identifier, new_tracking_code
from surplusflow_provider_common.models import CourierProviderRow, DeliveryBookingRow, DeliveryQuoteRow
from surplusflow_provider_common.receipt_bridge import PENDING_PAYER, PENDING_TRANSACTION, explorer_url
from surplusflow_provider_common.schemas import PurchaseIntent
from surplusflow_provider_common.time_utils import now_utc, to_iso

from ..config import CourierSettings
from ..dependencies import get_db, get_settings

router = APIRouter(prefix="/api", tags=["Providers"])

ProviderIdPath = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
IdempotencyKeyHeader = Annotated[str, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9._:-]{8,128}$")]


@router.post("/delivery/{provider_id}/book", status_code=201)
def book_delivery(
    provider_id: ProviderIdPath,
    intent: PurchaseIntent,
    idempotency_key: IdempotencyKeyHeader,
    db: Session = Depends(get_db),
    settings: CourierSettings = Depends(get_settings),
) -> JSONResponse:
    if provider_id != settings.provider_id:
        raise ApiException(
            error="not_found",
            message=f"This service does not host courier {provider_id!r}.",
            status_code=404,
            retryable=False,
        )

    if intent.resource_type != "delivery_booking" or intent.provider_id != provider_id:
        raise ApiException(
            error="invalid_request",
            message="PurchaseIntent does not describe this courier quote.",
            status_code=422,
            retryable=False,
        )

    provider = db.get(CourierProviderRow, provider_id)
    quote = db.get(DeliveryQuoteRow, intent.resource_id)
    if provider is None or quote is None or quote.provider_id != provider_id:
        raise ApiException(
            error="not_found",
            message=f"Quote {intent.resource_id!r} does not exist for provider {provider_id!r}.",
            status_code=404,
            retryable=False,
        )

    now = now_utc()
    # payment_wiring.make_courier_price_resolver already re-checked
    # availability against this same quote immediately before settlement
    # succeeded. This is a defensive re-check against a race between that
    # check and this write, not the primary gate.
    if quote_effective_status(quote, at=now) != "available":
        raise ApiException(
            error="provider_unavailable",
            message="This booking is no longer available.",
            status_code=409,
            retryable=True,
        )

    booking = DeliveryBookingRow(
        booking_id=new_identifier("booking"),
        run_id=intent.run_id,
        provider_id=provider_id,
        quote_id=quote.quote_id,
        status="confirmed",
        pickup_eta=quote.pickup_eta,
        delivery_eta=quote.delivery_eta,
        tracking_code=new_tracking_code(provider_id),
        payment_receipt={
            "success": True,
            "transaction": PENDING_TRANSACTION,
            "network": "xrpl:1",
            "payer": PENDING_PAYER,
            "payee": provider.pay_to,
            "amountDrops": quote.price_drops,
            "invoiceId": intent.invoice_id,
            "validated": True,
            "validatedAt": to_iso(now),
            "explorerUrl": explorer_url(PENDING_TRANSACTION),
        },
        invoice_id=intent.invoice_id,
        idempotency_key=idempotency_key,
        created_at=now,
    )
    db.add(booking)
    db.commit()

    body = booking_to_schema(booking).model_dump(mode="json", by_alias=True)
    return JSONResponse(status_code=201, content=body)
