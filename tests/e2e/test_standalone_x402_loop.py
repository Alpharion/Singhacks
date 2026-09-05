from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import requests
from fastapi.testclient import TestClient
from xrpl.core.binarycodec import decode, encode
from xrpl.models.transactions import Memo, Payment, Transaction
from xrpl.transaction import sign
from xrpl.wallet import Wallet
from x402_xrpl.client.presigned_payment_payer import (
    build_payment_header_for_signed_blob,
    invoice_id_to_invoice_id_field,
    invoice_id_to_memo_hex,
)

from surplusflow_payments import (
    PaymentExecutor,
    PaymentJournal,
    PaymentSettings,
    ProviderPaymentConfig,
    SQLiteInvoiceStore,
    SQLiteProviderResponseStore,
    create_standalone_provider_app,
)
from surplusflow_payments.models import JournalStatus, PurchaseIntent

PAYEE = "rPEPPER7kfTD9w2To4CQk6UCfuHM9c6GDY"
SOURCE_TAG = 20_260_530


class FakeFacilitatorResponse:
    def __init__(
        self,
        body: dict[str, object],
        *,
        status_code: int = 200,
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, object]:
        return self._body


class ValidatingFakeFacilitator:
    """Exercise the SDK protocol without contacting or mutating XRPL."""

    def __init__(self) -> None:
        self._client = self
        self.calls: list[str] = []
        self.settled_hash: str | None = None
        self.settled_transaction: Transaction | None = None

    async def post(
        self,
        path: str,
        *,
        json: dict[str, object],
    ) -> FakeFacilitatorResponse:
        self.calls.append(path)
        if path == "/verify":
            return FakeFacilitatorResponse({"isValid": True})
        if path != "/settle":
            return FakeFacilitatorResponse(
                {"error": "unsupported fake route"},
                status_code=404,
            )

        payment_payload = json["paymentPayload"]
        assert isinstance(payment_payload, dict)
        payload = payment_payload["payload"]
        assert isinstance(payload, dict)
        transaction_json = decode(str(payload["signedTxBlob"]))
        transaction = Transaction.from_xrpl(transaction_json)
        transaction_hash = transaction.get_hash().upper()
        self.settled_hash = transaction_hash
        self.settled_transaction = transaction
        return FakeFacilitatorResponse(
            {
                "success": True,
                "transaction": transaction_hash,
                "network": "xrpl:1",
                "payer": transaction.account,
            }
        )


class ASGIRequestsSession:
    """Adapt requests-style x402 calls to an in-process FastAPI application."""

    def __init__(self, app) -> None:
        self.client = TestClient(app)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs,
    ) -> requests.Response:
        parsed = urlsplit(url)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        response = self.client.request(
            method,
            path,
            headers=headers,
            json=kwargs.get("json"),
        )
        converted = requests.Response()
        converted.status_code = response.status_code
        converted.headers = requests.structures.CaseInsensitiveDict(
            response.headers
        )
        converted._content = response.content
        converted.encoding = response.encoding or "utf-8"
        converted.url = url
        return converted


class OfflinePayer:
    """Sign an inert, fully local fixture transaction that is never submitted."""

    def __init__(self, wallet: Wallet) -> None:
        self.wallet = wallet
        self.last_header: str | None = None

    def create_payment_header(self, requirement, *, extensions=None) -> str:
        invoice_id = requirement.invoice_id()
        assert invoice_id is not None
        source_tag = int(requirement.extra["sourceTag"])
        transaction = Payment(
            account=self.wallet.classic_address,
            destination=requirement.pay_to,
            amount=requirement.amount,
            fee="12",
            sequence=1,
            last_ledger_sequence=100,
            source_tag=source_tag,
            invoice_id=invoice_id_to_invoice_id_field(invoice_id),
            memos=[Memo(memo_data=invoice_id_to_memo_hex(invoice_id))],
        )
        signed = sign(transaction, self.wallet)
        self.last_header = build_payment_header_for_signed_blob(
            req=requirement,
            signed_tx_blob=encode(signed.to_xrpl()),
            invoice_id=invoice_id,
            extensions=extensions,
        )
        return self.last_header


