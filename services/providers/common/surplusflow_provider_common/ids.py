from __future__ import annotations

import secrets


def new_identifier(prefix: str) -> str:
    """Matches the frozen Identifier pattern `^[a-z][a-z0-9_-]{2,63}$`."""

    return f"{prefix}_{secrets.token_hex(6)}"


def new_pickup_token(seller_id: str) -> str:
    return f"pickup_{seller_id}_{secrets.token_hex(8)}"


def new_tracking_code(provider_id: str) -> str:
    return f"track_{provider_id}_{secrets.token_hex(6)}"[:64]
