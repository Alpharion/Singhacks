from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session
from surplusflow_provider_common.db import get_session_factory

from .config import SellerSettings


def get_db() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_settings(request: Request) -> SellerSettings:
    return request.app.state.settings
