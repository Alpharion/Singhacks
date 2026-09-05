from __future__ import annotations

import base64
import json

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from surplusflow_payments.headers import decode_payment_required
from surplusflow_payments.invoice_store import SQLiteInvoiceStore
from surplusflow_payments.provider import (
    ProviderPaymentConfig,
    ProviderPricingError,
    create_standalone_provider_app,
    install_provider_payment,
)
from surplusflow_payments.provider_idempotency import (
    ProviderRequestContext,
    SQLiteProviderResponseStore,
)

from conftest import PAYEE, SOURCE_TAG


def build_client(tmp_path) -> TestClient:
    config = ProviderPaymentConfig(
        protected_paths="/paid/demo",
        price_drops="5000",
        pay_to_address=PAYEE,
        facilitator_url="https://facilitator.example",
    )
    app = create_standalone_provider_app(
        config,
        SQLiteInvoiceStore(tmp_path / "invoices.sqlite3"),
        facilitator=object(),
    )
    return TestClient(app)


class FakeFacilitatorResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.status_code = 200
        self._body = body
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, object]:
        return self._body


class RecordingFacilitator:
    def __init__(self) -> None:
        self._client = self
        self.calls: list[str] = []

    async def post(
        self,
        path: str,
        *,
        json: dict[str, object],
    ) -> FakeFacilitatorResponse:
        self.calls.append(path)
        if path == "/verify":
            return FakeFacilitatorResponse({"isValid": True})
        assert path == "/settle"
        return FakeFacilitatorResponse(
            {
                "success": True,
                "transaction": "A" * 64,
                "network": "xrpl:1",
                "payer": "rBuyer1111111111111111111111111",
            }
        )


def dynamic_payload(
    *,
    quantity: int,
    invoice_id: str,
    idempotency_key: str,
    amount_drops: str | None = None,
) -> dict[str, object]:
    return {
        "resourceId": "offer_demo_001",
        "quantity": quantity,
        "amountDrops": amount_drops or str(quantity * 600_000),
        "payTo": PAYEE,
        "network": "xrpl:1",
        "asset": "XRP",
        "invoiceId": invoice_id,
        "idempotencyKey": idempotency_key,
    }