def build_intent() -> PurchaseIntent:
    return PurchaseIntent.model_validate(
        {
            "intentId": "intent_e2e_001",
            "runId": "run_e2e_001",
            "goalId": "goal_e2e_001",
            "resourceType": "food_reservation",
            "providerId": "seller_e2e_001",
            "resourceId": "offer_e2e_001",
            "targetUrl": "http://provider.test/paid/demo",
            "quantity": 20,
            "amountDrops": "10000",
            "payTo": PAYEE,
            "network": "xrpl:1",
            "asset": "XRP",
            "invoiceId": "inv:run_e2e_001:offer_e2e_001:v1",
            "idempotencyKey": "idem:run_e2e_001:offer_e2e_001:v1",
            "expiresAt": datetime.now(UTC) + timedelta(minutes=10),
            "rationale": "Lowest valid food reservation inside policy.",
            "policySnapshot": {
                "walletPolicyId": "policy_e2e_001",
                "maxOrderSpendDrops": "120000000",
                "maxTransactionSpendDrops": "70000000",
                "allowedPayees": [PAYEE],
            },
        }
    )


def test_complete_offline_x402_commercial_loop_and_response_replay(
    tmp_path,
) -> None:
    intent = build_intent()
    buyer = Wallet.create()
    facilitator = ValidatingFakeFacilitator()
    provider_app = create_standalone_provider_app(
        ProviderPaymentConfig(
            protected_paths="/paid/demo",
            price_drops=intent.amount_drops,
            pay_to_address=intent.pay_to,
            facilitator_url="https://unused.example",
        ),
        SQLiteInvoiceStore(tmp_path / "provider-invoices.sqlite3"),
        response_store=SQLiteProviderResponseStore(
            tmp_path / "provider-responses.sqlite3"
        ),
        facilitator=facilitator,
    )
    session = ASGIRequestsSession(provider_app)
    payer = OfflinePayer(buyer)
    journal = PaymentJournal(tmp_path / "buyer-payments.sqlite3")
    executor = PaymentExecutor(
        PaymentSettings(),
        journal,
        wallet_loader=lambda: buyer,
        payer_factory=lambda wallet, network, rpc_url: payer,
    )

    result = executor.execute(
        intent,
        already_spent_drops=0,
        session=session,
    )

    assert result.status_code == 201
    assert result.resource == {
        "reservationId": "reservation_standalone_001",
        "status": "confirmed",
        "valueDelivered": "exclusive demo food reservation",
    }
    assert result.receipt.transaction == facilitator.settled_hash
    assert result.receipt.payer == buyer.classic_address
    assert journal.get(intent.invoice_id).status is JournalStatus.VALIDATED
    assert facilitator.calls == ["/verify", "/settle"]
    assert facilitator.settled_transaction is not None
    assert facilitator.settled_transaction.destination == PAYEE
    assert facilitator.settled_transaction.amount == intent.amount_drops
    assert facilitator.settled_transaction.source_tag == SOURCE_TAG
    assert facilitator.settled_transaction.invoice_id == hashlib.sha256(
        intent.invoice_id.encode()
    ).hexdigest().upper()

    assert payer.last_header is not None
    replay = session.request(
        "POST",
        str(intent.target_url),
        headers={
            "Idempotency-Key": intent.idempotency_key,
            "PAYMENT-SIGNATURE": payer.last_header,
        },
        json=intent.model_dump(mode="json", by_alias=True),
    )

    assert replay.status_code == 201
    assert replay.json() == result.resource
    assert "PAYMENT-RESPONSE" in replay.headers
    assert facilitator.calls == ["/verify", "/settle"]
