from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "marketplace-test.db"
    monkeypatch.setenv("SURPLUSFLOW_DB_PATH", str(db_path))

    import surplusflow_provider_common.db as db_module

    db_module._engine = None
    db_module._SessionLocal = None

    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
