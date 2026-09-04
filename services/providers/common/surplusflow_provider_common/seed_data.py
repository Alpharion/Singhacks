"""Idempotent demo seed data shared by the marketplace and provider simulators.

IDs, seller/courier names, `payTo` addresses, prices, and dietary tags match
`packages/contracts/fixtures/food-offers.json` and `delivery-quotes.json` so
Person 1's UI fixtures and Person 2's tests describe the same demo world
this service actually serves. Timestamps are generated relative to service
start time (rather than the fixtures' fixed dates) so offers and quotes are
never already expired when a teammate boots the service.

The one seller offer that does not satisfy the "vegetarian" demo goal
(Central Grill's chicken meals) is kept, matching the fixture note, so the
buyer agent has a real dietary-incompatible offer to reject.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from .models import CourierProviderRow, DeliveryQuoteRow, FoodOfferRow, SellerRow
from .time_utils import now_utc

SELLERS: list[dict] = [
    {
        "seller_id": "seller_bakery_001",
        "seller_name": "Green Oven Bakery",
        "pay_to": "rFoodA1111111111111111111111111",
        "base_url": "http://localhost:8011",
    },
    {
        "seller_id": "seller_hotel_001",
        "seller_name": "Harbour Hotel Kitchen",
        "pay_to": "rFoodB1111111111111111111111111",
        "base_url": "http://localhost:8012",
    },
    {
        "seller_id": "seller_grill_001",
        "seller_name": "Central Grill",
        "pay_to": "rFoodC1111111111111111111111111",
        "base_url": "http://localhost:8013",
    },
]

COURIERS: list[dict] = [
    {
        "provider_id": "courier_fast_001",
        "provider_name": "FastRoute Courier",
        "pay_to": "rRideA1111111111111111111111111",
        "base_url": "http://localhost:8021",
        "simulate_failure": False,
    },
    {
        "provider_id": "courier_economy_001",
        "provider_name": "Economy Van",
        "pay_to": "rRideB1111111111111111111111111",
        "base_url": "http://localhost:8022",
        "simulate_failure": True,
    },
]


def _offer_defs(now):  # noqa: ANN001
    return [
        {
            "offer_id": "offer_bakery_001",
            "seller_id": "seller_bakery_001",
            "title": "Vegetarian bakery meal boxes",
            "description": "Assorted vegetarian sandwiches, fruit, and pastry boxes.",
            "dietary_tags": ["vegetarian", "nut_free"],
            "quantity_available": 60,
            "unit_price_drops": "600000",
            "location": {"zone": "Queenstown", "latitude": 1.2942, "longitude": 103.7861},
            "prepared_at": now - timedelta(hours=3),
            "expires_at": now + timedelta(hours=7),
            "pickup_window_start": now + timedelta(hours=1),
            "pickup_window_end": now + timedelta(hours=2, minutes=30),
            "reliability_score": 0.94,
            "status": "available",
            "updated_at": now,
        },
        {
            "offer_id": "offer_hotel_001",
            "seller_id": "seller_hotel_001",
            "title": "Vegetarian rice and vegetable bowls",
            "description": "Chilled same-day surplus buffet bowls.",
            "dietary_tags": ["vegetarian", "halal"],
            "quantity_available": 60,
            "unit_price_drops": "650000",
            "location": {"zone": "Tanjong Pagar", "latitude": 1.2764, "longitude": 103.8432},
            "prepared_at": now - timedelta(hours=3, minutes=30),
            "expires_at": now + timedelta(hours=7, minutes=30),
            "pickup_window_start": now + timedelta(hours=1, minutes=30),
            "pickup_window_end": now + timedelta(hours=3),
            "reliability_score": 0.91,
            "status": "available",
            "updated_at": now,
        },
        {
            "offer_id": "offer_grill_001",
            "seller_id": "seller_grill_001",
            "title": "Chicken meal boxes",
            "description": "Low-cost chicken meals that do not satisfy the vegetarian goal.",
            "dietary_tags": ["halal", "nut_free"],
            "quantity_available": 100,
            "unit_price_drops": "400000",
            "location": {"zone": "Outram", "latitude": 1.2819, "longitude": 103.8392},
            "prepared_at": now - timedelta(hours=4),
            "expires_at": now + timedelta(hours=6, minutes=30),
            "pickup_window_start": now + timedelta(hours=1),
            "pickup_window_end": now + timedelta(hours=2),
            "reliability_score": 0.97,
            "status": "available",
            "updated_at": now,
        },
    ]


def _quote_defs(now):  # noqa: ANN001
    return [
        {
            "quote_id": "quote_fast_001",
            "provider_id": "courier_fast_001",
            "pickup_seller_ids": ["seller_bakery_001", "seller_hotel_001"],
            "destination_zone": "Queenstown",
            "capacity_meals": 150,
            "price_drops": "12000000",
            "pickup_eta": now + timedelta(hours=2),
            "delivery_eta": now + timedelta(hours=3, minutes=35),
            "valid_until": now + timedelta(hours=4),
            "reliability_score": 0.96,
            "status": "available",
        },
        {
            "quote_id": "quote_economy_001",
            "provider_id": "courier_economy_001",
            "pickup_seller_ids": ["seller_bakery_001", "seller_hotel_001"],
            "destination_zone": "Queenstown",
            "capacity_meals": 120,
            "price_drops": "10000000",
            "pickup_eta": now + timedelta(hours=2, minutes=30),
            "delivery_eta": now + timedelta(hours=3, minutes=50),
            "valid_until": now + timedelta(hours=4),
            "reliability_score": 0.82,
            # Discovery reports this quote as available; the demo failure is
            # simulated at booking time (see providers/delivery's
            # DEMO_ECONOMY_COURIER_FAILURE handling) so the buyer agent can
            # select it and then observe a real 503 + replan.
            "status": "available",
        },
    ]


def ensure_seed_data(session: Session) -> None:
    """Populate demo sellers/offers/couriers/quotes once, idempotently."""

    if session.query(SellerRow).count() > 0:
        return

    now = now_utc()

    # Two commits: parent rows (sellers, couriers) must exist before the
    # foreign-key-bearing child rows (offers, quotes) are inserted.
    for seller in SELLERS:
        session.add(SellerRow(**seller))
    for courier in COURIERS:
        session.add(CourierProviderRow(**courier))
    session.commit()

    for offer in _offer_defs(now):
        session.add(FoodOfferRow(**offer))
    for quote in _quote_defs(now):
        session.add(DeliveryQuoteRow(**quote))
    session.commit()
