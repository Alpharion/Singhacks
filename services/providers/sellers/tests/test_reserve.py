from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import BUYER_ADDRESS, build_payment_signature

SELLER_ID = "seller_bakery_001"
OFFER_ID = "offer_bakery_001"
PAY_TO = "rsqFz7Ctvh2yKGAJ171o5sWwifMRnLLmZa"
UNIT_PRICE_DROPS = 600_000


def _future_iso(hours: int = 1) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return value.replace(":", "_").replace(".", "_")


def _build_intent(
    *,
    quantity: int | None,
    invoice_id: str,
    idempotency_key: str,
    seller_id: str = SELLER_ID,
    offer_id: str = OFFER_ID,
    pay_to: str = PAY_TO,
    unit_price_drops: int = UNIT_PRICE_DROPS,
) -> dict:
    amount = str((quantity or 0) * unit_price_drops)
    return {
        "intentId": f"intent_{_slug(invoice_id)}",
        "runId": "run_demo_001",
        "goalId": "goal_demo_001",
        "resourceType": "food_reservation",
        "providerId": seller_id,
        "resourceId": offer_id,
        "targetUrl": f"http://localhost:8011/api/sellers/{seller_id}/offers/{offer_id}/reserve",
        "quantity": quantity,
        "amountDrops": amount,
        "payTo": pay_to,
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
            "allowedPayees": [pay_to],
        },
    }


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
    assert "PAYMENT-REQUIRED" in response.headers


