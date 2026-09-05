"""One codebase, three configured seller instances.

Which seller this process represents is chosen entirely by environment
variables (`SELLER_ID`, `PORT`), matching the ports and IDs frozen in
`packages/contracts/README.md`'s service table (Green Oven 8011, Harbour
Hotel 8012, Central Grill 8013). This avoids maintaining three near-
identical FastAPI apps for "three configurable seller simulators"
(PROJECT_CONTEXT.md section 11, Person 3 responsibilities).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SellerSettings:
    seller_id: str
    base_url: str


def load_settings() -> SellerSettings:
    seller_id = os.environ.get("SELLER_ID")
    if not seller_id:
        raise RuntimeError(
            "SELLER_ID environment variable is required (e.g. seller_bakery_001). "
            "See services/providers/sellers/README.md."
        )
    port = os.environ.get("PORT", "8011")
    base_url = os.environ.get("SELLER_BASE_URL", f"http://localhost:{port}")
    return SellerSettings(seller_id=seller_id, base_url=base_url)
