"""Wires Person 4's `install_provider_payment` into this courier instance.

`POST /api/delivery/{providerId}/book` has no quote id in the URL (the
quote is chosen in the request body via `PurchaseIntent.resourceId`), so
unlike sellers this needs only **one** `install_provider_payment` call per
courier instance; the resolver looks up whichever quote the request names.

Uses trusted request-scoped pricing (`docs/architecture/PAYMENTS_HANDOFF.md`,
Person 3 integration section): the resolver returns the quote's own stored
`priceDrops`, never the buyer-supplied `PurchaseIntent.amountDrops`.

The deterministic demo failure (Economy Van) is raised from the resolver
itself, so it happens before any payment challenge is issued -- "check
availability before offering payment" and "produce the planned
deterministic provider failure" are the same mechanism here.

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
from surplusflow_provider_common.converters import quote_effective_status
from surplusflow_provider_common.db import get_database_url, get_session_factory
from surplusflow_provider_common.models import DeliveryBookingRow, DeliveryQuoteRow
from surplusflow_provider_common.receipt_bridge import install_receipt_bridge
from surplusflow_provider_common.time_utils import now_utc


def _x402_data_dir() -> Path:
    db_path = Path(get_database_url().removeprefix("sqlite:///"))
    data_dir = db_path.parent / "x402"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def make_courier_price_resolver(*, provider_id: str, simulate_failure: bool):
    def resolve(context: ProviderRequestContext) -> int:
        if simulate_failure:
            raise ProviderPricingError(
                f"{provider_id} cannot accept the route because its remaining "
                "vehicle became unavailable.",
                error="provider_unavailable",
                status_code=503,
                retryable=True,
            )

        intent = PurchaseIntent.model_validate(context.payload)
        if intent.provider_id != provider_id or intent.resource_type != "delivery_booking":
            raise ProviderPricingError(
                "PurchaseIntent does not describe this courier quote.",
                error="invalid_request",
                status_code=422,
            )

        session = get_session_factory()()
        try:
            quote = session.get(DeliveryQuoteRow, intent.resource_id)
        finally:
            session.close()

        if quote is None or quote.provider_id != provider_id:
            raise ProviderPricingError(
                f"Quote {intent.resource_id!r} does not exist for provider {provider_id!r}.",
                error="not_found",
                status_code=404,
            )

        status = quote_effective_status(quote, at=now_utc())
        if status == "expired":
            raise ProviderPricingError(
                "This delivery quote has expired.", error="quote_expired", status_code=409
            )
        if status == "unavailable":
            raise ProviderPricingError(
                "This courier is no longer available.",
                error="provider_unavailable",
                status_code=409,
                retryable=True,
            )

        return int(quote.price_drops)

    return resolve


def patch_booking_receipt(booking_id: str, transaction: str, payer: str, url: str) -> None:
    """Fill in the real settlement receipt once `receipt_bridge` has it."""

    session: Session = get_session_factory()()
    try:
        row = session.get(DeliveryBookingRow, booking_id)
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


def install_courier_payments(
    app,
    *,
    provider_id: str,
    pay_to: str,
    simulate_failure: bool,
    facilitator: object | None = None,
) -> None:
    """`facilitator` overrides the real XRPL testnet facilitator client --
    used only by tests (see tests/conftest.py) to avoid live network calls;
    production boots always leave it `None` and hit the real facilitator."""

    facilitator_url = os.environ.get(
        "XRPL_FACILITATOR_URL", "https://xrpl-facilitator-testnet.t54.ai"
    )
    data_dir = _x402_data_dir()
    protected_path = f"/api/delivery/{provider_id}/book"

    config = ProviderPaymentConfig(
        protected_paths=protected_path,
        pay_to_address=pay_to,
        facilitator_url=facilitator_url,
        description=f"SurplusFlow delivery booking via {provider_id}",
    )
    install_provider_payment(
        app,
        config,
        SQLiteInvoiceStore(data_dir / f"{provider_id}-invoices.sqlite3"),
        SQLiteProviderResponseStore(data_dir / f"{provider_id}-responses.sqlite3"),
        facilitator=facilitator,
        price_resolver=make_courier_price_resolver(provider_id=provider_id, simulate_failure=simulate_failure),
    )

    install_receipt_bridge(app, id_field="bookingId", persist_receipt=patch_booking_receipt)
