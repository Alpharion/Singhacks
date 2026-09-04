"""SQLAlchemy ORM models backing the marketplace and provider simulators.

These are storage rows, not wire types. `app` routers translate between
these rows and the frozen Pydantic schemas in `schemas.py`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class SellerRow(Base):
    __tablename__ = "sellers"

    seller_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seller_name: Mapped[str] = mapped_column(String(100))
    pay_to: Mapped[str] = mapped_column(String(40))
    base_url: Mapped[str] = mapped_column(String(200))


class FoodOfferRow(Base):
    __tablename__ = "food_offers"

    offer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seller_id: Mapped[str] = mapped_column(String(64), ForeignKey("sellers.seller_id"))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dietary_tags: Mapped[list[str]] = mapped_column(JSON)
    quantity_available: Mapped[int] = mapped_column(Integer)
    unit_price_drops: Mapped[str] = mapped_column(String(32))
    location: Mapped[dict] = mapped_column(JSON)
    prepared_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column()
    pickup_window_start: Mapped[datetime] = mapped_column()
    pickup_window_end: Mapped[datetime] = mapped_column()
    reliability_score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column()


class CourierProviderRow(Base):
    __tablename__ = "courier_providers"

    provider_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(100))
    pay_to: Mapped[str] = mapped_column(String(40))
    base_url: Mapped[str] = mapped_column(String(200))


class DeliveryQuoteRow(Base):
    __tablename__ = "delivery_quotes"

    quote_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), ForeignKey("courier_providers.provider_id"))
    pickup_seller_ids: Mapped[list[str]] = mapped_column(JSON)
    destination_zone: Mapped[str] = mapped_column(String(80))
    capacity_meals: Mapped[int] = mapped_column(Integer)
    price_drops: Mapped[str] = mapped_column(String(32))
    pickup_eta: Mapped[datetime] = mapped_column()
    delivery_eta: Mapped[datetime] = mapped_column()
    valid_until: Mapped[datetime] = mapped_column()
    reliability_score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))


class ReservationRow(Base):
    __tablename__ = "reservations"

    reservation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64))
    seller_id: Mapped[str] = mapped_column(String(64))
    offer_id: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    pickup_window_start: Mapped[datetime] = mapped_column()
    pickup_window_end: Mapped[datetime] = mapped_column()
    pickup_token: Mapped[str | None] = mapped_column(String(256), nullable=True)
    payment_receipt: Mapped[dict] = mapped_column(JSON)
    invoice_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column()


class DeliveryBookingRow(Base):
    __tablename__ = "delivery_bookings"

    booking_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64))
    provider_id: Mapped[str] = mapped_column(String(64))
    quote_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    pickup_eta: Mapped[datetime] = mapped_column()
    delivery_eta: Mapped[datetime] = mapped_column()
    tracking_code: Mapped[str] = mapped_column(String(64))
    payment_receipt: Mapped[dict] = mapped_column(JSON)
    invoice_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column()


class IdempotencyRecordRow(Base):
    """Dedupes retried payment-protected requests per contract section 8.

    Keyed by `f"{scope}:{idempotency_key}"` so sellers and couriers share
    one table without colliding on identical key strings.
    """

    __tablename__ = "idempotency_records"

    record_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(128))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSON)
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column()