def test_reserve_with_valid_payment_confirms_reservation(client, facilitator):
    invoice_id = "inv:test:success:v1"
    idem_key = "idem:test:success:v1"
    intent = _build_intent(quantity=5, invoice_id=invoice_id, idempotency_key=idem_key)
    headers = {"Idempotency-Key": idem_key}

    challenge = client.post(f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve", json=intent, headers=headers)
    signature = build_payment_signature(challenge.headers["PAYMENT-REQUIRED"])

    response = client.post(
        f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={**headers, "PAYMENT-SIGNATURE": signature},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sellerId"] == SELLER_ID
    assert body["offerId"] == OFFER_ID
    assert body["quantity"] == 5
    assert body["status"] == "confirmed"
    receipt = body["paymentReceipt"]
    assert receipt["transaction"] == facilitator.transaction
    assert receipt["payer"] == BUYER_ADDRESS
    assert receipt["payee"] == PAY_TO
    assert receipt["amountDrops"] == str(5 * UNIT_PRICE_DROPS)
    assert receipt["invoiceId"] == invoice_id
    assert facilitator.calls == ["/verify", "/settle"]


def test_reserve_retry_with_same_idempotency_key_replays_response(client, facilitator):
    invoice_id = "inv:test:replay:v1"
    idem_key = "idem:test:replay:v1"
    intent = _build_intent(quantity=3, invoice_id=invoice_id, idempotency_key=idem_key)
    headers = {"Idempotency-Key": idem_key}

    challenge = client.post(f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve", json=intent, headers=headers)
    signature = build_payment_signature(challenge.headers["PAYMENT-REQUIRED"])
    paid_headers = {**headers, "PAYMENT-SIGNATURE": signature}

    first = client.post(f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve", json=intent, headers=paid_headers)
    second = client.post(f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve", json=intent, headers=paid_headers)

    assert first.status_code == second.status_code == 201
    assert first.json()["reservationId"] == second.json()["reservationId"]
    assert first.json() == second.json()
    # Only one settlement despite two paid requests reaching the provider.
    assert facilitator.calls == ["/verify", "/settle"]


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
    assert "PAYMENT-REQUIRED" not in response.headers


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


def test_reserve_rejects_tampered_signed_amount(client, facilitator):
    invoice_id = "inv:test:badsig:v1"
    idem_key = "idem:test:badsig:v1"
    intent = _build_intent(quantity=2, invoice_id=invoice_id, idempotency_key=idem_key)
    headers = {"Idempotency-Key": idem_key}

    challenge = client.post(f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve", json=intent, headers=headers)
    tampered_signature = build_payment_signature(challenge.headers["PAYMENT-REQUIRED"], accepted_amount="1")

    response = client.post(
        f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={**headers, "PAYMENT-SIGNATURE": tampered_signature},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "invoice_mismatch"
    # Terms are checked before the facilitator is ever contacted.
    assert facilitator.calls == []


def test_reserve_rejects_intent_describing_a_different_offer(client):
    invoice_id = "inv:test:mismatch:v1"
    idem_key = "idem:test:mismatch:v1"
    intent = _build_intent(quantity=1, invoice_id=invoice_id, idempotency_key=idem_key)
    intent["resourceId"] = "offer_hotel_001"

    response = client.post(
        f"/api/sellers/{SELLER_ID}/offers/{OFFER_ID}/reserve",
        json=intent,
        headers={"Idempotency-Key": idem_key},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert "PAYMENT-REQUIRED" not in response.headers


def test_reserve_accepts_partial_quantity_below_availability(hotel_client, hotel_facilitator):
    """Regression guard for the frozen fixture's partial-purchase scenario:
    packages/contracts/fixtures/delivery-quote-request.json reserves 40 of
    offer_hotel_001's 60 available meals. This must keep working -- do not
    collapse reservations into a whole-lot-only model to fit a payment
    adapter that cannot yet price a partial quantity per request."""

    hotel_seller_id = "seller_hotel_001"
    hotel_offer_id = "offer_hotel_001"
    hotel_pay_to = "rBNu67NF8xwMTnyeT5uWFAKsnkF4pc28AA"
    hotel_unit_price = 650_000
    invoice_id = "inv:test:partial:v1"
    idem_key = "idem:test:partial:v1"
    intent = _build_intent(
        quantity=40,
        invoice_id=invoice_id,
        idempotency_key=idem_key,
        seller_id=hotel_seller_id,
        offer_id=hotel_offer_id,
        pay_to=hotel_pay_to,
        unit_price_drops=hotel_unit_price,
    )
    headers = {"Idempotency-Key": idem_key}

    challenge = hotel_client.post(
        f"/api/sellers/{hotel_seller_id}/offers/{hotel_offer_id}/reserve", json=intent, headers=headers
    )
    assert challenge.status_code == 402
    signature = build_payment_signature(challenge.headers["PAYMENT-REQUIRED"])

    response = hotel_client.post(
        f"/api/sellers/{hotel_seller_id}/offers/{hotel_offer_id}/reserve",
        json=intent,
        headers={**headers, "PAYMENT-SIGNATURE": signature},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 40
    assert body["status"] == "confirmed"
    assert body["paymentReceipt"]["amountDrops"] == str(40 * hotel_unit_price)

    # 20 of 60 remain: a request for 25 must be rejected as sold out...
    over_intent = _build_intent(
        quantity=25,
        invoice_id="inv:test:partial:remaining-check:v1",
        idempotency_key="idem:test:partial:remaining-check:v1",
        seller_id=hotel_seller_id,
        offer_id=hotel_offer_id,
        pay_to=hotel_pay_to,
        unit_price_drops=hotel_unit_price,
    )
    over_response = hotel_client.post(
        f"/api/sellers/{hotel_seller_id}/offers/{hotel_offer_id}/reserve",
        json=over_intent,
        headers={"Idempotency-Key": over_intent["idempotencyKey"]},
    )
    assert over_response.status_code == 409
    assert over_response.json()["error"] == "offer_sold_out"

    # ...while the remaining 20 are still purchasable.
    remaining_intent = _build_intent(
        quantity=20,
        invoice_id="inv:test:partial:remaining-buy:v1",
        idempotency_key="idem:test:partial:remaining-buy:v1",
        seller_id=hotel_seller_id,
        offer_id=hotel_offer_id,
        pay_to=hotel_pay_to,
        unit_price_drops=hotel_unit_price,
    )
    remaining_response = hotel_client.post(
        f"/api/sellers/{hotel_seller_id}/offers/{hotel_offer_id}/reserve",
        json=remaining_intent,
        headers={"Idempotency-Key": remaining_intent["idempotencyKey"]},
    )
    assert remaining_response.status_code == 402