def payment_signature(
    payment_required_header: str,
    *,
    accepted_amount: str | None = None,
) -> str:
    challenge = json.loads(base64.b64decode(payment_required_header))
    accepted = challenge["accepts"][0]
    if accepted_amount is not None:
        accepted["amount"] = accepted_amount
    payload = {
        "x402Version": 2,
        "accepted": accepted,
        "payload": {
            "invoiceId": accepted["extra"]["invoiceId"],
            "signedTxBlob": "DEADBEEF",
        },
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


def build_dynamic_client(
    tmp_path,
    *,
    facilitator: object | None = None,
) -> tuple[TestClient, list[ProviderRequestContext], list[dict[str, object]]]:
    app = FastAPI()
    pricing_calls: list[ProviderRequestContext] = []
    route_calls: list[dict[str, object]] = []

    def resolve_price(context: ProviderRequestContext) -> int:
        pricing_calls.append(context)
        if context.payload.get("resourceId") != "offer_demo_001":
            raise ProviderPricingError(
                "Offer does not exist",
                error="not_found",
                status_code=404,
            )
        quantity = context.payload.get("quantity")
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise ProviderPricingError("Quantity must be an integer")
        if quantity > 60:
            raise ProviderPricingError(
                "Only 60 meals remain",
                error="offer_sold_out",
                status_code=409,
            )
        return quantity * 600_000

    @app.post("/paid/dynamic", status_code=201)
    async def reserve(payload: dict[str, object], response: Response):
        route_calls.append(payload)
        response.headers["X-Reservation-ID"] = "reservation_dynamic_001"
        return {
            "reservationId": "reservation_dynamic_001",
            "quantity": payload["quantity"],
        }

    install_provider_payment(
        app,
        ProviderPaymentConfig(
            protected_paths="/paid/dynamic",
            pay_to_address=PAYEE,
            facilitator_url="https://facilitator.example",
        ),
        SQLiteInvoiceStore(tmp_path / "dynamic-invoices.sqlite3"),
        SQLiteProviderResponseStore(tmp_path / "dynamic-responses.sqlite3"),
        facilitator=facilitator or object(),
        price_resolver=resolve_price,
    )
    return TestClient(app), pricing_calls, route_calls


def test_health_is_public(tmp_path) -> None:
    response = build_client(tmp_path).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_paid_resource_issues_bound_x402_challenge(tmp_path) -> None:
    invoice_id = "inv:provider_demo_001"
    response = build_client(tmp_path).post(
        "/paid/demo",
        headers={"Idempotency-Key": "idem:provider_demo_001"},
        json={
            "invoiceId": invoice_id,
            "idempotencyKey": "idem:provider_demo_001",
        },
    )

    assert response.status_code == 402
    challenge = decode_payment_required(response.headers["PAYMENT-REQUIRED"])
    option = challenge.accepts[0]
    assert challenge.x402_version == 2
    assert option.network == "xrpl:1"
    assert option.asset == "XRP"
    assert option.pay_to == PAYEE
    assert option.amount == "5000"
    assert option.extra.source_tag == SOURCE_TAG
    assert option.extra.invoice_id == invoice_id


def test_dynamic_price_uses_trusted_quantity_and_unit_price(tmp_path) -> None:
    client, pricing_calls, _route_calls = build_dynamic_client(tmp_path)

    twenty = dynamic_payload(
        quantity=20,
        invoice_id="inv:dynamic_quantity_020",
        idempotency_key="idem:dynamic_quantity_020",
    )
    forty = dynamic_payload(
        quantity=40,
        invoice_id="inv:dynamic_quantity_040",
        idempotency_key="idem:dynamic_quantity_040",
    )
    twenty_response = client.post(
        "/paid/dynamic",
        headers={"Idempotency-Key": twenty["idempotencyKey"]},
        json=twenty,
    )
    forty_response = client.post(
        "/paid/dynamic",
        headers={"Idempotency-Key": forty["idempotencyKey"]},
        json=forty,
    )

    twenty_requirement = decode_payment_required(
        twenty_response.headers["PAYMENT-REQUIRED"]
    ).accepts[0]
    forty_requirement = decode_payment_required(
        forty_response.headers["PAYMENT-REQUIRED"]
    ).accepts[0]
    assert twenty_response.status_code == 402
    assert forty_response.status_code == 402
    assert twenty_requirement.amount == "12000000"
    assert forty_requirement.amount == "24000000"
    assert twenty_requirement.extra.source_tag == SOURCE_TAG
    assert forty_requirement.extra.source_tag == SOURCE_TAG
    assert [call.payload["quantity"] for call in pricing_calls] == [20, 40]


def test_dynamic_price_rejects_tampered_intent_before_challenge(tmp_path) -> None:
    client, _pricing_calls, route_calls = build_dynamic_client(tmp_path)
    payload = dynamic_payload(
        quantity=20,
        amount_drops="1",
        invoice_id="inv:dynamic_tampered_001",
        idempotency_key="idem:dynamic_tampered_001",
    )

    response = client.post(
        "/paid/dynamic",
        headers={"Idempotency-Key": payload["idempotencyKey"]},
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert "amountDrops" in response.json()["message"]
    assert "PAYMENT-REQUIRED" not in response.headers
    assert route_calls == []


def test_invoice_cannot_be_reused_for_changed_dynamic_request(tmp_path) -> None:
    client, _pricing_calls, route_calls = build_dynamic_client(tmp_path)
    first = dynamic_payload(
        quantity=20,
        invoice_id="inv:dynamic_binding_001",
        idempotency_key="idem:dynamic_binding_001",
    )
    changed = dynamic_payload(
        quantity=30,
        invoice_id="inv:dynamic_binding_001",
        idempotency_key="idem:dynamic_binding_002",
    )

    challenge = client.post(
        "/paid/dynamic",
        headers={"Idempotency-Key": first["idempotencyKey"]},
        json=first,
    )
    conflict = client.post(
        "/paid/dynamic",
        headers={"Idempotency-Key": changed["idempotencyKey"]},
        json=changed,
    )

    assert challenge.status_code == 402
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "invoice_mismatch"
    assert route_calls == []


def test_signed_dynamic_terms_are_checked_before_facilitator(tmp_path) -> None:
    facilitator = RecordingFacilitator()
    client, _pricing_calls, route_calls = build_dynamic_client(
        tmp_path,
        facilitator=facilitator,
    )
    payload = dynamic_payload(
        quantity=20,
        invoice_id="inv:dynamic_signature_001",
        idempotency_key="idem:dynamic_signature_001",
    )
    headers = {"Idempotency-Key": payload["idempotencyKey"]}
    challenge = client.post("/paid/dynamic", headers=headers, json=payload)
    signature = payment_signature(
        challenge.headers["PAYMENT-REQUIRED"],
        accepted_amount="1",
    )

    response = client.post(
        "/paid/dynamic",
        headers={**headers, "PAYMENT-SIGNATURE": signature},
        json=payload,
    )

    assert response.status_code == 409
    assert response.json()["error"] == "invoice_mismatch"
    assert facilitator.calls == []
    assert route_calls == []


def test_dynamic_paid_response_replays_without_second_settlement(tmp_path) -> None:
    facilitator = RecordingFacilitator()
    client, pricing_calls, route_calls = build_dynamic_client(
        tmp_path,
        facilitator=facilitator,
    )
    payload = dynamic_payload(
        quantity=40,
        invoice_id="inv:dynamic_settlement_001",
        idempotency_key="idem:dynamic_settlement_001",
    )
    headers = {"Idempotency-Key": payload["idempotencyKey"]}
    challenge = client.post("/paid/dynamic", headers=headers, json=payload)
    signature = payment_signature(challenge.headers["PAYMENT-REQUIRED"])
    paid_headers = {**headers, "PAYMENT-SIGNATURE": signature}

    paid = client.post("/paid/dynamic", headers=paid_headers, json=payload)
    replay = client.post("/paid/dynamic", headers=paid_headers, json=payload)

    assert paid.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == paid.json()
    assert replay.headers["PAYMENT-RESPONSE"] == paid.headers["PAYMENT-RESPONSE"]
    assert facilitator.calls == ["/verify", "/settle"]
    assert len(pricing_calls) == 2
    assert route_calls == [payload]


def test_identical_unsigned_retry_reuses_invoice_safely(tmp_path) -> None:
    client = build_client(tmp_path)
    headers = {"Idempotency-Key": "idem:provider_demo_001"}
    payload = {
        "invoiceId": "inv:provider_demo_001",
        "idempotencyKey": "idem:provider_demo_001",
    }

    first = client.post("/paid/demo", headers=headers, json=payload)
    second = client.post("/paid/demo", headers=headers, json=payload)

    assert first.status_code == 402
    assert second.status_code == 402
    first_challenge = decode_payment_required(
        first.headers["PAYMENT-REQUIRED"]
    )
    second_challenge = decode_payment_required(
        second.headers["PAYMENT-REQUIRED"]
    )
    assert first_challenge.accepts[0].extra.invoice_id == payload["invoiceId"]
    assert second_challenge.accepts[0].extra.invoice_id == payload["invoiceId"]


def test_options_preflight_is_not_charged(tmp_path) -> None:
    response = build_client(tmp_path).options("/paid/demo")

    assert response.status_code != 402


def test_paid_resource_requires_idempotency_key(tmp_path) -> None:
    response = build_client(tmp_path).post("/paid/demo")

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("network", "xrpl:0", "xrpl:1"),
        ("asset", "RLUSD", "XRP"),
    ],
)
def test_provider_rejects_unsupported_payment_configuration(
    field: str,
    value: str,
    message: str,
) -> None:
    data = {
        "protected_paths": "/paid/demo",
        "price_drops": "5000",
        "pay_to_address": PAYEE,
        "facilitator_url": "https://facilitator.example",
        field: value,
    }

    with pytest.raises(ValidationError, match=message):
        ProviderPaymentConfig(**data)


def test_provider_requires_exactly_one_pricing_mode(tmp_path) -> None:
    config_without_price = ProviderPaymentConfig(
        protected_paths="/paid/demo",
        pay_to_address=PAYEE,
        facilitator_url="https://facilitator.example",
    )
    with pytest.raises(ValueError, match="configure price_drops"):
        create_standalone_provider_app(
            config_without_price,
            SQLiteInvoiceStore(tmp_path / "missing-price.sqlite3"),
            facilitator=object(),
        )

    config_with_price = config_without_price.model_copy(
        update={"price_drops": "5000"}
    )
    with pytest.raises(ValueError, match="mutually exclusive"):
        create_standalone_provider_app(
            config_with_price,
            SQLiteInvoiceStore(tmp_path / "ambiguous-price.sqlite3"),
            facilitator=object(),
            price_resolver=lambda _context: "5000",
        )
