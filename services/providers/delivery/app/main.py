"""SurplusFlow courier booking simulator (Person 3).

Represents FastRoute Courier or Economy Van depending on `PROVIDER_ID`.
See `app/config.py` and `README.md` for the two demo configurations.

Seeding and payment-middleware registration happen synchronously here
(not in an async lifespan handler): FastAPI/Starlette freezes the
middleware stack the first time the app is dispatched at all -- including
the ASGI `lifespan` scope -- so `install_provider_payment` must already
know this courier's data before that first dispatch.
"""

from __future__ import annotations

from fastapi import FastAPI
from surplusflow_provider_common.db import get_session_factory, init_db, startup_lock
from surplusflow_provider_common.errors import register_error_handlers
from surplusflow_provider_common.models import CourierProviderRow
from surplusflow_provider_common.seed_data import ensure_seed_data

from .config import load_settings
from .payment_wiring import install_courier_payments
from .routers import book, health


def create_app(*, facilitator: object | None = None) -> FastAPI:
    """`facilitator` is a test-only seam -- see `payment_wiring.install_courier_payments`."""

    settings = load_settings()

    with startup_lock():
        init_db()
        session = get_session_factory()()
        try:
            ensure_seed_data(session)
            provider = session.get(CourierProviderRow, settings.provider_id)
        finally:
            session.close()

    if provider is None:
        raise RuntimeError(f"Courier {settings.provider_id!r} is not present in seed data.")

    app = FastAPI(title=f"SurplusFlow Courier ({settings.provider_id})", version="1.0.0")
    app.state.settings = settings
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(book.router)

    install_courier_payments(
        app,
        provider_id=settings.provider_id,
        pay_to=provider.pay_to,
        simulate_failure=settings.simulate_failure,
        facilitator=facilitator,
    )

    return app


app = create_app()
