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

# Fixture payees from packages/contracts. Synthetic and shape-valid only; real
# runs must supply funded Testnet addresses through ignored environment files.
DEMO_ALLOWED_PAYEES = (
    "rFoodA1111111111111111111111111",
    "rFoodB1111111111111111111111111",
    "rFoodC1111111111111111111111111",
    "rRideA1111111111111111111111111",
    "rRideB1111111111111111111111111",
)


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
    allowed_payees: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            payee.strip()
            for payee in os.getenv(
                "BUYER_AGENT_ALLOWED_PAYEES", ",".join(DEMO_ALLOWED_PAYEES)
            ).split(",")
            if payee.strip()
        )
    )
    max_transaction_spend_drops: str = field(
        default_factory=lambda: os.getenv("BUYER_AGENT_MAX_TX_DROPS", "70000000")
    )

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)


def settings() -> Settings:
    """Read settings fresh so tests can vary the environment per case."""
    return Settings()


def assert_no_seed_access() -> None:
    """Fail loudly if a wallet seed was ever exposed to this process."""
    leaked = [name for name in SEED_ENV_VARS if os.getenv(name)]
    if leaked:
        raise RuntimeError(
            "buyer agent must never receive wallet seeds; found: " + ", ".join(leaked)
        )
