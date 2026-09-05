"""SurplusFlow marketplace service (port 8002, Person 3).

Aggregates free offer and courier-quote discovery and exposes reservation
status. It never chooses purchases and never holds the buyer's wallet
credentials (PROJECT_CONTEXT.md section 5, "Platform service").
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from surplusflow_provider_common.db import get_session_factory, init_db, startup_lock
from surplusflow_provider_common.errors import register_error_handlers
from surplusflow_provider_common.seed_data import ensure_seed_data

from .routers import delivery, health, offers, reservations


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    with startup_lock():
        init_db()
        session = get_session_factory()()
        try:
            ensure_seed_data(session)
        finally:
            session.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="SurplusFlow Marketplace", version="1.0.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(offers.router)
    app.include_router(delivery.router)
    app.include_router(reservations.router)
    return app


app = create_app()
