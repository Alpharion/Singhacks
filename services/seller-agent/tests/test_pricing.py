"""The pricing engine's guarantees.

The floor tests are the important ones. A seller delegates pricing on the
promise that one number is inviolable, so these sweep the whole input space
rather than checking a few hand-picked cases.
"""

from __future__ import annotations

import pytest

from seller_agent.drops import from_xrp
from seller_agent.pricing import quote

FLOOR = from_xrp("1.20")
OPENING = from_xrp("2.00")


def price(**overrides) -> int:
    kwargs = dict(
        floor_drops=FLOOR,
        opening_drops=OPENING,
        current_drops=OPENING,
        elapsed_ratio=0.0,
        quantity_total=60,
        quantity_remaining=60,
        enquiries=0,
    )
    kwargs.update(overrides)
    return quote(**kwargs).unit_price_drops


class TestFloorIsAbsolute:
    def test_never_goes_under_the_floor_anywhere_in_the_input_space(self):
        for elapsed in [i / 20 for i in range(0, 21)]:
            for remaining in range(0, 61, 5):
                for enquiries in range(0, 10):
                    result = quote(
                        floor_drops=FLOOR,
                        opening_drops=OPENING,
                        current_drops=FLOOR,
                        elapsed_ratio=elapsed,
                        quantity_total=60,
                        quantity_remaining=remaining,
                        enquiries=enquiries,
                    )
                    assert result.unit_price_drops >= FLOOR

    def test_holds_the_floor_even_past_the_deadline(self):
        assert price(elapsed_ratio=2.0, current_drops=FLOOR) == FLOOR

    def test_never_exceeds_the_opening_ask(self):
        # Strong demand and a fast sell-through must not invent a price above
        # what the seller advertised.
        assert price(elapsed_ratio=0.0, quantity_remaining=1, enquiries=99) <= OPENING

    def test_a_floor_equal_to_the_opening_leaves_one_price(self):
        result = quote(
            floor_drops=FLOOR,
            opening_drops=FLOOR,
            current_drops=FLOOR,
            elapsed_ratio=0.5,
            quantity_total=10,
            quantity_remaining=10,
            enquiries=0,
        )
        assert result.unit_price_drops == FLOOR

    def test_rejects_an_opening_below_the_floor(self):
        with pytest.raises(ValueError):
            quote(
                floor_drops=OPENING,
                opening_drops=FLOOR,
                current_drops=FLOOR,
                elapsed_ratio=0.0,
                quantity_total=10,
                quantity_remaining=10,
                enquiries=0,
            )


class TestClearsBeforeExpiry:
    def test_price_falls_as_the_deadline_approaches(self):
        early = price(elapsed_ratio=0.1)
        middle = price(elapsed_ratio=0.5)
        late = price(elapsed_ratio=0.9)
        assert early > middle > late

    def test_reaches_the_floor_by_the_deadline_when_nothing_has_sold(self):
        assert price(elapsed_ratio=1.0, quantity_remaining=60) == FLOOR

    def test_unsold_stock_discounts_harder_than_stock_that_is_moving(self):
        stalled = price(elapsed_ratio=0.6, quantity_remaining=60)
        moving = price(elapsed_ratio=0.6, quantity_remaining=10)
        assert moving > stalled


class TestDemand:
    def test_interest_holds_the_price_up(self):
        quiet = price(elapsed_ratio=0.5, enquiries=0)
        busy = price(elapsed_ratio=0.5, enquiries=6)
        assert busy > quiet

    def test_demand_cannot_push_past_the_opening_ask(self):
        assert price(elapsed_ratio=0.0, enquiries=1000) <= OPENING


class TestDecisionShape:
    def test_reports_reducing_when_the_price_drops(self):
        result = quote(
            floor_drops=FLOOR,
            opening_drops=OPENING,
            current_drops=OPENING,
            elapsed_ratio=0.7,
            quantity_total=60,
            quantity_remaining=60,
            enquiries=0,
        )
        assert result.action == "reduce"
        assert result.unit_price_drops < OPENING
        assert result.reasons

    def test_reports_the_floor_once_it_is_reached(self):
        result = quote(
            floor_drops=FLOOR,
            opening_drops=OPENING,
            current_drops=FLOOR,
            elapsed_ratio=1.0,
            quantity_total=60,
            quantity_remaining=60,
            enquiries=0,
        )
        assert result.action == "floor"
        assert any("floor" in reason.lower() for reason in result.reasons)

    def test_factors_are_recorded_for_audit(self):
        result = quote(
            floor_drops=FLOOR,
            opening_drops=OPENING,
            current_drops=OPENING,
            elapsed_ratio=0.5,
            quantity_total=60,
            quantity_remaining=30,
            enquiries=2,
        )
        assert result.factors.sell_through == pytest.approx(0.5)
        assert result.factors.time_elapsed == pytest.approx(0.5)
        assert result.factors.enquiries == 2
        assert result.factors.remaining == 30
