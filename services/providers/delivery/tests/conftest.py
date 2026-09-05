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
        self.transaction = transaction or "B" * 64

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


def _make_client(
    tmp_path,
    monkeypatch,
    *,
    provider_id: str,
    port: str,
    facilitator: object,
    simulate_failure: bool | None = None,
):
    db_path = tmp_path / f"{provider_id}-test.db"
    monkeypatch.setenv("SURPLUSFLOW_DB_PATH", str(db_path))
    monkeypatch.setenv("PROVIDER_ID", provider_id)
    monkeypatch.setenv("PORT", port)
    monkeypatch.setenv("XRPL_FACILITATOR_URL", "https://facilitator.example")
    if simulate_failure is None:
        monkeypatch.delenv("COURIER_SIMULATE_FAILURE", raising=False)
    else:
        monkeypatch.setenv("COURIER_SIMULATE_FAILURE", "true" if simulate_failure else "false")

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
    """FastRoute Courier: reliable, no simulated failure."""

    with _make_client(
        tmp_path,
        monkeypatch,
        provider_id="courier_fast_001",
        port="8021",
        facilitator=facilitator,
        simulate_failure=False,
    ) as c:
        yield c


@pytest.fixture()
def failing_facilitator() -> RecordingFacilitator:
    return RecordingFacilitator()


@pytest.fixture()
def failing_client(tmp_path, monkeypatch, failing_facilitator):
    """Economy Van with the demo failure explicitly enabled."""

    with _make_client(
        tmp_path,
        monkeypatch,
        provider_id="courier_economy_001",
        port="8022",
        facilitator=failing_facilitator,
        simulate_failure=True,
    ) as c:
        yield c
