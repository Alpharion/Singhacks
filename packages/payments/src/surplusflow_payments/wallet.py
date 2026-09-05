import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from xrpl.wallet import Wallet

from .config import PROJECT_ENV_FILE
from .errors import WalletConfigurationError


WALLET_ENV_FILE_VAR = "XRPL_WALLET_ENV_FILE"


def _default_seed_source() -> Mapping[str, str | None]:
    """Read the buyer seed at the signing boundary without exporting it.

    A caller may still provide ``XRPL_BUYER_SEED`` in the process environment
    (the standalone tools support that), but the integrated buyer agent keeps
    seed variables out of its environment. In that case only this payment
    module reads the ignored project ``.env`` file, or the Docker secret path
    named by ``XRPL_WALLET_ENV_FILE``.
    """

    if os.environ.get("XRPL_BUYER_SEED"):
        return os.environ
    configured_path = os.environ.get(WALLET_ENV_FILE_VAR)
    path = Path(configured_path) if configured_path else PROJECT_ENV_FILE
    return dotenv_values(path)


def load_buyer_wallet(
    environment: Mapping[str, str | None] | None = None,
    variable_name: str = "XRPL_BUYER_SEED",
) -> Wallet:
    """Load a wallet at the signing boundary without logging secret material.

    Explicit mappings are useful for tests and external secret managers. When
    omitted, the seed is read lazily from the process environment or ignored
    wallet file; it is never added to ``os.environ``.
    """

    source = environment if environment is not None else _default_seed_source()
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
