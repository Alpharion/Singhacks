from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

BUYER_ADDRESS = "rTfvjSafenA8Bws6rFznqmymZjDPBUmjC"


class FakeFacilitatorResponse:
    def __init__(self, body: dict[str, object], status_code: int = 200) -> None:
        self.status_code = status_code
        self._body = body
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, object]:
        return self._body


class RecordingFacilitator:
    """Fake x402 facilitator matching packages/payments' own test double
    (`packages/payments/tests/test_provider.py::RecordingFacilitator`):
    always approves verify and settles with a deterministic transaction
    hash, so these tests never touch the real XRPL testnet facilitator."""

    def __init__(self, *, payer: str = BUYER_ADDRESS, transaction: str | None = None) -> None:
        self._client = self
        self.calls: list[str] = []
        self.payer = payer
        self.transaction = transaction or "A" * 64

    async def post(self, path: str, *, json: dict[str, object]) -> FakeFacilitatorResponse:  # noqa: A002
        self.calls.append(path)
        if path == "/verify":
            return FakeFacilitatorResponse({"isValid": True})
        assert path == "/settle"
        return FakeFacilitatorResponse(
            {
                "success": True,
                "transaction": self.transaction,
                "network": "xrpl:1",
                "payer": self.payer,
            }
        )


def build_payment_signature(payment_required_header: str, *, accepted_amount: str | None = None) -> str:
    """Build a PAYMENT-SIGNATURE header by echoing back a PAYMENT-REQUIRED
    challenge, matching the wire shape `RecordingFacilitator`/x402-xrpl
    expects. `accepted_amount` lets a test tamper with the signed amount."""

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


def _make_client(tmp_path, monkeypatch, *, seller_id: str, port: str, facilitator: object):
    db_path = tmp_path / f"{seller_id}-test.db"
    monkeypatch.setenv("SURPLUSFLOW_DB_PATH", str(db_path))
    monkeypatch.setenv("SELLER_ID", seller_id)
    monkeypatch.setenv("PORT", port)
    monkeypatch.setenv("XRPL_FACILITATOR_URL", "https://facilitator.example")

    import surplusflow_provider_common.db as db_module

    db_module._engine = None
    db_module._SessionLocal = None

    from app.main import create_app

    app = create_app(facilitator=facilitator)
    return TestClient(app)


@pytest.fixture()
def facilitator() -> RecordingFacilitator:
    return RecordingFacilitator()


@pytest.fixture()
def client(tmp_path, monkeypatch, facilitator):
    with _make_client(tmp_path, monkeypatch, seller_id="seller_bakery_001", port="8011", facilitator=facilitator) as c:
        yield c


@pytest.fixture()
def hotel_facilitator() -> RecordingFacilitator:
    return RecordingFacilitator()


@pytest.fixture()
def hotel_client(tmp_path, monkeypatch, hotel_facilitator):
    """Harbour Hotel Kitchen: offer_hotel_001 has quantityAvailable=60, used to
    cover the frozen fixture's partial-quantity scenario (40 of 60 meals)."""

    with _make_client(
        tmp_path, monkeypatch, seller_id="seller_hotel_001", port="8012", facilitator=hotel_facilitator
    ) as c:
        yield c
