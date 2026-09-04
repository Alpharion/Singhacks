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
