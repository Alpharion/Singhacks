from __future__ import annotations

import base64
import json

import pytest
import requests
from xrpl.core.binarycodec import encode
from xrpl.models.transactions import Payment
from xrpl.transaction import sign
from x402_xrpl.clients import X402PurchaseResult
from x402_xrpl.types import PaymentRequirements

from surplusflow_payments.client import PaymentExecutor
from surplusflow_payments.config import PaymentSettings
from surplusflow_payments.errors import (
    PaymentExecutionError,
    PaymentReceiptError,
    PolicyViolation,
    WalletConfigurationError,
)
from surplusflow_payments.journal import PaymentJournal
from surplusflow_payments.models import JournalStatus

from conftest import SOURCE_TAG, requirement_dict


def build_signed_header(wallet, intent) -> tuple[str, str]:
    transaction = Payment(
        account=wallet.classic_address,
        destination=intent.pay_to,
        amount=intent.amount_drops,
        fee="12",
        sequence=1,
        last_ledger_sequence=100,
        source_tag=SOURCE_TAG,
    )
    signed = sign(transaction, wallet)
    envelope = {
        "x402Version": 2,
        "payload": {
            "invoiceId": intent.invoice_id,
            "signedTxBlob": encode(signed.to_xrpl()),
        },
    }
    return (
        base64.b64encode(json.dumps(envelope).encode()).decode(),
        signed.get_hash().upper(),
    )


def make_response(
    *,
    json_body: object | None = None,
    text_body: str = "",
    status_code: int = 201,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.encoding = "utf-8"
    if json_body is not None:
        response._content = json.dumps(json_body).encode()
        response.headers["Content-Type"] = "application/json"
    else:
        response._content = text_body.encode()
        response.headers["Content-Type"] = "text/plain"
    return response


class FakePayer:
    def __init__(self, header: str) -> None:
        self.header = header

    def create_payment_header(self, requirement, *, extensions=None) -> str:
        del requirement, extensions
        return self.header


def build_executor(
    tmp_path,
    buyer_wallet,
    intent,
    purchase_function,
) -> tuple[PaymentExecutor, PaymentJournal, str]:
    signed_header, transaction_hash = build_signed_header(buyer_wallet, intent)
    journal = PaymentJournal(tmp_path / "payments.sqlite3")
    executor = PaymentExecutor(
        PaymentSettings(payment_journal_path=tmp_path / "ignored.sqlite3"),
        journal,
        wallet_loader=lambda: buyer_wallet,
        payer_factory=lambda wallet, network, rpc_url: FakePayer(signed_header),
        purchase_function=purchase_function,
    )
    return executor, journal, transaction_hash


def purchase_success(intent, payer, transaction_hash, *, resource=None):
    def purchase(url: str, **kwargs) -> X402PurchaseResult:
        assert url == str(intent.target_url)
        assert kwargs["network_filter"] == "xrpl:1"
        assert kwargs["scheme_filter"] == "exact"
        assert kwargs["max_value"] == int(intent.amount_drops)
        assert kwargs["invoice_binding"] == "both"
        assert kwargs["confirmation_mode"] == "auto"
        assert kwargs["headers"]["Idempotency-Key"] == intent.idempotency_key

        raw_requirement = requirement_dict(intent)
        selected = kwargs["payment_requirements_selector"]([raw_requirement])
        requirement = PaymentRequirements.from_dict(selected)
        kwargs["payment_header_factory"](requirement, extensions=None)

        return X402PurchaseResult(
            status="success",
            response=(
                make_response(json_body=resource or {"reservationId": "res_001"})
                if not isinstance(resource, str)
                else make_response(text_body=resource)
            ),
            payment_response={
                "success": True,
                "transaction": transaction_hash,
                "network": "xrpl:1",
                "payer": payer,
            },
        )

    return purchase


def test_executes_authorized_purchase_and_records_validated_receipt(
    tmp_path,
    buyer_wallet,
    intent,
) -> None:
    _, _, transaction_hash = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        lambda *_args, **_kwargs: None,
    )
    purchase = purchase_success(
        intent,
        buyer_wallet.classic_address,
        transaction_hash,
    )
    executor, journal, _ = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        purchase,
    )

    result = executor.execute(intent, already_spent_drops=0)

    assert result.status_code == 201
    assert result.resource == {"reservationId": "res_001"}
    assert result.receipt.transaction == transaction_hash
    entry = journal.get(intent.invoice_id)
    assert entry.status is JournalStatus.VALIDATED
    assert entry.transaction_hash == transaction_hash


