"""HTTP surface: the two endpoints Person 2 owns on port 8001."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from buyer_agent import timeutil

from test_contracts import schema_validator


def request_text() -> str:
    """A demo request whose deadline is always a few hours away."""
    deadline = timeutil.plus(timeutil.now(), hours=6).astimezone(timeutil.local_zone())
    return (
        "Secure 100 vegetarian meals for our community kitchen, delivered to Queenstown "
        f"by {deadline:%H:%M}, for no more than 120 XRP including delivery."
    )


BODY = {
    "buyerId": "buyer_kitchen_001",
    "requestText": request_text(),
    "walletPolicyId": "policy_demo_001",
}
KEY = {"Idempotency-Key": "idem:test:run:v1"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BUYER_AGENT_SYNCHRONOUS_RUNS", "1")
    monkeypatch.setenv("BUYER_AGENT_DISCOVERY_MODE", "fixtures")
    monkeypatch.setenv("BUYER_AGENT_PAYMENT_MODE", "simulated")
    monkeypatch.setenv("SURPLUSFLOW_TIMEZONE", "Asia/Singapore")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from buyer_agent.main import app

    with TestClient(app) as test_client:
        yield test_client


def body_now() -> dict:
    return {**BODY, "requestText": request_text()}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_procure_accepts_the_demo_request(client):
    response = client.post("/api/procure", json=body_now(), headers=KEY)
    assert response.status_code == 202
    payload = response.json()
    assert response.headers["Location"] == f"/api/runs/{payload['runId']}"
    assert payload["goal"]["mealCount"] == 100
    assert payload["goal"]["maxTotalSpendDrops"] == "120000000"


def test_the_response_matches_the_frozen_run_schema(client):
    payload = client.post("/api/procure", json=body_now(), headers=KEY).json()
    assert list(schema_validator("agent-run.schema.json").iter_errors(payload)) == []


def test_a_synchronous_run_reaches_fulfilment(client):
    payload = client.post("/api/procure", json=body_now(), headers=KEY).json()
    assert payload["status"] == "fulfilled"
    assert payload["spend"]["totalDrops"] == "74000000"
    assert len(payload["reservations"]) == 2
    assert len(payload["deliveryBookings"]) == 1


def test_the_run_can_be_read_back(client):
    created = client.post("/api/procure", json=body_now(), headers=KEY).json()
    response = client.get(f"/api/runs/{created['runId']}")
    assert response.status_code == 200
    assert response.json()["runId"] == created["runId"]


def test_an_unknown_run_is_a_contract_shaped_404(client):
    response = client.get("/api/runs/run_does_not_exist")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
    assert response.json()["retryable"] is False


def test_replaying_the_same_key_returns_the_same_run(client):
    body = body_now()
    first = client.post("/api/procure", json=body, headers=KEY).json()
    second = client.post("/api/procure", json=body, headers=KEY).json()
    assert first["runId"] == second["runId"]


def test_reusing_a_key_for_a_different_body_conflicts(client):
    client.post("/api/procure", json=body_now(), headers=KEY)
    changed = {**body_now(), "buyerId": "buyer_other_001"}
    response = client.post("/api/procure", json=changed, headers=KEY)
    assert response.status_code == 409
    assert response.json()["error"] == "invalid_request"


def test_a_missing_idempotency_key_is_refused(client):
    response = client.post("/api/procure", json=body_now())
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_a_malformed_idempotency_key_is_refused(client):
    response = client.post(
        "/api/procure", json=body_now(), headers={"Idempotency-Key": "short"}
    )
    assert response.status_code == 422
    assert "Idempotency-Key" in response.json()["message"]


def test_an_unparseable_request_never_starts_a_run(client):
    body = {**body_now(), "requestText": "Please get us some food when you can."}
    response = client.post("/api/procure", json=body, headers=KEY)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_an_unknown_field_is_refused(client):
    body = {**body_now(), "surprise": True}
    response = client.post("/api/procure", json=body, headers=KEY)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_validation_errors_are_never_raw_fastapi(client):
    response = client.post("/api/procure", json={"buyerId": "x"}, headers=KEY)
    assert response.status_code == 422
    payload = response.json()
    assert set(payload) >= {"error", "message", "retryable", "requestId"}
    assert "detail" not in payload
