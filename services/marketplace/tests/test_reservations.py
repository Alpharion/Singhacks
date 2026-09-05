from __future__ import annotations


def test_get_reservation_not_found_returns_contract_error(client):
    response = client.get("/api/reservations/reservation_missing_001")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["retryable"] is False
    assert len(body["requestId"]) >= 8


def test_get_reservation_rejects_invalid_id_shape(client):
    response = client.get("/api/reservations/NOT-VALID-ID")
    assert response.status_code == 422
