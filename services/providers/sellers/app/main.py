"""SurplusFlow seller reservation simulator (Person 3).

Represents a bakery, hotel kitchen, or grill depending on `SELLER_ID`. See
`app/config.py` and `README.md` for the three demo configurations.

Seeding and payment-middleware registration happen synchronously here
(not in an async lifespan handler): FastAPI/Starlette freezes the
middleware stack the first time the app is dispatched at all -- including
the ASGI `lifespan` scope -- so `install_provider_payment` must already
know this seller's offers before that first dispatch.
"""

from __future__ import annotations

from fastapi import FastAPI
from surplusflow_provider_common.db import get_session_factory, init_db, startup_lock
from surplusflow_provider_common.errors import register_error_handlers
from surplusflow_provider_common.models import FoodOfferRow, SellerRow
from surplusflow_provider_common.seed_data import ensure_seed_data

from .config import load_settings
from .payment_wiring import install_seller_payments
from .routers import health, reserve


def create_app(*, facilitator: object | None = None) -> FastAPI:
    """`facilitator` is a test-only seam -- see `payment_wiring.install_seller_payments`."""

    settings = load_settings()

    with startup_lock():
        init_db()
        session = get_session_factory()()
        try:
            ensure_seed_data(session)
            seller = session.get(SellerRow, settings.seller_id)
            offers = (
                session.query(FoodOfferRow)
                .filter(FoodOfferRow.seller_id == settings.seller_id)
                .all()
            )
        finally:
            session.close()

    if seller is None:
        raise RuntimeError(f"Seller {settings.seller_id!r} is not present in seed data.")

    app = FastAPI(title=f"SurplusFlow Seller ({settings.seller_id})", version="1.0.0")
    app.state.settings = settings
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(reserve.router)

    install_seller_payments(
        app, seller_id=settings.seller_id, offers=offers, pay_to=seller.pay_to, facilitator=facilitator
    )

    return app


app = create_app()
