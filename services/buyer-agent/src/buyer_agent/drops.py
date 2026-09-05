"""XRP drop arithmetic.

Every monetary value on the wire is an integer string in drops. Nothing in this
service converts XRP to float for arithmetic; floats only appear when rendering
a human-readable label.
"""

from __future__ import annotations

from collections.abc import Iterable

DROPS_PER_XRP = 1_000_000


def to_int(value: str) -> int:
    return int(value)


def to_str(value: int) -> str:
    if value < 0:
        raise ValueError(f"drops cannot be negative: {value}")
    return str(value)


def total(values: Iterable[str]) -> int:
    return sum(int(value) for value in values)


def from_xrp(xrp: float | int | str) -> int:
    """Convert an XRP figure to drops without floating-point drift."""
    text = str(xrp).strip()
    if "." in text:
        whole, _, fraction = text.partition(".")
        fraction = (fraction + "000000")[:6]
    else:
        whole, fraction = text, "000000"
    return int(whole or "0") * DROPS_PER_XRP + int(fraction)


def to_xrp_label(value: str | int) -> str:
    """Human label such as ``74 XRP`` or ``74.5 XRP``. Display only."""
    amount = int(value)
    whole, remainder = divmod(amount, DROPS_PER_XRP)
    if remainder == 0:
        return f"{whole} XRP"
    return f"{whole}.{remainder:06d}".rstrip("0") + " XRP"
