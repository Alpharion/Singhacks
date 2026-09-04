from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from surplusflow_payments.headers import decode_payment_required
from surplusflow_payments.invoice_store import SQLiteInvoiceStore
from surplusflow_payments.provider import (
    ProviderPaymentConfig,
    create_standalone_provider_app,
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


def test_health_is_public(tmp_path) -> None:
    response = build_client(tmp_path).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_paid_resource_issues_bound_x402_challenge(tmp_path) -> None:
    response = build_client(tmp_path).post("/paid/demo")

    assert response.status_code == 402
    challenge = decode_payment_required(response.headers["PAYMENT-REQUIRED"])
    option = challenge.accepts[0]
    assert challenge.x402_version == 2
    assert option.network == "xrpl:1"
    assert option.asset == "XRP"
    assert option.pay_to == PAYEE
    assert option.amount == "5000"
    assert option.extra.source_tag == SOURCE_TAG
    assert option.extra.invoice_id


def test_options_preflight_is_not_charged(tmp_path) -> None:
    response = build_client(tmp_path).options("/paid/demo")

    assert response.status_code != 402


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
