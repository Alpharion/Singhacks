from __future__ import annotations

import pytest

from surplusflow_payments.config import PaymentSettings
from surplusflow_payments.errors import PaymentExecutionError, PolicyViolation
from surplusflow_payments.readiness import (
    TestnetReadinessChecker as ReadinessChecker,
)

from conftest import PAYEE, SECOND_PAYEE


class FakeResponse:
    def __init__(self, balance: str) -> None:
        self.result = {"account_data": {"Balance": balance}}


class FakeClient:
    def __init__(self, balances: dict[str, str]) -> None:
        self.balances = balances
        self.requests = []

    def request(self, request):
        assert request.ledger_index == "validated"
        self.requests.append(request)
        return FakeResponse(self.balances[request.account])


class BrokenClient:
    def request(self, request):
        del request
        raise ConnectionError("private upstream diagnostics")


def test_reports_public_balances_without_secret_material(buyer_wallet) -> None:
    balances = {
        buyer_wallet.classic_address: "10000000",
        PAYEE: "2000000",
        SECOND_PAYEE: "0",
    }
    client = FakeClient(balances)
    report = ReadinessChecker(
        PaymentSettings(),
        client=client,
        wallet_loader=lambda: buyer_wallet,
    ).check({"bakery": PAYEE, "courier": SECOND_PAYEE})

    public = report.to_public_dict()
    assert report.ready is False
    assert public["network"] == "xrpl:1"
    assert public["accounts"][0]["balanceXrp"] == "10"
    assert public["accounts"][2]["funded"] is False
    assert len(client.requests) == 3


def test_reports_ready_when_every_account_is_funded(buyer_wallet) -> None:
    balances = {
        buyer_wallet.classic_address: "10000000",
        PAYEE: "2000000",
    }
    report = ReadinessChecker(
        PaymentSettings(),
        client=FakeClient(balances),
        wallet_loader=lambda: buyer_wallet,
    ).check({"bakery": PAYEE})

    assert report.ready is True


def test_requires_at_least_one_provider(buyer_wallet) -> None:
    checker = ReadinessChecker(
        PaymentSettings(),
        client=FakeClient({}),
        wallet_loader=lambda: buyer_wallet,
    )

    with pytest.raises(PolicyViolation, match="at least one"):
        checker.check({})


def test_rejects_shared_buyer_and_provider_account(buyer_wallet) -> None:
    checker = ReadinessChecker(
        PaymentSettings(),
        client=FakeClient({}),
        wallet_loader=lambda: buyer_wallet,
    )

    with pytest.raises(PolicyViolation, match="separate"):
        checker.check({"provider": buyer_wallet.classic_address})


def test_provider_role_cannot_override_buyer(buyer_wallet) -> None:
    checker = ReadinessChecker(
        PaymentSettings(),
        client=FakeClient({}),
        wallet_loader=lambda: buyer_wallet,
    )

    with pytest.raises(PolicyViolation, match="override"):
        checker.check({"buyer": PAYEE})


def test_rejects_invalid_provider_address(buyer_wallet) -> None:
    checker = ReadinessChecker(
        PaymentSettings(),
        client=FakeClient({}),
        wallet_loader=lambda: buyer_wallet,
    )

    with pytest.raises(PolicyViolation, match="valid XRPL"):
        checker.check({"provider": "not-an-address"})


def test_sanitizes_ledger_lookup_failures(buyer_wallet) -> None:
    checker = ReadinessChecker(
        PaymentSettings(),
        client=BrokenClient(),
        wallet_loader=lambda: buyer_wallet,
    )

    with pytest.raises(PaymentExecutionError, match="for buyer") as error:
        checker.check({"provider": PAYEE})

    assert "private upstream diagnostics" not in str(error.value)
