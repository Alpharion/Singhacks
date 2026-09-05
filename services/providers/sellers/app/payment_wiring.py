"""Wires Person 4's `install_provider_payment` into this seller instance.

Registered once per offer this seller currently has, using **trusted
request-scoped pricing** (`docs/architecture/PAYMENTS_HANDOFF.md`, Person 3
integration section): the resolver recomputes `quantity * unitPriceDrops`
from this service's own offer data and returns that -- it never returns
the buyer-supplied `PurchaseIntent.amountDrops`. This is what lets the
same offer be reserved for any quantity up to what remains (for example
40 of a 60-meal hotel offer), unlike a single fixed price per path.

Never imports anything from `packages/payments/**` other than its public
API, and never edits it.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.orm import Session
from surplusflow_payments import (
    ProviderPaymentConfig,
    ProviderPricingError,
    ProviderRequestContext,
    PurchaseIntent,
    SQLiteInvoiceStore,
    SQLiteProviderResponseStore,
    install_provider_payment,
)
from surplusflow_provider_common.converters import offer_effective_status
from surplusflow_provider_common.db import get_database_url, get_session_factory
from surplusflow_provider_common.models import FoodOfferRow, ReservationRow
from surplusflow_provider_common.receipt_bridge import install_receipt_bridge
from surplusflow_provider_common.time_utils import now_utc


def _x402_data_dir() -> Path:
    db_path = Path(get_database_url().removeprefix("sqlite:///"))
    data_dir = db_path.parent / "x402"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def make_seller_price_resolver(*, seller_id: str, offer_id: str):
    """Build the trusted price resolver for one specific seller offer.

    Runs *before* the x402 challenge is issued, so this is also where
    "check availability before offering payment" lives for sellers.
    """

    def resolve(context: ProviderRequestContext) -> int:
        intent = PurchaseIntent.model_validate(context.payload)
        if (
            intent.provider_id != seller_id
            or intent.resource_id != offer_id
            or intent.resource_type != "food_reservation"
        ):
            raise ProviderPricingError(
                "PurchaseIntent does not describe this seller offer.",
                error="invalid_request",
                status_code=422,
            )

        session = get_session_factory()()
        try:
            offer = session.get(FoodOfferRow, offer_id)
        finally:
            session.close()

        if offer is None or offer.seller_id != seller_id:
            raise ProviderPricingError(
                f"Offer {offer_id!r} does not exist for seller {seller_id!r}.",
                error="not_found",
                status_code=404,
            )

        status = offer_effective_status(offer, at=now_utc())
        if status == "expired":
            raise ProviderPricingError(
                "This offer has expired.", error="offer_expired", status_code=409
            )
        if status in ("sold_out", "withdrawn"):
            raise ProviderPricingError(
                "This offer is no longer available.",
                error="offer_sold_out",
                status_code=409,
            )
        if intent.quantity is None or intent.quantity < 1:
            raise ProviderPricingError(
                "PurchaseIntent.quantity is required for a food_reservation.",
                error="invalid_request",
                status_code=422,
            )
        if intent.quantity > offer.quantity_available:
            raise ProviderPricingError(
                f"Only {offer.quantity_available} meals remain, "
                f"{intent.quantity} were requested.",
                error="offer_sold_out",
                status_code=409,
            )

        return intent.quantity * int(offer.unit_price_drops)

    return resolve


def patch_reservation_receipt(reservation_id: str, transaction: str, payer: str, url: str) -> None:
    """Fill in the real settlement receipt once `receipt_bridge` has it."""

    session: Session = get_session_factory()()
    try:
        row = session.get(ReservationRow, reservation_id)
        if row is None:
            return
        receipt = dict(row.payment_receipt)
        receipt["transaction"] = transaction
        receipt["payer"] = payer
        receipt["explorerUrl"] = url
        row.payment_receipt = receipt
        session.commit()
    finally:
        session.close()


def install_seller_payments(
    app,
    *,
    seller_id: str,
    offers: list[FoodOfferRow],
    pay_to: str,
    facilitator: object | None = None,
) -> None:
    """`facilitator` overrides the real XRPL testnet facilitator client --
    used only by tests (see tests/conftest.py) to avoid live network calls;
    production boots always leave it `None` and hit the real facilitator."""

    facilitator_url = os.environ.get(
        "XRPL_FACILITATOR_URL", "https://xrpl-facilitator-testnet.t54.ai"
    )
    data_dir = _x402_data_dir()

    for offer in offers:
        protected_path = f"/api/sellers/{seller_id}/offers/{offer.offer_id}/reserve"
        config = ProviderPaymentConfig(
            protected_paths=protected_path,
            pay_to_address=pay_to,
            facilitator_url=facilitator_url,
            description=f"SurplusFlow reservation for {offer.title}",
        )
        install_provider_payment(
            app,
            config,
            SQLiteInvoiceStore(data_dir / f"{offer.offer_id}-invoices.sqlite3"),
            SQLiteProviderResponseStore(data_dir / f"{offer.offer_id}-responses.sqlite3"),
            facilitator=facilitator,
            price_resolver=make_seller_price_resolver(seller_id=seller_id, offer_id=offer.offer_id),
        )

    install_receipt_bridge(app, id_field="reservationId", persist_receipt=patch_reservation_receipt)
