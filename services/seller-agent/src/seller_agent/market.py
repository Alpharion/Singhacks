"""A simulated buyer population, so the pricing loop has something to push against.

Without this the agent reprices into a vacuum: nothing ever buys, so the price
walks down to the floor and the demo shows a decay curve rather than the thing
that matters, which is the feedback loop. Cheaper stock attracts buyers, buyers
consume inventory, and inventory selling faster than the clock is what stops the
agent conceding.

This is a *simulation*, and the listing says so (`simulatedMarket`) so the UI can
label it. The real signal is Person 3's marketplace: a buyer agent discovering an
offer raises an enquiry, and a settled x402 reservation is a sale. This class
exists to stand in for those two calls while the agents run separately, and it is
switched off by pointing the agent at the real thing.

Each listing seeds its own generator from its id, so a listing replays the same
way twice - a demo that reruns differently every time is impossible to narrate.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

#: Chance per tick that anyone looks at all, before price is considered.
#:
#: Tuned so a mid-priced listing sees a buyer every few ticks. Lower values are
#: arguably more realistic for one bakery, but they leave minute-long silences
#: in the middle of the run where the agent is visibly working and nothing is
#: happening, which reads as a stall rather than as a market.
BASE_INTEREST = 0.75
#: Largest share of the original quantity one buyer will take.
MAX_LOT_SHARE = 0.34
#: Below this attractiveness nobody bites, however long they have.
INTEREST_FLOOR = 0.08


@dataclass(frozen=True)
class Trade:
    """What the market did this tick."""

    enquiries: int
    units: int


class SimulatedMarket:
    """Buyers who care about price, and care more as the deadline nears.

    Attractiveness is how far the price has fallen through the band the seller
    allowed. At the opening ask almost nobody bites; near the floor most do.
    Lateness adds a little urgency of its own - a caterer who still needs food
    at eight o'clock is less fussy than one shopping at four.
    """

    def __init__(self, listing_id: str, *, enabled: bool) -> None:
        self.enabled = enabled
        self._random = random.Random(listing_id)

    def tick(
        self,
        *,
        position: float,
        elapsed: float,
        quantity_total: int,
        quantity_remaining: int,
    ) -> Trade:
        """`position` is 1 at the opening ask and 0 at the floor."""
        if not self.enabled or quantity_remaining <= 0:
            return Trade(enquiries=0, units=0)

        # Falling through the band is what draws buyers; urgency adds a little.
        attractiveness = max(INTEREST_FLOOR, (1.0 - position) * 0.85 + elapsed * 0.15)

        if self._random.random() > BASE_INTEREST * attractiveness:
            return Trade(enquiries=0, units=0)

        # Someone is interested. How much they take scales with how good the
        # price looks to them.
        lot_ceiling = max(1, int(quantity_total * MAX_LOT_SHARE * attractiveness))
        units = min(quantity_remaining, self._random.randint(1, lot_ceiling))

        return Trade(enquiries=1, units=units)
