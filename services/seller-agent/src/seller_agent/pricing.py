"""The pricing engine.

Deterministic, like the buyer's optimizer and for the same reason: this is the
part that decides money, so the same inputs must always produce the same price
and a language model must never be in the loop. `llm.py` may phrase the
resulting decision; it cannot change it.

The objective is to clear the inventory before it expires. Unsold surplus food
is a total loss - it is thrown away - so as the collection deadline approaches
the agent trades margin for certainty and walks the price down toward the
floor. Two things push back: selling faster than the clock (there is no need to
discount stock that is already moving) and live buyer interest.

The floor is absolute. It is applied last, as a hard clamp, and asserted after
the fact. A seller delegates pricing precisely because they have stated a number
they will not go under.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import PricingAction, PricingFactors

#: How strongly being ahead of or behind schedule moves the price.
#:
#: Kept small on purpose. `pace` is sell-through minus elapsed time, so when
#: nothing has sold it is simply the negative of elapsed time and a large weight
#: would count the clock twice - collapsing to the floor around 60% of the way
#: through the window, with hours of selling time left and nothing in reserve.
PACE_WEIGHT = 0.15
#: How strongly recent buyer interest holds the price up.
DEMAND_WEIGHT = 0.35
#: Enquiries at which demand is considered saturated.
DEMAND_SATURATION = 6.0
#: Moves smaller than this fraction of the band are not worth making.
HOLD_BAND = 0.02
#: Prices are quoted to the nearest hundredth of an XRP. Nobody sells bread at
#: 1.971296 XRP, and a price a person cannot read back is not a price.
PRICE_INCREMENT_DROPS = 10_000


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class PriceQuote:
    unit_price_drops: int
    action: PricingAction
    factors: PricingFactors
    reasons: list[str]


def compute_factors(
    *,
    elapsed_ratio: float,
    quantity_total: int,
    quantity_remaining: int,
    enquiries: int,
) -> PricingFactors:
    sold = quantity_total - quantity_remaining
    sell_through = clamp(sold / quantity_total) if quantity_total else 1.0
    time_elapsed = clamp(elapsed_ratio)
    return PricingFactors(
        time_elapsed=round(time_elapsed, 4),
        sell_through=round(sell_through, 4),
        pace=round(sell_through - time_elapsed, 4),
        demand=round(clamp(enquiries / DEMAND_SATURATION), 4),
        enquiries=enquiries,
        remaining=quantity_remaining,
    )


def _reasons(factors: PricingFactors, action: PricingAction, floor_reached: bool) -> list[str]:
    reasons: list[str] = []

    if factors.time_elapsed >= 0.85:
        reasons.append(
            f"{round((1 - factors.time_elapsed) * 100)}% of the collection window is left; "
            "unsold stock is written off at the deadline."
        )
    elif factors.time_elapsed >= 0.4:
        reasons.append(
            f"{round(factors.time_elapsed * 100)}% of the collection window has passed."
        )

    if factors.pace <= -0.15:
        reasons.append(
            f"Sold {round(factors.sell_through * 100)}% with "
            f"{round(factors.time_elapsed * 100)}% of the time gone, so the stock is "
            "moving slower than the clock."
        )
    elif factors.pace >= 0.15:
        reasons.append(
            f"Sold {round(factors.sell_through * 100)}% with only "
            f"{round(factors.time_elapsed * 100)}% of the time gone, so there is no need "
            "to discount."
        )

    if factors.enquiries > 0:
        reasons.append(
            f"{factors.enquiries} buyer "
            f"{'enquiry' if factors.enquiries == 1 else 'enquiries'} since listing."
        )

    if floor_reached:
        reasons.append("Holding at the floor the seller set; the agent cannot go under it.")
    elif action == "hold":
        reasons.append("No move large enough to be worth making.")

    return reasons


def quote(
    *,
    floor_drops: int,
    opening_drops: int,
    current_drops: int,
    elapsed_ratio: float,
    quantity_total: int,
    quantity_remaining: int,
    enquiries: int,
) -> PriceQuote:
    """The price this listing should be asking right now.

    The price sits somewhere in the band between the floor and the opening ask.
    Position in that band starts at 1 (full ask) and is pulled down by elapsed
    time, then pushed back up by good pace and live demand.
    """
    if floor_drops <= 0:
        raise ValueError("floor price must be positive")
    if opening_drops < floor_drops:
        raise ValueError("opening price cannot be below the floor")

    factors = compute_factors(
        elapsed_ratio=elapsed_ratio,
        quantity_total=quantity_total,
        quantity_remaining=quantity_remaining,
        enquiries=enquiries,
    )

    band = opening_drops - floor_drops
    position = clamp(
        (1.0 - factors.time_elapsed) + factors.pace * PACE_WEIGHT + factors.demand * DEMAND_WEIGHT
    )

    target = floor_drops + int(round(band * position))

    # Quote to a readable increment before clamping, so rounding can never be
    # what pushes a price under the floor.
    target = int(round(target / PRICE_INCREMENT_DROPS)) * PRICE_INCREMENT_DROPS

    # The floor is absolute. Applied last so no earlier term can undercut it.
    target = max(floor_drops, min(target, opening_drops))

    # Ignore moves too small to mean anything, so the timeline reads as decisions
    # rather than noise.
    if band > 0 and abs(target - current_drops) < max(1, int(band * HOLD_BAND)):
        target = current_drops

    at_floor = target <= floor_drops
    if target < current_drops:
        action: PricingAction = "floor" if at_floor else "reduce"
    elif target > current_drops:
        action = "raise"
    else:
        action = "floor" if at_floor else "hold"

    assert target >= floor_drops, "pricing engine produced a price below the seller's floor"

    return PriceQuote(
        unit_price_drops=target,
        action=action,
        factors=factors,
        reasons=_reasons(factors, action, floor_reached=at_floor),
    )
