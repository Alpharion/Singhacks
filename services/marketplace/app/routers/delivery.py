"""`POST /api/delivery/quotes` -- free courier-quote discovery for a pickup set."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from surplusflow_provider_common.converters import quote_to_schema
from surplusflow_provider_common.models import CourierProviderRow, DeliveryQuoteRow
from surplusflow_provider_common.schemas import DeliveryQuoteRequest, DeliveryQuotesResponse
from surplusflow_provider_common.time_utils import now_utc

from ..dependencies import get_db

router = APIRouter(prefix="/api", tags=["Discovery"])


@router.post("/delivery/quotes", response_model=DeliveryQuotesResponse)
def list_delivery_quotes(payload: DeliveryQuoteRequest, db: Session = Depends(get_db)) -> DeliveryQuotesResponse:
    requested_seller_ids = {pickup.seller_id for pickup in payload.pickups}
    providers = {row.provider_id: row for row in db.query(CourierProviderRow).all()}

    quotes = []
    for quote_row in db.query(DeliveryQuoteRow).all():
        provider = providers.get(quote_row.provider_id)
        if provider is None:
            continue
        if not requested_seller_ids.intersection(quote_row.pickup_seller_ids):
            continue
        quotes.append(
            quote_to_schema(
                quote_row, provider_name=provider.provider_name, pay_to=provider.pay_to, base_url=provider.base_url
            )
        )

    return DeliveryQuotesResponse(quotes=quotes, generated_at=now_utc())
