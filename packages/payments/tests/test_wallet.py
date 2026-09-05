from __future__ import annotations

import os

import pytest
from xrpl.wallet import Wallet

from surplusflow_payments.errors import WalletConfigurationError
from surplusflow_payments.wallet import WALLET_ENV_FILE_VAR, load_buyer_wallet


def test_loads_wallet_only_from_named_environment_value() -> None:
    source = Wallet.create()

    loaded = load_buyer_wallet({"XRPL_BUYER_SEED": source.seed})

    assert loaded.classic_address == source.classic_address


def test_missing_seed_is_sanitized() -> None:
    with pytest.raises(WalletConfigurationError, match="is required") as error:
        load_buyer_wallet({})

    assert "seed" not in str(error.value).lower().replace("buyer_seed", "")


def test_invalid_seed_is_not_echoed() -> None:
    invalid_seed = "definitely-not-a-real-secret"

    with pytest.raises(WalletConfigurationError) as error:
        load_buyer_wallet({"XRPL_BUYER_SEED": invalid_seed})

    assert invalid_seed not in str(error.value)


def test_default_loader_reads_ignored_wallet_file_without_exporting_seed(
    monkeypatch, tmp_path
) -> None:
    source = Wallet.create()
    wallet_file = tmp_path / "wallet.env"
    wallet_file.write_text(f"XRPL_BUYER_SEED={source.seed}\n", encoding="utf-8")
    monkeypatch.delenv("XRPL_BUYER_SEED", raising=False)
    monkeypatch.setenv(WALLET_ENV_FILE_VAR, str(wallet_file))

    loaded = load_buyer_wallet()

    assert loaded.classic_address == source.classic_address
    assert "XRPL_BUYER_SEED" not in os.environ
