"""Runtime configuration.

Like the buyer agent, this service never holds a wallet seed. It sets prices;
it does not take money. Settlement stays with the provider services and the
payments package.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

SEED_ENV_VARS = ("XRPL_BUYER_SEED", "XRPL_SELLER_SEED", "XRPL_COURIER_SEED")


@dataclass(frozen=True)
class Settings:
    #: Seconds between repricing ticks.
    tick_seconds: float = field(
        default_factory=lambda: float(os.getenv("SELLER_AGENT_TICK_SECONDS", "3"))
    )
    #: How much faster than wall-clock the agent's window runs. A collection
    #: window of several hours is unwatchable in real time, so the demo
    #: compresses it - and says so, on the listing itself.
    time_scale: int = field(
        default_factory=lambda: max(1, int(os.getenv("SELLER_AGENT_TIME_SCALE", "200")))
    )
    #: Simulate a buyer population in-process. On by default so the pricing
    #: loop has something to react to; switch off once the real marketplace
    #: raises enquiries and sales.
    simulated_market: bool = field(
        default_factory=lambda: os.getenv("SELLER_AGENT_SIMULATED_MARKET", "1") != "0"
    )
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)


def settings() -> Settings:
    return Settings()


def assert_no_seed_access() -> None:
    """Fail loudly rather than let a seed sit in this process's environment."""
    leaked = [name for name in SEED_ENV_VARS if os.getenv(name)]
    if leaked:
        raise RuntimeError(
            "The seller agent must never see a wallet seed. Remove from its "
            f"environment: {', '.join(leaked)}."
        )
