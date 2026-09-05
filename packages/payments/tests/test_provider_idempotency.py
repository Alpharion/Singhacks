from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from surplusflow_payments.provider_idempotency import (
    ClaimStatus,
    ProviderIdempotencyMiddleware,
    SQLiteProviderResponseStore,
    request_fingerprint,
)


def test_store_claim_complete_and_replay(tmp_path) -> None:
    store = SQLiteProviderResponseStore(tmp_path / "responses.sqlite3")
    key = "idem:store_001"
    fingerprint = "A" * 64

    assert store.claim(key, fingerprint).status is ClaimStatus.NEW
    assert store.claim(key, fingerprint).status is ClaimStatus.IN_PROGRESS
    assert store.claim(key, "B" * 64).status is ClaimStatus.CONFLICT

    store.complete(
        key,
        fingerprint,
        status_code=201,
        headers=[
            (b"content-type", b"application/json"),
            (b"payment-response", b"receipt"),
        ],
        body=b'{"reservationId":"reservation_001"}',
    )

    completed = store.claim(key, fingerprint)
    assert completed.status is ClaimStatus.COMPLETED
    assert completed.response is not None
    assert completed.response.status_code == 201
    assert completed.response.body == b'{"reservationId":"reservation_001"}'
    assert (b"payment-response", b"receipt") in completed.response.headers


def test_fingerprint_canonicalizes_json_key_order() -> None:
    scope = {
        "method": "POST",
        "path": "/paid",
        "query_string": b"",
    }

    first = request_fingerprint(scope, b'{"a":1,"b":2}')
    reordered = request_fingerprint(scope, b'{ "b": 2, "a": 1 }')

    assert first == reordered


def test_store_release_allows_safe_retry(tmp_path) -> None:
    store = SQLiteProviderResponseStore(tmp_path / "responses.sqlite3")
    key = "idem:release_001"
    fingerprint = "A" * 64
    assert store.claim(key, fingerprint).status is ClaimStatus.NEW

    store.release(key, fingerprint)

    assert store.claim(key, fingerprint).status is ClaimStatus.NEW


def test_stale_pending_claim_can_be_recovered(tmp_path) -> None:
    store = SQLiteProviderResponseStore(
        tmp_path / "responses.sqlite3",
        pending_ttl_seconds=-1,
    )
    key = "idem:stale_001"
    fingerprint = "A" * 64
    assert store.claim(key, fingerprint).status is ClaimStatus.NEW

    assert store.claim(key, fingerprint).status is ClaimStatus.NEW


def test_complete_requires_matching_pending_claim(tmp_path) -> None:
    store = SQLiteProviderResponseStore(tmp_path / "responses.sqlite3")

    try:
        store.complete(
            "idem:missing_001",
            "A" * 64,
            status_code=201,
            headers=[],
            body=b"",
        )
    except KeyError as error:
        assert "not pending" in str(error)
    else:
        raise AssertionError("missing claim must not be completed")


def build_idempotent_app(tmp_path) -> tuple[TestClient, list[dict[str, str]]]:
    app = FastAPI()
    calls: list[dict[str, str]] = []

    @app.post("/paid", status_code=201)
    async def paid(payload: dict[str, str], response: Response):
        calls.append(payload)
        response.headers["PAYMENT-RESPONSE"] = "settled-receipt"
        return {"reservationId": "reservation_001", "payload": payload}

    app.add_middleware(
        ProviderIdempotencyMiddleware,
        store=SQLiteProviderResponseStore(tmp_path / "responses.sqlite3"),
        protected_paths="/paid",
    )
    return TestClient(app), calls


def test_middleware_replays_completed_paid_response(tmp_path) -> None:
    client, calls = build_idempotent_app(tmp_path)
    headers = {"Idempotency-Key": "idem:middleware_001"}
    payload = {
        "offer": "offer_001",
        "invoiceId": "inv:middleware_001",
        "idempotencyKey": "idem:middleware_001",
    }

    first = client.post("/paid", json=payload, headers=headers)
    replay = client.post("/paid", json=payload, headers=headers)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert replay.headers["PAYMENT-RESPONSE"] == "settled-receipt"
    assert calls == [payload]


def test_middleware_rejects_same_key_for_different_request(tmp_path) -> None:
    client, calls = build_idempotent_app(tmp_path)
    headers = {"Idempotency-Key": "idem:middleware_001"}
    first_payload = {
        "offer": "offer_001",
        "invoiceId": "inv:middleware_001",
        "idempotencyKey": "idem:middleware_001",
    }
    first = client.post("/paid", json=first_payload, headers=headers)

    conflict = client.post(
        "/paid",
        json={**first_payload, "offer": "offer_002"},
        headers=headers,
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "payment_replayed"
    assert conflict.json()["retryable"] is False
    assert len(calls) == 1


def test_middleware_rejects_missing_or_malformed_key(tmp_path) -> None:
    client, calls = build_idempotent_app(tmp_path)

    missing = client.post("/paid", json={"offer": "offer_001"})
    malformed = client.post(
        "/paid",
        json={"offer": "offer_001"},
        headers={"Idempotency-Key": "short"},
    )

    assert missing.status_code == 422
    assert malformed.status_code == 422
    assert missing.json()["error"] == "invalid_request"
    assert calls == []


def test_middleware_releases_unsigned_or_failed_response(tmp_path) -> None:
    app = FastAPI()
    calls = 0

    @app.post("/paid")
    async def unpaid():
        nonlocal calls
        calls += 1
        return Response(status_code=402)

    app.add_middleware(
        ProviderIdempotencyMiddleware,
        store=SQLiteProviderResponseStore(tmp_path / "responses.sqlite3"),
        protected_paths="/paid",
    )
    client = TestClient(app)
    headers = {"Idempotency-Key": "idem:unpaid_001"}
    payload = {
        "invoiceId": "inv:unpaid_001",
        "idempotencyKey": "idem:unpaid_001",
    }

    assert client.post("/paid", headers=headers, json=payload).status_code == 402
    assert client.post("/paid", headers=headers, json=payload).status_code == 402
    assert calls == 2


def test_middleware_requires_invoice_and_matching_body_key(tmp_path) -> None:
    client, calls = build_idempotent_app(tmp_path)
    headers = {"Idempotency-Key": "idem:middleware_001"}

    missing_invoice = client.post(
        "/paid",
        json={"idempotencyKey": "idem:middleware_001"},
        headers=headers,
    )
    mismatched_key = client.post(
        "/paid",
        json={
            "invoiceId": "inv:middleware_001",
            "idempotencyKey": "idem:different_001",
        },
        headers=headers,
    )

    assert missing_invoice.status_code == 422
    assert mismatched_key.status_code == 422
    assert "must equal" in mismatched_key.json()["message"]
    assert calls == []


def test_middleware_passes_through_public_path(tmp_path) -> None:
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.add_middleware(
        ProviderIdempotencyMiddleware,
        store=SQLiteProviderResponseStore(tmp_path / "responses.sqlite3"),
        protected_paths="/paid",
    )

    assert TestClient(app).get("/health").json() == {"status": "ok"}
