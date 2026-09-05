"""One codebase, two configured courier instances.

Mirrors `services/providers/sellers/app/config.py`'s approach: which
courier this process represents is chosen by `PROVIDER_ID`/`PORT`
(FastRoute Courier 8021, Economy Van 8022 per
`packages/contracts/README.md`'s service table).

`simulate_failure` implements "Courier services: Simulate one capacity or
route failure for fallback testing" (PROJECT_CONTEXT.md section 5) and
"one predictable provider failure for the demo" (PROJECT_BRIEF.md, Person
3). It defaults on for Economy Van via `DEMO_ECONOMY_COURIER_FAILURE`
(`.env.example`), and can be overridden per-instance for testing via
`COURIER_SIMULATE_FAILURE`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_ECONOMY_VAN_PROVIDER_ID = "courier_economy_001"


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class CourierSettings:
    provider_id: str
    base_url: str
    simulate_failure: bool


def load_settings() -> CourierSettings:
    provider_id = os.environ.get("PROVIDER_ID")
    if not provider_id:
        raise RuntimeError(
            "PROVIDER_ID environment variable is required (e.g. courier_fast_001). "
            "See services/providers/delivery/README.md."
        )
    port = os.environ.get("PORT", "8021")
    base_url = os.environ.get("COURIER_BASE_URL", f"http://localhost:{port}")

    if "COURIER_SIMULATE_FAILURE" in os.environ:
        simulate_failure = _env_flag("COURIER_SIMULATE_FAILURE", default=False)
    elif provider_id == _ECONOMY_VAN_PROVIDER_ID:
        simulate_failure = _env_flag("DEMO_ECONOMY_COURIER_FAILURE", default=True)
    else:
        simulate_failure = False

    return CourierSettings(provider_id=provider_id, base_url=base_url, simulate_failure=simulate_failure)
