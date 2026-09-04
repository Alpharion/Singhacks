"""SurplusFlow seller reservation simulator (Person 3).

Represents a bakery, hotel kitchen, or grill depending on `SELLER_ID`. See
`app/config.py` and `README.md` for the three demo configurations.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from surplusflow_provider_common.db import get_session_factory, init_db
from surplusflow_provider_common.errors import register_error_handlers
from surplusflow_provider_common.seed_data import ensure_seed_data

from .config import load_settings
from .routers import health, reserve


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    session = get_session_factory()()
    try:
        ensure_seed_data(session)
    finally:
        session.close()
    yield


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title=f"SurplusFlow Seller ({settings.seller_id})", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(reserve.router)
    return app


app = create_app()
