"""`GET /api/offers` -- free food-offer discovery (Contract Freeze v1.0.0)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from surplusflow_provider_common.converters import offer_to_schema
from surplusflow_provider_common.models import FoodOfferRow, SellerRow
from surplusflow_provider_common.schemas import DietaryTag, FoodOffersResponse
from surplusflow_provider_common.time_utils import now_utc

from ..dependencies import get_db

router = APIRouter(prefix="/api", tags=["Discovery"])


@router.get("/offers", response_model=FoodOffersResponse)
def list_food_offers(
    dietary_tag: DietaryTag | None = Query(default=None, alias="dietaryTag"),
    available_at: datetime | None = Query(default=None, alias="availableAt"),
    min_quantity: int | None = Query(default=None, alias="minQuantity", ge=1),
    db: Session = Depends(get_db),
) -> FoodOffersResponse:
    sellers = {row.seller_id: row for row in db.query(SellerRow).all()}

    offers = []
    for offer_row in db.query(FoodOfferRow).all():
        seller = sellers.get(offer_row.seller_id)
        if seller is None:
            continue
        offer = offer_to_schema(
            offer_row, seller_name=seller.seller_name, pay_to=seller.pay_to, base_url=seller.base_url
        )
        if dietary_tag is not None and dietary_tag not in offer.dietary_tags:
            continue
        if min_quantity is not None and offer.quantity_available < min_quantity:
            continue
        if available_at is not None and not (offer.prepared_at <= available_at <= offer.expires_at):
            continue
        offers.append(offer)

    return FoodOffersResponse(offers=offers, generated_at=now_utc())