def test_returns_text_resource_when_provider_body_is_not_json(
    tmp_path,
    buyer_wallet,
    intent,
) -> None:
    _, _, transaction_hash = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        lambda *_args, **_kwargs: None,
    )
    purchase = purchase_success(
        intent,
        buyer_wallet.classic_address,
        transaction_hash,
        resource="confirmed",
    )
    executor, _, _ = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        purchase,
    )

    result = executor.execute(intent, already_spent_drops=0)

    assert result.resource == "confirmed"


def test_purchase_failure_before_signing_is_retryable(
    tmp_path,
    buyer_wallet,
    intent,
) -> None:
    def fail_before_signing(*_args, **_kwargs):
        raise ConnectionError("upstream details must be hidden")

    executor, journal, _ = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        fail_before_signing,
    )

    with pytest.raises(PaymentExecutionError, match="client execution failed"):
        executor.execute(intent, already_spent_drops=0)

    entry = journal.get(intent.invoice_id)
    assert entry.status is JournalStatus.FAILED
    assert entry.error_code == "client_exception"


def test_purchase_failure_after_signing_requires_reconciliation(
    tmp_path,
    buyer_wallet,
    intent,
) -> None:
    def fail_after_signing(_url: str, **kwargs):
        requirement = PaymentRequirements.from_dict(requirement_dict(intent))
        kwargs["payment_header_factory"](requirement, extensions=None)
        raise TimeoutError("settlement outcome unknown")

    executor, journal, transaction_hash = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        fail_after_signing,
    )

    with pytest.raises(PaymentExecutionError):
        executor.execute(intent, already_spent_drops=0)

    entry = journal.get(intent.invoice_id)
    assert entry.status is JournalStatus.UNCERTAIN
    assert entry.transaction_hash == transaction_hash


@pytest.mark.parametrize(
    ("result_factory", "expected_error", "expected_code"),
    [
        (
            lambda response, tx_hash, payer: X402PurchaseResult(
                status="failed",
                response=response,
                reason="rejected",
            ),
            PaymentExecutionError,
            "x402_failed",
        ),
        (
            lambda response, tx_hash, payer: X402PurchaseResult(
                status="success",
                response=response,
            ),
            PaymentReceiptError,
            "missing_payment_response",
        ),
    ],
)
def test_rejects_unsuccessful_or_receiptless_result_before_signing(
    tmp_path,
    buyer_wallet,
    intent,
    result_factory,
    expected_error,
    expected_code: str,
) -> None:
    def purchase(*_args, **_kwargs):
        return result_factory(
            make_response(json_body={"ok": True}),
            "A" * 64,
            buyer_wallet.classic_address,
        )

    executor, journal, _ = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        purchase,
    )

    with pytest.raises(expected_error):
        executor.execute(intent, already_spent_drops=0)

    entry = journal.get(intent.invoice_id)
    assert entry.status is JournalStatus.FAILED
    assert entry.error_code == expected_code


