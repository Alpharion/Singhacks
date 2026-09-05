from __future__ import annotations

import pytest

from surplusflow_payments.errors import PaymentExecutionError
from surplusflow_payments.status import TransactionStatusClient

TX_HASH = "A" * 64


class FakeResponse:
    result = {
        "validated": True,
        "ledger_index": 1234,
        "meta": {"TransactionResult": "tesSUCCESS"},
    }


class FakeClient:
    def request(self, request):
        assert request.transaction == TX_HASH.lower()
        return FakeResponse()


class BrokenClient:
    def request(self, request):
        del request
        raise ConnectionError("secret upstream detail")


def test_reads_validated_transaction_status() -> None:
    status = TransactionStatusClient(
        "https://rpc.example",
        client=FakeClient(),
    ).get(TX_HASH.lower())

    assert status.transaction_hash == TX_HASH
    assert status.validated is True
    assert status.result_code == "tesSUCCESS"
    assert status.ledger_index == 1234


def test_sanitizes_rpc_failure() -> None:
    with pytest.raises(PaymentExecutionError, match="could not retrieve"):
        TransactionStatusClient(
            "https://rpc.example",
            client=BrokenClient(),
        ).get(TX_HASH)
