from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

from surplusflow_provider_common.payments import encode_header

FAST_PROVIDER_ID = "courier_fast_001"
FAST_QUOTE_ID = "quote_fast_001"
FAST_PAY_TO = "rRideA1111111111111111111111111"
FAST_PRICE_DROPS = "12000000"
BUYER_ADDRESS = "rBuyerTest111111111111111111111"


def _future_iso(hours: int = 1) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return value.replace(":", "_").replace(".", "_")


def _build_intent(*, provider_id: str, quote_id: str, pay_to: str, amount: str, invoice_id: str, idempotency_key: str) -> dict:
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


def _payment_signature_header(*, pay_to: str, invoice_id: str, amount: str) -> str:
    return encode_header(
        {
            "network": "xrpl:1",
            "asset": "XRP",
            "payTo": pay_to,
            "amount": amount,
            "invoiceId": invoice_id,
            "payer": BUYER_ADDRESS,
        }
    )


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
    challenge = json.loads(base64.b64decode(response.headers["PAYMENT-REQUIRED"]))
    assert challenge["accepts"][0]["payTo"] == FAST_PAY_TO
    assert challenge["accepts"][0]["amount"] == FAST_PRICE_DROPS


def test_book_with_valid_payment_confirms_booking(client):
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
    signature = _payment_signature_header(pay_to=FAST_PAY_TO, invoice_id=invoice_id, amount=FAST_PRICE_DROPS)

    response = client.post(
        f"/api/delivery/{FAST_PROVIDER_ID}/book",
        json=intent,
        headers={"Idempotency-Key": idem_key, "PAYMENT-SIGNATURE": signature},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["providerId"] == FAST_PROVIDER_ID
    assert body["quoteId"] == FAST_QUOTE_ID
    assert body["status"] == "confirmed"
    assert body["paymentReceipt"]["invoiceId"] == invoice_id
    assert "PAYMENT-RESPONSE" in response.headers


def test_book_retry_with_same_idempotency_key_replays_response(client):
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
    signature = _payment_signature_header(pay_to=FAST_PAY_TO, invoice_id=invoice_id, amount=FAST_PRICE_DROPS)
    headers = {"Idempotency-Key": idem_key, "PAYMENT-SIGNATURE": signature}

    first = client.post(f"/api/delivery/{FAST_PROVIDER_ID}/book", json=intent, headers=headers)
    second = client.post(f"/api/delivery/{FAST_PROVIDER_ID}/book", json=intent, headers=headers)

    assert first.status_code == second.status_code == 201
    assert first.json()["bookingId"] == second.json()["bookingId"]


def test_book_rejects_amount_mismatch(client):
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


def test_book_rejects_wrong_provider_path(client):
    invoice_id = "inv:test:courierwrong:v1"
    idem_key = "idem:test:courierwrong:v1"
    intent = _build_intent(
        provider_id="courier_economy_001",
        quote_id="quote_economy_001",
        pay_to="rRideB1111111111111111111111111",
        amount="10000000",
        invoice_id=invoice_id,
        idempotency_key=idem_key,
    )

    response = client.post("/api/delivery/courier_economy_001/book", json=intent, headers={"Idempotency-Key": idem_key})

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_economy_van_simulated_failure_returns_503(failing_client):
    invoice_id = "inv:test:courierfail:v1"
    idem_key = "idem:test:courierfail:v1"
    intent = _build_intent(
        provider_id="courier_economy_001",
        quote_id="quote_economy_001",
        pay_to="rRideB1111111111111111111111111",
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
    assert body["details"]["providerId"] == "courier_economy_001"
