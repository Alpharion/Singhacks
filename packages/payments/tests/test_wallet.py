from __future__ import annotations

import pytest
from xrpl.wallet import Wallet

from surplusflow_payments.errors import WalletConfigurationError
from surplusflow_payments.wallet import load_buyer_wallet


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
