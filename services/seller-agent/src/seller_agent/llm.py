"""The model boundary.

The language model gets exactly one job on this side, the same one it has on the
buyer side: turn a decision that has already been made into a sentence a person
can read. It never sees the floor as something negotiable, never chooses a
price, and its output is never parsed back into a number.

With no `OPENAI_API_KEY` the deterministic phrasing below runs alone, and every
test still passes.
"""

from __future__ import annotations

import logging
import os

from . import drops
from .models import PricingAction, PricingFactors

log = logging.getLogger(__name__)


def _deterministic(
    *,
    action: PricingAction,
    previous_drops: int,
    new_drops: int,
    floor_drops: int,
    factors: PricingFactors,
) -> str:
    remaining_pct = round((1 - factors.time_elapsed) * 100)

    if action == "floor":
        return (
            f"At the floor of {drops.to_xrp_label(floor_drops)} with "
            f"{factors.remaining} unsold and {remaining_pct}% of the window left. "
            "This is as low as the seller allowed."
        )
    if action == "reduce":
        return (
            f"Cut from {drops.to_xrp_label(previous_drops)} to "
            f"{drops.to_xrp_label(new_drops)}: {remaining_pct}% of the collection "
            f"window is left and {factors.remaining} units are still unsold."
        )
    if action == "raise":
        return (
            f"Raised to {drops.to_xrp_label(new_drops)}: "
            f"{round(factors.sell_through * 100)}% has sold with {remaining_pct}% of the "
            f"window still to run, and {factors.enquiries} buyers are asking."
        )
    return (
        f"Holding at {drops.to_xrp_label(new_drops)}; the stock is moving in line with "
        "the clock."
    )


def phrase_rationale(
    *,
    action: PricingAction,
    previous_drops: int,
    new_drops: int,
    floor_drops: int,
    factors: PricingFactors,
    reasons: list[str],
    enabled: bool,
) -> str:
    """One sentence explaining a decision the engine has already made."""
    fallback = _deterministic(
        action=action,
        previous_drops=previous_drops,
        new_drops=new_drops,
        floor_drops=floor_drops,
        factors=factors,
    )
    if not enabled:
        return fallback

    try:
        from openai import OpenAI  # imported lazily so the dependency stays optional

        client = OpenAI()
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "claude-placeholder"),
            input=(
                "You are writing one sentence for a seller's audit log, explaining a "
                "surplus-food pricing decision that has already been made. Do not "
                "second-guess it and do not mention any price other than those given.\n"
                f"Action: {action}\n"
                f"Previous: {drops.to_xrp_label(previous_drops)}\n"
                f"New: {drops.to_xrp_label(new_drops)}\n"
                f"Floor: {drops.to_xrp_label(floor_drops)}\n"
                f"Reasons: {'; '.join(reasons)}"
            ),
            max_output_tokens=90,
        )
        text = (response.output_text or "").strip()
        return text or fallback
    except Exception as error:  # noqa: BLE001 - a narration failure must never stop a sale
        log.warning("rationale model unavailable, using deterministic phrasing: %s", error)
        return fallback
