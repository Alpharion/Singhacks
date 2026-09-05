"""Row -> wire-schema conversions shared by the marketplace and providers."""

from __future__ import annotations

from .models import DeliveryBookingRow, DeliveryQuoteRow, FoodOfferRow, ReservationRow
from .schemas import DeliveryBooking, DeliveryQuote, FoodOffer, Location, PaymentReceipt, Reservation, TimeWindow
from .time_utils import ensure_aware, now_utc


def offer_effective_status(offer: FoodOfferRow, *, at) -> str:  # noqa: ANN001
    if offer.status in ("withdrawn", "sold_out"):
        return offer.status
    if ensure_aware(offer.expires_at) <= at:
        return "expired"
    if offer.quantity_available <= 0:
        return "sold_out"
    return offer.status


def offer_to_schema(offer: FoodOfferRow, *, seller_name: str, pay_to: str, base_url: str) -> FoodOffer:
    status = offer_effective_status(offer, at=now_utc())
    return FoodOffer(
        offer_id=offer.offer_id,
        seller_id=offer.seller_id,
        seller_name=seller_name,
        reservation_endpoint=f"{base_url}/api/sellers/{offer.seller_id}/offers/{offer.offer_id}/reserve",
        pay_to=pay_to,
        title=offer.title,
        description=offer.description,
        dietary_tags=offer.dietary_tags,
        quantity_available=offer.quantity_available,
        unit_price_drops=offer.unit_price_drops,
        location=Location.model_validate(offer.location),
        prepared_at=offer.prepared_at,
        expires_at=offer.expires_at,
        pickup_window=TimeWindow(start=offer.pickup_window_start, end=offer.pickup_window_end),
        reliability_score=offer.reliability_score,
        status=status,
        updated_at=offer.updated_at,
    )


def quote_effective_status(quote: DeliveryQuoteRow, *, at) -> str:  # noqa: ANN001
    if quote.status == "unavailable":
        return "unavailable"
    if ensure_aware(quote.valid_until) <= at:
        return "expired"
    return quote.status


def quote_to_schema(quote: DeliveryQuoteRow, *, provider_name: str, pay_to: str, base_url: str) -> DeliveryQuote:
    status = quote_effective_status(quote, at=now_utc())
    return DeliveryQuote(
        quote_id=quote.quote_id,
        provider_id=quote.provider_id,
        provider_name=provider_name,
        booking_endpoint=f"{base_url}/api/delivery/{quote.provider_id}/book",
        pay_to=pay_to,
        pickup_seller_ids=quote.pickup_seller_ids,
        destination_zone=quote.destination_zone,
        capacity_meals=quote.capacity_meals,
        price_drops=quote.price_drops,
        pickup_eta=quote.pickup_eta,
        delivery_eta=quote.delivery_eta,
        valid_until=quote.valid_until,
        reliability_score=quote.reliability_score,
        status=status,
    )


def reservation_to_schema(row: ReservationRow) -> Reservation:
    return Reservation(
        reservation_id=row.reservation_id,
        run_id=row.run_id,
        seller_id=row.seller_id,
        offer_id=row.offer_id,
        quantity=row.quantity,
        status=row.status,
        pickup_window=TimeWindow(start=row.pickup_window_start, end=row.pickup_window_end),
        pickup_token=row.pickup_token,
        payment_receipt=PaymentReceipt.model_validate(row.payment_receipt),
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def booking_to_schema(row: DeliveryBookingRow) -> DeliveryBooking:
    return DeliveryBooking(
        booking_id=row.booking_id,
        run_id=row.run_id,
        provider_id=row.provider_id,
        quote_id=row.quote_id,
        status=row.status,
        pickup_eta=row.pickup_eta,
        delivery_eta=row.delivery_eta,
        tracking_code=row.tracking_code,
        payment_receipt=PaymentReceipt.model_validate(row.payment_receipt),
        created_at=row.created_at,
    )
