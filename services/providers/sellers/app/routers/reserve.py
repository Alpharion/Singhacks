"""`POST /api/sellers/{sellerId}/offers/{offerId}/reserve` -- x402-protected
food reservation.

Implements the payment sequence frozen in `PROJECT_CONTEXT.md` section 7:
the first call returns HTTP 402 with a `PAYMENT-REQUIRED` challenge; the
buyer retries the identical request with the same `Idempotency-Key` plus a
`PAYMENT-SIGNATURE` header; only after `PaymentAdapter.verify_and_settle`
validates the payment does this route lock inventory and return the
reservation.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from surplusflow_provider_common.converters import offer_effective_status, reservation_to_schema
from surplusflow_provider_common.errors import ApiException, new_request_id
from surplusflow_provider_common.idempotency import ReplayedResponse, check_idempotency, store_idempotent_response
from surplusflow_provider_common.ids import new_identifier, new_pickup_token
from surplusflow_provider_common.models import FoodOfferRow, ReservationRow, SellerRow
from surplusflow_provider_common.payments import (
    PaymentVerificationError,
    PendingPayment,
    encode_header,
    get_payment_adapter,
    source_tag_from_invoice,
)
from surplusflow_provider_common.schemas import ApiError, PurchaseIntent
from surplusflow_provider_common.time_utils import now_utc

from ..config import SellerSettings
from ..dependencies import get_db, get_settings

router = APIRouter(prefix="/api", tags=["Providers"])

IdentifierPath = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
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


@router.post("/sellers/{seller_id}/offers/{offer_id}/reserve", status_code=201)
def reserve_food_offer(
    seller_id: IdentifierPath,
    offer_id: IdentifierPath,
    intent: PurchaseIntent,
    idempotency_key: IdempotencyKeyHeader,
    payment_signature: Annotated[str | None, Header(alias="PAYMENT-SIGNATURE")] = None,
    db: Session = Depends(get_db),
    settings: SellerSettings = Depends(get_settings),
) -> JSONResponse:
    if seller_id != settings.seller_id:
        raise ApiException(
            error="not_found",
            message=f"This service does not host seller {seller_id!r}.",
            status_code=404,
            retryable=False,
        )

    if idempotency_key != intent.idempotency_key:
        raise ApiException(
            error="invalid_request",
            message="Idempotency-Key header must equal PurchaseIntent.idempotencyKey.",
            status_code=422,
            retryable=False,
        )

    if intent.resource_type != "food_reservation" or intent.resource_id != offer_id or intent.provider_id != seller_id:
        raise ApiException(
            error="invalid_request",
            message="PurchaseIntent does not describe this seller offer.",
            status_code=422,
            retryable=False,
        )

    if intent.quantity is None or intent.quantity < 1:
        raise ApiException(
            error="invalid_request",
            message="PurchaseIntent.quantity is required for a food_reservation.",
            status_code=422,
            retryable=False,
        )

    request_body = intent.model_dump(mode="json", by_alias=True)
    scope = f"seller_reserve:{seller_id}:{offer_id}"
    try:
        check_idempotency(db, scope=scope, idempotency_key=idempotency_key, request_body=request_body)
    except ReplayedResponse as replay:
        return JSONResponse(status_code=replay.status_code, content=replay.body, headers=replay.headers)

    seller = db.get(SellerRow, seller_id)
    offer = db.get(FoodOfferRow, offer_id)
    if seller is None or offer is None or offer.seller_id != seller_id:
        raise ApiException(
            error="not_found",
            message=f"Offer {offer_id!r} does not exist for seller {seller_id!r}.",
            status_code=404,
            retryable=False,
        )

    now = now_utc()
    effective_status = offer_effective_status(offer, at=now)
    if effective_status == "expired":
        return _error_response(
            error="offer_expired", message="This offer has expired.", status_code=409, retryable=False
        )
    if effective_status in ("sold_out", "withdrawn"):
        return _error_response(
            error="offer_sold_out", message="This offer is no longer available.", status_code=409, retryable=False
        )
    if intent.quantity > offer.quantity_available:
        return _error_response(
            error="offer_sold_out",
            message=f"Only {offer.quantity_available} meals remain, {intent.quantity} were requested.",
            status_code=409,
            retryable=False,
        )

    if intent.pay_to != seller.pay_to:
        raise ApiException(
            error="invalid_request", message="PurchaseIntent.payTo does not match this seller.", status_code=422, retryable=False
        )
    expected_amount = str(intent.quantity * int(offer.unit_price_drops))
    if intent.amount_drops != expected_amount:
        raise ApiException(
            error="invalid_request",
            message=f"PurchaseIntent.amountDrops must equal {expected_amount} for this quantity.",
            status_code=422,
            retryable=False,
        )
    if intent.expires_at <= now:
        return _error_response(
            error="invalid_request", message="PurchaseIntent has expired; request a fresh intent.", status_code=422, retryable=False
        )

    existing_invoice = (
        db.query(ReservationRow)
        .filter(ReservationRow.invoice_id == intent.invoice_id, ReservationRow.idempotency_key != idempotency_key)
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
        pay_to=seller.pay_to,
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
            message="An XRPL payment is required to complete this reservation.",
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

    offer.quantity_available -= intent.quantity
    if offer.quantity_available <= 0:
        offer.status = "sold_out"
    offer.updated_at = now

    reservation = ReservationRow(
        reservation_id=new_identifier("reservation"),
        run_id=intent.run_id,
        seller_id=seller_id,
        offer_id=offer_id,
        quantity=intent.quantity,
        status="confirmed",
        pickup_window_start=offer.pickup_window_start,
        pickup_window_end=offer.pickup_window_end,
        pickup_token=new_pickup_token(seller_id),
        payment_receipt=receipt.model_dump(mode="json", by_alias=True),
        invoice_id=intent.invoice_id,
        idempotency_key=idempotency_key,
        created_at=now,
        expires_at=offer.pickup_window_end,
    )
    db.add(reservation)
    db.commit()

    response_body = reservation_to_schema(reservation).model_dump(mode="json", by_alias=True)
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
