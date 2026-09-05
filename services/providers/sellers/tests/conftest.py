from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _make_client(tmp_path, monkeypatch, *, seller_id: str, port: str):
    db_path = tmp_path / f"{seller_id}-test.db"
    monkeypatch.setenv("SURPLUSFLOW_DB_PATH", str(db_path))
    monkeypatch.setenv("SELLER_ID", seller_id)
    monkeypatch.setenv("PORT", port)

    import surplusflow_provider_common.db as db_module

    db_module._engine = None
    db_module._SessionLocal = None

    from app.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    with _make_client(tmp_path, monkeypatch, seller_id="seller_bakery_001", port="8011") as c:
        yield c


@pytest.fixture()
def hotel_client(tmp_path, monkeypatch):
    """Harbour Hotel Kitchen: offer_hotel_001 has quantityAvailable=60, used to
    cover the frozen fixture's partial-quantity scenario (40 of 60 meals)."""

    with _make_client(tmp_path, monkeypatch, seller_id="seller_hotel_001", port="8012") as c:
        yield c
