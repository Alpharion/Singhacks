"""Runtime configuration.

The buyer agent deliberately has no access to any wallet seed. ``assert_no_seed_access``
is called at import time by the payment boundary so a misconfiguration fails loudly
instead of leaking a secret into agent memory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SEED_ENV_VARS = ("XRPL_BUYER_SEED", "XRPL_SELLER_SEED", "XRPL_COURIER_SEED")

# Fixture payees from packages/contracts. These match the contract's address
# pattern but are NOT valid base58check addresses, so the payment boundary
# rejects them. They exist only so simulated runs have something to allow-list.
DEMO_ALLOWED_PAYEES = (
    "rFoodA1111111111111111111111111",
    "rFoodB1111111111111111111111111",
    "rFoodC1111111111111111111111111",
    "rRideA1111111111111111111111111",
    "rRideB1111111111111111111111111",
)

# Pre-authorized provider addresses, supplied through ignored environment files.
# The allowlist must come from configuration the buyer approved in advance --
# never from an address discovered at runtime, which would let a compromised
# marketplace nominate its own payee.
PROVIDER_PAYEE_ENV_VARS = (
    "XRPL_BAKERY_PAY_TO",
    "XRPL_HOTEL_PAY_TO",
    "XRPL_GRILL_PAY_TO",
    "XRPL_FAST_COURIER_PAY_TO",
    "XRPL_ECONOMY_COURIER_PAY_TO",
)


def _configured_payees() -> tuple[str, ...]:
    explicit = os.getenv("BUYER_AGENT_ALLOWED_PAYEES", "")
    if explicit.strip():
        return tuple(item.strip() for item in explicit.split(",") if item.strip())
    from_env = tuple(
        value.strip()
        for name in PROVIDER_PAYEE_ENV_VARS
        if (value := os.getenv(name, "")).strip()
    )
    return from_env or DEMO_ALLOWED_PAYEES


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def contracts_dir() -> Path:
    return repo_root() / "packages" / "contracts"


@dataclass(frozen=True)
class Settings:
    marketplace_base_url: str = field(
        default_factory=lambda: os.getenv("MARKETPLACE_BASE_URL", "http://localhost:8002")
    )
    discovery_mode: str = field(
        default_factory=lambda: os.getenv("BUYER_AGENT_DISCOVERY_MODE", "fixtures")
    )
    payment_mode: str = field(
        default_factory=lambda: os.getenv("BUYER_AGENT_PAYMENT_MODE", "simulated")
    )
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    request_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("BUYER_AGENT_TIMEOUT_SECONDS", "30"))
    )
    max_replans: int = field(
        default_factory=lambda: int(os.getenv("BUYER_AGENT_MAX_REPLANS", "4"))
    )
    allowed_payees: tuple[str, ...] = field(default_factory=_configured_payees)
    max_transaction_spend_drops: str = field(
        default_factory=lambda: os.getenv("BUYER_AGENT_MAX_TX_DROPS", "70000000")
    )

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)


def settings() -> Settings:
    """Read settings fresh so tests can vary the environment per case."""
    return Settings()


def assert_payees_usable(settings: Settings) -> None:
    """In x402 mode every approved payee must be a real XRPL address.

    The frozen fixtures ship deliberately synthetic addresses. Catching them
    here produces one clear message at startup instead of a validation error
    from the payment boundary midway through a run.
    """
    if settings.payment_mode != "x402":
        return
    if not settings.allowed_payees:
        raise RuntimeError(
            "x402 mode needs an approved payee list. Set the XRPL_*_PAY_TO variables "
            "in .env, or BUYER_AGENT_ALLOWED_PAYEES."
        )
    from xrpl.core.addresscodec import is_valid_classic_address

    invalid = [
        payee for payee in settings.allowed_payees if not is_valid_classic_address(payee)
    ]
    if invalid:
        raise RuntimeError(
            "x402 mode requires funded Testnet addresses, but these approved payees are "
            "not valid XRPL classic addresses: "
            + ", ".join(invalid)
            + ". The contract fixtures use synthetic placeholders; supply real addresses "
            "through the XRPL_*_PAY_TO variables in your ignored .env."
        )


def assert_no_seed_access() -> None:
    """Fail loudly if a wallet seed was ever exposed to this process."""
    leaked = [name for name in SEED_ENV_VARS if os.getenv(name)]
    if leaked:
        raise RuntimeError(
            "buyer agent must never receive wallet seeds; found: " + ", ".join(leaked)
        )
