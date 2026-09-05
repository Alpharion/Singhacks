from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import BUYER_ADDRESS, build_payment_signature

FAST_PROVIDER_ID = "courier_fast_001"
FAST_QUOTE_ID = "quote_fast_001"
FAST_PAY_TO = "rh9mJwT6fVV3bwt1APGfXoAa94vb6YBuMQ"
FAST_PRICE_DROPS = "12000000"


def _future_iso(hours: int = 1) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return value.replace(":", "_").replace(".", "_")


def _build_intent(
    *, provider_id: str, quote_id: str, pay_to: str, amount: str, invoice_id: str, idempotency_key: str
) -> dict:
    return {
        "intentId": f"intent_{_slug(invoice_id)}",
        "runId": "run_demo_001",
        "goalId": "goal_demo_001",
        "resourceType": "delivery_booking",
        "providerId": provider_id,
        "resourceId": quote_id,
        "targetUrl": f"http://localhost:8021/api/delivery/{provider_id}/book",
        "amountDrops": amount,
        "payTo": pay_to,
        "network": "xrpl:1",
        "asset": "XRP",
        "invoiceId": invoice_id,
        "idempotencyKey": idempotency_key,
        "expiresAt": _future_iso(),
        "rationale": "Test booking covering the delivery leg.",
        "policySnapshot": {
            "walletPolicyId": "policy_demo_001",
            "maxOrderSpendDrops": "120000000",
            "maxTransactionSpendDrops": "70000000",
            "allowedPayees": [pay_to],
        },
    }


def test_book_without_payment_returns_402_challenge(client):
    invoice_id = "inv:test:courier402:v1"
    idem_key = "idem:test:courier402:v1"
    intent = _build_intent(
        provider_id=FAST_PROVIDER_ID,
        quote_id=FAST_QUOTE_ID,
        pay_to=FAST_PAY_TO,
        amount=FAST_PRICE_DROPS,
        invoice_id=invoice_id,
        idempotency_key=idem_key,
    )

    response = client.post(f"/api/delivery/{FAST_PROVIDER_ID}/book", json=intent, headers={"Idempotency-Key": idem_key})

    assert response.status_code == 402
    assert "PAYMENT-REQUIRED" in response.headers


def test_book_with_valid_payment_confirms_booking(client, facilitator):
    invoice_id = "inv:test:couriersuccess:v1"
    idem_key = "idem:test:couriersuccess:v1"
    intent = _build_intent(
        provider_id=FAST_PROVIDER_ID,
        quote_id=FAST_QUOTE_ID,
        pay_to=FAST_PAY_TO,
        amount=FAST_PRICE_DROPS,
        invoice_id=invoice_id,
        idempotency_key=idem_key,
    )
    headers = {"Idempotency-Key": idem_key}

    challenge = client.post(f"/api/delivery/{FAST_PROVIDER_ID}/book", json=intent, headers=headers)
    assert challenge.status_code == 402
    signature = build_payment_signature(challenge.headers["PAYMENT-REQUIRED"])

    response = client.post(
        f"/api/delivery/{FAST_PROVIDER_ID}/book",
        json=intent,
        headers={**headers, "PAYMENT-SIGNATURE": signature},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["providerId"] == FAST_PROVIDER_ID
    assert body["quoteId"] == FAST_QUOTE_ID
    assert body["status"] == "confirmed"
    receipt = body["paymentReceipt"]
    assert receipt["transaction"] == facilitator.transaction
    assert receipt["payer"] == BUYER_ADDRESS
    assert receipt["payee"] == FAST_PAY_TO
    assert receipt["amountDrops"] == FAST_PRICE_DROPS
    assert receipt["invoiceId"] == invoice_id
    assert facilitator.calls == ["/verify", "/settle"]


def test_book_retry_with_same_idempotency_key_replays_response(client, facilitator):
    invoice_id = "inv:test:courierreplay:v1"
    idem_key = "idem:test:courierreplay:v1"
    intent = _build_intent(
        provider_id=FAST_PROVIDER_ID,
        quote_id=FAST_QUOTE_ID,
        pay_to=FAST_PAY_TO,
        amount=FAST_PRICE_DROPS,
        invoice_id=invoice_id,
        idempotency_key=idem_key,
    )
    headers = {"Idempotency-Key": idem_key}
    challenge = client.post(f"/api/delivery/{FAST_PROVIDER_ID}/book", json=intent, headers=headers)
    signature = build_payment_signature(challenge.headers["PAYMENT-REQUIRED"])
    paid_headers = {**headers, "PAYMENT-SIGNATURE": signature}

    first = client.post(f"/api/delivery/{FAST_PROVIDER_ID}/book", json=intent, headers=paid_headers)
    second = client.post(f"/api/delivery/{FAST_PROVIDER_ID}/book", json=intent, headers=paid_headers)

    assert first.status_code == second.status_code == 201
    assert first.json()["bookingId"] == second.json()["bookingId"]
    assert facilitator.calls == ["/verify", "/settle"]


def test_book_rejects_amount_mismatch_before_challenge(client):
    invoice_id = "inv:test:courieramount:v1"
    idem_key = "idem:test:courieramount:v1"
    intent = _build_intent(
        provider_id=FAST_PROVIDER_ID,
        quote_id=FAST_QUOTE_ID,
        pay_to=FAST_PAY_TO,
        amount="1",
        invoice_id=invoice_id,
        idempotency_key=idem_key,
    )

    response = client.post(f"/api/delivery/{FAST_PROVIDER_ID}/book", json=intent, headers={"Idempotency-Key": idem_key})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert "PAYMENT-REQUIRED" not in response.headers


def test_book_rejects_wrong_provider_path(client):
    invoice_id = "inv:test:courierwrong:v1"
    idem_key = "idem:test:courierwrong:v1"
    intent = _build_intent(
        provider_id="courier_economy_001",
        quote_id="quote_economy_001",
        pay_to="rh1p5es2WiK6Ane1x9QGpCF4QsMX2ESZjg",
        amount="10000000",
        invoice_id=invoice_id,
        idempotency_key=idem_key,
    )

    response = client.post("/api/delivery/courier_economy_001/book", json=intent, headers={"Idempotency-Key": idem_key})

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_economy_van_simulated_failure_returns_503(failing_client, failing_facilitator):
    invoice_id = "inv:test:courierfail:v1"
    idem_key = "idem:test:courierfail:v1"
    intent = _build_intent(
        provider_id="courier_economy_001",
        quote_id="quote_economy_001",
        pay_to="rh1p5es2WiK6Ane1x9QGpCF4QsMX2ESZjg",
        amount="10000000",
        invoice_id=invoice_id,
        idempotency_key=idem_key,
    )

    response = failing_client.post(
        "/api/delivery/courier_economy_001/book", json=intent, headers={"Idempotency-Key": idem_key}
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "provider_unavailable"
    assert body["retryable"] is True
    # The resolver rejects before ever contacting the facilitator.
    assert failing_facilitator.calls == []
