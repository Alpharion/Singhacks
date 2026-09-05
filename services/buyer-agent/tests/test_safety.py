"""Person 2 must never touch a wallet seed or build a raw transaction."""

from __future__ import annotations

from pathlib import Path

import pytest

from buyer_agent import config


def source_files() -> list[Path]:
    root = Path(config.__file__).parent
    return sorted(path for path in root.glob("*.py"))


def test_no_module_reads_a_wallet_seed():
    offenders = []
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        for name in config.SEED_ENV_VARS:
            # config.py names them only to assert they are absent.
            if name in text and path.name != "config.py":
                offenders.append(f"{path.name} references {name}")
    assert offenders == []


def test_no_module_signs_or_submits_a_transaction():
    banned = ("xrpl.wallet", "Wallet.from_seed", "autofill", "sign_and_submit", "safe_sign")
    offenders = [
        f"{path.name} uses {token}"
        for path in source_files()
        for token in banned
        if token in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_a_leaked_seed_stops_the_service(monkeypatch):
    monkeypatch.setenv("XRPL_BUYER_SEED", "sEdSomethingThatShouldNotBeHere")
    with pytest.raises(RuntimeError, match="never receive wallet seeds"):
        config.assert_no_seed_access()


def test_no_seed_present_is_fine(monkeypatch):
    for name in config.SEED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    config.assert_no_seed_access()


def test_fixture_payees_are_refused_in_x402_mode(monkeypatch):
    """The frozen fixtures ship synthetic addresses that cannot receive XRP."""
    monkeypatch.delenv("BUYER_AGENT_ALLOWED_PAYEES", raising=False)
    for name in config.PROVIDER_PAYEE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    settings = config.Settings(payment_mode="x402")
    with pytest.raises(RuntimeError, match="not valid XRPL classic addresses"):
        config.assert_payees_usable(settings)


def test_fixture_payees_are_fine_in_simulated_mode(monkeypatch):
    monkeypatch.delenv("BUYER_AGENT_ALLOWED_PAYEES", raising=False)
    config.assert_payees_usable(config.Settings(payment_mode="simulated"))


def test_real_addresses_from_env_are_accepted(monkeypatch):
    monkeypatch.delenv("BUYER_AGENT_ALLOWED_PAYEES", raising=False)
    for name in config.PROVIDER_PAYEE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XRPL_BAKERY_PAY_TO", "rBXVQRYBGNMG4qW1BJHTpuSyyrJDtQe9pE")
    settings = config.Settings(payment_mode="x402")
    assert settings.allowed_payees == ("rBXVQRYBGNMG4qW1BJHTpuSyyrJDtQe9pE",)
    config.assert_payees_usable(settings)


def test_a_runtime_address_cannot_widen_the_allowlist(monkeypatch):
    """Only pre-authorized configuration may nominate a payee."""
    monkeypatch.delenv("BUYER_AGENT_ALLOWED_PAYEES", raising=False)
    for name in config.PROVIDER_PAYEE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XRPL_HOTEL_PAY_TO", "rBXVQRYBGNMG4qW1BHyyFLKDJmEx3naHCs")
    assert config.Settings().allowed_payees == ("rBXVQRYBGNMG4qW1BHyyFLKDJmEx3naHCs",)
