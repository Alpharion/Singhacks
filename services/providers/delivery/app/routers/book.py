"""`POST /api/delivery/{providerId}/book` -- x402-protected courier booking.

Uses the same 402 -> sign -> retry -> 201 sequence as
`services/providers/sellers/app/routers/reserve.py`. Additionally, when
this instance is configured with `simulate_failure` (Economy Van by
default via `DEMO_ECONOMY_COURIER_FAILURE`), every booking attempt is
rejected with `503 provider_unavailable` before payment even starts, so
the buyer agent must replan -- PROJECT_CONTEXT.md section 5: "Courier
services... Simulate one capacity or route failure for fallback testing."
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from surplusflow_provider_common.converters import booking_to_schema, quote_effective_status
from surplusflow_provider_common.errors import ApiException, new_request_id
from surplusflow_provider_common.idempotency import ReplayedResponse, check_idempotency, store_idempotent_response
from surplusflow_provider_common.ids import new_identifier, new_tracking_code
from surplusflow_provider_common.models import CourierProviderRow, DeliveryBookingRow, DeliveryQuoteRow
from surplusflow_provider_common.payments import (
    PaymentVerificationError,
    PendingPayment,
    encode_header,
    get_payment_adapter,
    source_tag_from_invoice,
)
from surplusflow_provider_common.schemas import ApiError, PurchaseIntent
from surplusflow_provider_common.time_utils import now_utc

from ..config import CourierSettings
from ..dependencies import get_db, get_settings

router = APIRouter(prefix="/api", tags=["Providers"])

ProviderIdPath = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
IdempotencyKeyHeader = Annotated[str, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9._:-]{8,128}$")]

_PAYMENT_ERROR_STATUS = {
    "network_mismatch": 422,
    "invoice_mismatch": 409,
    "payment_replayed": 409,
    "payment_failed": 402,
    "payment_timeout": 402,
}


def _error_response(*, error: str, message: str, status_code: int, retryable: bool, details: dict | None = None):
    body = ApiError(error=error, message=message, retryable=retryable, request_id=new_request_id(), details=details)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json", by_alias=True, exclude_none=True))


@router.post("/delivery/{provider_id}/book", status_code=201)
def book_delivery(
    provider_id: ProviderIdPath,
    intent: PurchaseIntent,
    idempotency_key: IdempotencyKeyHeader,
    payment_signature: Annotated[str | None, Header(alias="PAYMENT-SIGNATURE")] = None,
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

    if settings.simulate_failure:
        return _error_response(
            error="provider_unavailable",
            message=f"{provider_id} cannot accept the route because its remaining vehicle became unavailable.",
            status_code=503,
            retryable=True,
            details={"providerId": provider_id, "quoteId": intent.resource_id},
        )

    if idempotency_key != intent.idempotency_key:
        raise ApiException(
            error="invalid_request",
            message="Idempotency-Key header must equal PurchaseIntent.idempotencyKey.",
            status_code=422,
            retryable=False,
        )

    if intent.resource_type != "delivery_booking" or intent.resource_id is None or intent.provider_id != provider_id:
        raise ApiException(
            error="invalid_request",
            message="PurchaseIntent does not describe this courier quote.",
            status_code=422,
            retryable=False,
        )

    request_body = intent.model_dump(mode="json", by_alias=True)
    scope = f"courier_book:{provider_id}:{intent.resource_id}"
    try:
        check_idempotency(db, scope=scope, idempotency_key=idempotency_key, request_body=request_body)
    except ReplayedResponse as replay:
        return JSONResponse(status_code=replay.status_code, content=replay.body, headers=replay.headers)

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
    effective_status = quote_effective_status(quote, at=now)
    if effective_status == "expired":
        return _error_response(
            error="quote_expired", message="This delivery quote has expired.", status_code=409, retryable=False
        )
    if effective_status == "unavailable":
        return _error_response(
            error="provider_unavailable", message="This courier is no longer available.", status_code=409, retryable=True
        )

    if intent.pay_to != provider.pay_to:
        raise ApiException(
            error="invalid_request", message="PurchaseIntent.payTo does not match this courier.", status_code=422, retryable=False
        )
    if intent.amount_drops != quote.price_drops:
        raise ApiException(
            error="invalid_request",
            message=f"PurchaseIntent.amountDrops must equal {quote.price_drops} for this quote.",
            status_code=422,
            retryable=False,
        )
    if intent.expires_at <= now:
        return _error_response(
            error="invalid_request", message="PurchaseIntent has expired; request a fresh intent.", status_code=422, retryable=False
        )

    existing_invoice = (
        db.query(DeliveryBookingRow)
        .filter(
            DeliveryBookingRow.invoice_id == intent.invoice_id,
            DeliveryBookingRow.idempotency_key != idempotency_key,
        )
        .first()
    )
    if existing_invoice is not None:
        return _error_response(
            error="payment_replayed",
            message="This invoice ID has already been settled for a different request.",
            status_code=409,
            retryable=False,
        )

    pending = PendingPayment(
        pay_to=provider.pay_to,
        amount_drops=intent.amount_drops,
        invoice_id=intent.invoice_id,
        source_tag=source_tag_from_invoice(intent.invoice_id),
    )
    adapter = get_payment_adapter()

    if payment_signature is None:
        requirement = adapter.build_requirement(pending)
        header_value = encode_header(requirement.model_dump(mode="json", by_alias=True))
        body = ApiError(
            error="payment_required",
            message="An XRPL payment is required to complete this booking.",
            retryable=True,
            request_id=new_request_id(),
        )
        return JSONResponse(
            status_code=402,
            content=body.model_dump(mode="json", by_alias=True, exclude_none=True),
            headers={"PAYMENT-REQUIRED": header_value},
        )

    try:
        receipt = adapter.verify_and_settle(payment_signature, pending)
    except PaymentVerificationError as exc:
        return _error_response(
            error=exc.error,
            message=exc.message,
            status_code=_PAYMENT_ERROR_STATUS.get(exc.error, 402),
            retryable=exc.retryable,
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
        payment_receipt=receipt.model_dump(mode="json", by_alias=True),
        invoice_id=intent.invoice_id,
        idempotency_key=idempotency_key,
        created_at=now,
    )
    db.add(booking)
    db.commit()

    response_body = booking_to_schema(booking).model_dump(mode="json", by_alias=True)
    response_headers = {"PAYMENT-RESPONSE": encode_header(receipt.model_dump(mode="json", by_alias=True))}
    store_idempotent_response(
        db,
        scope=scope,
        idempotency_key=idempotency_key,
        request_body=request_body,
        status_code=201,
        response_body=response_body,
        headers=response_headers,
    )
    return JSONResponse(status_code=201, content=response_body, headers=response_headers)