def test_invalid_receipt_after_signing_is_marked_uncertain(
    tmp_path,
    buyer_wallet,
    intent,
) -> None:
    _, _, transaction_hash = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        lambda *_args, **_kwargs: None,
    )

    def purchase(_url: str, **kwargs):
        requirement = PaymentRequirements.from_dict(requirement_dict(intent))
        kwargs["payment_header_factory"](requirement, extensions=None)
        return X402PurchaseResult(
            status="success",
            response=make_response(json_body={"ok": True}),
            payment_response={
                "success": True,
                "transaction": "0" * 64,
                "network": "xrpl:1",
                "payer": buyer_wallet.classic_address,
            },
        )

    executor, journal, _ = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        purchase,
    )

    with pytest.raises(PaymentReceiptError, match="pre-submission hash"):
        executor.execute(intent, already_spent_drops=0)

    entry = journal.get(intent.invoice_id)
    assert entry.status is JournalStatus.UNCERTAIN
    assert entry.transaction_hash == transaction_hash
    assert entry.error_code == "invalid_payment_receipt"


@pytest.mark.parametrize(
    ("headers", "message", "error_code"),
    [
        (
            {"payment-signature": "caller-controlled"},
            "PAYMENT-SIGNATURE",
            "caller_payment_header",
        ),
        (
            {"IDEMPOTENCY-KEY": "idem:not_the_intent"},
            "does not match",
            "caller_idempotency_mismatch",
        ),
    ],
)
def test_rejects_caller_controlled_payment_headers(
    tmp_path,
    buyer_wallet,
    intent,
    headers: dict[str, str],
    message: str,
    error_code: str,
) -> None:
    def should_not_run(*_args, **_kwargs):
        raise AssertionError("purchase function must not be called")

    executor, journal, _ = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        should_not_run,
    )

    with pytest.raises(PolicyViolation, match=message):
        executor.execute(intent, already_spent_drops=0, headers=headers)

    assert journal.get(intent.invoice_id).error_code == error_code


def test_accepts_matching_case_insensitive_idempotency_header(
    tmp_path,
    buyer_wallet,
    intent,
) -> None:
    _, _, transaction_hash = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        lambda *_args, **_kwargs: None,
    )
    purchase = purchase_success(
        intent,
        buyer_wallet.classic_address,
        transaction_hash,
    )
    executor, _, _ = build_executor(
        tmp_path,
        buyer_wallet,
        intent,
        purchase,
    )

    result = executor.execute(
        intent,
        already_spent_drops=0,
        headers={"idempotency-key": intent.idempotency_key},
    )

    assert result.receipt.validated is True


@pytest.mark.parametrize(
    "wallet_loader",
    [
        lambda: (_ for _ in ()).throw(ValueError("raw secret detail")),
        lambda: (_ for _ in ()).throw(
            WalletConfigurationError("configured wallet unavailable")
        ),
    ],
)
def test_wallet_loader_failures_are_sanitized_and_recorded(
    tmp_path,
    intent,
    wallet_loader,
) -> None:
    journal = PaymentJournal(tmp_path / "payments.sqlite3")
    executor = PaymentExecutor(
        PaymentSettings(),
        journal,
        wallet_loader=wallet_loader,
    )

    with pytest.raises(WalletConfigurationError):
        executor.execute(intent, already_spent_drops=0)

    assert journal.get(intent.invoice_id).error_code == "wallet_configuration_error"


def test_payer_configuration_failure_is_sanitized_and_recorded(
    tmp_path,
    buyer_wallet,
    intent,
) -> None:
    journal = PaymentJournal(tmp_path / "payments.sqlite3")

    def broken_payer_factory(wallet, network, rpc_url):
        del wallet, network, rpc_url
        raise ValueError("internal signer details")

    executor = PaymentExecutor(
        PaymentSettings(),
        journal,
        wallet_loader=lambda: buyer_wallet,
        payer_factory=broken_payer_factory,
    )

    with pytest.raises(PaymentExecutionError, match="could not be configured"):
        executor.execute(intent, already_spent_drops=0)

    assert journal.get(intent.invoice_id).error_code == "payer_configuration_error"
