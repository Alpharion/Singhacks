import os
from collections.abc import Mapping

from xrpl.wallet import Wallet

from .errors import WalletConfigurationError


def load_buyer_wallet(
    environment: Mapping[str, str] | None = None,
    variable_name: str = "XRPL_BUYER_SEED",
) -> Wallet:
    """Load a wallet at the signing boundary without logging secret material."""

    source = environment if environment is not None else os.environ
    seed = source.get(variable_name)
    if not seed:
        raise WalletConfigurationError(
            f"{variable_name} is required in an ignored environment file"
        )
    try:
        return Wallet.from_seed(seed)
    except Exception:
        raise WalletConfigurationError(
            f"{variable_name} does not contain a valid XRPL seed"
        ) from None
    finally:
        seed = None
