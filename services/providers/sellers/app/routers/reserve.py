"""`POST /api/sellers/{sellerId}/offers/{offerId}/reserve`.

Payment is fully owned by Person 4's `install_provider_payment`, wired in
`../payment_wiring.py`. By the time this handler runs, the x402 challenge,
trusted request-scoped pricing, and facilitator settlement have already
succeeded for the exact quantity in this request -- this handler must not
build a 402 challenge, verify a signature, or compute a price itself. Its
only job is the atomic inventory lock and returning the reservation.

The real settlement transaction hash and payer are not available here --
only via the `PAYMENT-RESPONSE` header `install_provider_payment` adds
*after* this handler returns. This handler writes `PENDING_TRANSACTION`/
`PENDING_PAYER` placeholders; `surplusflow_provider_common.receipt_bridge`
(installed after payment_wiring's `install_provider_payment` calls) patches
in the real values before the response reaches the client.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from surplusflow_provider_common.converters import offer_effective_status, reservation_to_schema
from surplusflow_provider_common.errors import ApiException
from surplusflow_provider_common.ids import new_identifier, new_pickup_token
from surplusflow_provider_common.models import FoodOfferRow, ReservationRow, SellerRow
from surplusflow_provider_common.receipt_bridge import PENDING_PAYER, PENDING_TRANSACTION, explorer_url
from surplusflow_provider_common.schemas import PurchaseIntent
from surplusflow_provider_common.time_utils import now_utc, to_iso

from ..config import SellerSettings
from ..dependencies import get_db, get_settings

router = APIRouter(prefix="/api", tags=["Providers"])

IdentifierPath = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
IdempotencyKeyHeader = Annotated[str, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9._:-]{8,128}$")]


@router.post("/sellers/{seller_id}/offers/{offer_id}/reserve", status_code=201)
def reserve_food_offer(
    seller_id: IdentifierPath,
    offer_id: IdentifierPath,
    intent: PurchaseIntent,
    idempotency_key: IdempotencyKeyHeader,
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

    if intent.resource_type != "food_reservation" or intent.resource_id != offer_id or intent.provider_id != seller_id:
        raise ApiException(
            error="invalid_request",
            message="PurchaseIntent does not describe this seller offer.",
            status_code=422,
            retryable=False,
        )

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
    # payment_wiring.make_seller_price_resolver already re-checked
    # availability and quantity against this same offer immediately before
    # settlement succeeded. This is a defensive re-check against a race
    # between that check and this write, not the primary gate.
    if (
        offer_effective_status(offer, at=now) != "available"
        or intent.quantity is None
        or intent.quantity > offer.quantity_available
    ):
        raise ApiException(
            error="offer_sold_out",
            message="This offer sold out between payment and fulfilment.",
            status_code=409,
            retryable=False,
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
        payment_receipt={
            "success": True,
            "transaction": PENDING_TRANSACTION,
            "network": "xrpl:1",
            "payer": PENDING_PAYER,
            "payee": seller.pay_to,
            "amountDrops": str(intent.quantity * int(offer.unit_price_drops)),
            "invoiceId": intent.invoice_id,
            "validated": True,
            "validatedAt": to_iso(now),
            "explorerUrl": explorer_url(PENDING_TRANSACTION),
        },
        invoice_id=intent.invoice_id,
        idempotency_key=idempotency_key,
        created_at=now,
        expires_at=offer.pickup_window_end,
    )
    db.add(reservation)
    db.commit()

    body = reservation_to_schema(reservation).model_dump(mode="json", by_alias=True)
    return JSONResponse(status_code=201, content=body)
