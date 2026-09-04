from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _make_client(tmp_path, monkeypatch, *, provider_id: str, port: str, simulate_failure: bool | None = None):
    db_path = tmp_path / f"{provider_id}-test.db"
    monkeypatch.setenv("SURPLUSFLOW_DB_PATH", str(db_path))
    monkeypatch.setenv("PROVIDER_ID", provider_id)
    monkeypatch.setenv("PORT", port)
    if simulate_failure is None:
        monkeypatch.delenv("COURIER_SIMULATE_FAILURE", raising=False)
    else:
        monkeypatch.setenv("COURIER_SIMULATE_FAILURE", "true" if simulate_failure else "false")

    import surplusflow_provider_common.db as db_module

    db_module._engine = None
    db_module._SessionLocal = None

    from app.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """FastRoute Courier: reliable, no simulated failure."""

    with _make_client(tmp_path, monkeypatch, provider_id="courier_fast_001", port="8021", simulate_failure=False) as c:
        yield c


@pytest.fixture()
def failing_client(tmp_path, monkeypatch):
    """Economy Van with the demo failure explicitly enabled."""

    with _make_client(
        tmp_path, monkeypatch, provider_id="courier_economy_001", port="8022", simulate_failure=True
    ) as c:
        yield c
