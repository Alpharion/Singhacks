from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

from surplusflow_provider_common.payments import encode_header

SELLER_ID = "seller_bakery_001"
OFFER_ID = "offer_bakery_001"
PAY_TO = "rFoodA1111111111111111111111111"
UNIT_PRICE_DROPS = 600_000
BUYER_ADDRESS = "rBuyerTest111111111111111111111"


def _future_iso(hours: int = 1) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return value.replace(":", "_").replace(".", "_")


def _build_intent(*, quantity: int, invoice_id: str, idempotency_key: str) -> dict:
    amount = str(quantity * UNIT_PRICE_DROPS)
    return {
        "intentId": f"intent_{_slug(invoice_id)}",
        "runId": "run_demo_001",
        "goalId": "goal_demo_001",
        "resourceType": "food_reservation",
        "providerId": SELLER_ID,
        "resourceId": OFFER_ID,
        "targetUrl": f"http://localhost:8011/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        "quantity": quantity,
        "amountDrops": amount,
        "payTo": PAY_TO,
        "network": "xrpl:1",
        "asset": "XRP",
        "invoiceId": invoice_id,
        "idempotencyKey": idempotency_key,
        "expiresAt": _future_iso(),
        "rationale": "Test reservation covering the vegetarian goal.",
        "policySnapshot": {
            "walletPolicyId": "policy_demo_001",
            "maxOrderSpendDrops": "120000000",
            "maxTransactionSpendDrops": "70000000",
            "allowedPayees": [PAY_TO],
        },
    }


def _payment_signature_header(*, invoice_id: str, amount: str) -> str:
    return encode_header(
        {
            "network": "xrpl:1",
            "asset": "XRP",
            "payTo": PAY_TO,
            "amount": amount,
            "invoiceId": invoice_id,
            "payer": BUYER_ADDRESS,
        }
    )


def test_reserve_without_payment_returns_402_challenge(client):
    invoice_id = "inv:test:402:v1"
    idem_key = "idem:test:402:v1"
    intent = _build_intent(quantity=5, invoice_id=invoice_id, idempotency_key=idem_key)

    response = client.post(
        f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={"Idempotency-Key": idem_key},
    )

    assert response.status_code == 402
    assert response.json()["error"] == "payment_required"
    challenge = json.loads(base64.b64decode(response.headers["PAYMENT-REQUIRED"]))
    accept = challenge["accepts"][0]
    assert accept["payTo"] == PAY_TO
    assert accept["amount"] == intent["amountDrops"]
    assert accept["extra"]["invoiceId"] == invoice_id


def test_reserve_with_valid_payment_confirms_reservation(client):
    invoice_id = "inv:test:success:v1"
    idem_key = "idem:test:success:v1"
    intent = _build_intent(quantity=5, invoice_id=invoice_id, idempotency_key=idem_key)
    signature = _payment_signature_header(invoice_id=invoice_id, amount=intent["amountDrops"])

    response = client.post(
        f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={"Idempotency-Key": idem_key, "PAYMENT-SIGNATURE": signature},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sellerId"] == SELLER_ID
    assert body["offerId"] == OFFER_ID
    assert body["quantity"] == 5
    assert body["status"] == "confirmed"
    assert body["paymentReceipt"]["invoiceId"] == invoice_id
    assert "PAYMENT-RESPONSE" in response.headers


def test_reserve_retry_with_same_idempotency_key_replays_response(client):
    invoice_id = "inv:test:replay:v1"
    idem_key = "idem:test:replay:v1"
    intent = _build_intent(quantity=3, invoice_id=invoice_id, idempotency_key=idem_key)
    signature = _payment_signature_header(invoice_id=invoice_id, amount=intent["amountDrops"])
    headers = {"Idempotency-Key": idem_key, "PAYMENT-SIGNATURE": signature}

    first = client.post(f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve", json=intent, headers=headers)
    second = client.post(f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve", json=intent, headers=headers)

    assert first.status_code == second.status_code == 201
    assert first.json()["reservationId"] == second.json()["reservationId"]


def test_reserve_rejects_quantity_above_availability(client):
    invoice_id = "inv:test:oversell:v1"
    idem_key = "idem:test:oversell:v1"
    intent = _build_intent(quantity=10_000, invoice_id=invoice_id, idempotency_key=idem_key)

    response = client.post(
        f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={"Idempotency-Key": idem_key},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "offer_sold_out"


def test_reserve_rejects_wrong_seller_path(client):
    invoice_id = "inv:test:wrongseller:v1"
    idem_key = "idem:test:wrongseller:v1"
    intent = _build_intent(quantity=1, invoice_id=invoice_id, idempotency_key=idem_key)
    intent["providerId"] = "seller_hotel_001"

    response = client.post(
        f"/api/sellers/seller_hotel_001/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={"Idempotency-Key": idem_key},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_reserve_rejects_mismatched_idempotency_header(client):
    invoice_id = "inv:test:badheader:v1"
    idem_key = "idem:test:badheader:v1"
    intent = _build_intent(quantity=1, invoice_id=invoice_id, idempotency_key=idem_key)

    response = client.post(
        f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={"Idempotency-Key": "idem:different:key:v1"},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_reserve_rejects_invalid_payment_signature(client):
    invoice_id = "inv:test:badsig:v1"
    idem_key = "idem:test:badsig:v1"
    intent = _build_intent(quantity=2, invoice_id=invoice_id, idempotency_key=idem_key)
    bad_signature = _payment_signature_header(invoice_id=invoice_id, amount="999999999")

    response = client.post(
        f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={"Idempotency-Key": idem_key, "PAYMENT-SIGNATURE": bad_signature},
    )

    assert response.status_code == 402
    assert response.json()["error"] == "payment_failed"
