"""The simulated buyer population.

Its job is to give the pricing loop something to push against. These tests
assert the shape of that pressure, not exact draws: buyers must prefer a cheaper
price, must never take more than exists, and must replay identically for a given
listing so a demo can be narrated the same way twice.
"""

from __future__ import annotations

from seller_agent.market import SimulatedMarket


def total_units(position: float, *, listing_id: str = "listing_test", ticks: int = 400) -> int:
    market = SimulatedMarket(listing_id, enabled=True)
    sold = 0
    for _ in range(ticks):
        trade = market.tick(
            position=position, elapsed=0.5, quantity_total=60, quantity_remaining=60
        )
        sold += trade.units
    return sold


def test_a_disabled_market_never_trades():
    market = SimulatedMarket("listing_test", enabled=False)
    for _ in range(50):
        trade = market.tick(
            position=0.0, elapsed=1.0, quantity_total=60, quantity_remaining=60
        )
        assert trade == trade.__class__(enquiries=0, units=0)


def test_buyers_prefer_a_cheaper_price():
    # position 1 is the opening ask, 0 is the floor.
    assert total_units(0.0) > total_units(1.0)


def test_nothing_sells_once_the_stock_is_gone():
    market = SimulatedMarket("listing_test", enabled=True)
    for _ in range(50):
        trade = market.tick(
            position=0.0, elapsed=0.9, quantity_total=60, quantity_remaining=0
        )
        assert trade.units == 0


def test_a_buyer_never_takes_more_than_is_left():
    market = SimulatedMarket("listing_test", enabled=True)
    for _ in range(200):
        trade = market.tick(
            position=0.0, elapsed=0.9, quantity_total=60, quantity_remaining=3
        )
        assert trade.units <= 3


def test_a_listing_replays_the_same_way():
    # A demo that runs differently every time cannot be narrated.
    assert total_units(0.4, listing_id="listing_abc") == total_units(
        0.4, listing_id="listing_abc"
    )


def test_different_listings_differ():
    assert total_units(0.4, listing_id="listing_abc") != total_units(
        0.4, listing_id="listing_xyz"
    )
