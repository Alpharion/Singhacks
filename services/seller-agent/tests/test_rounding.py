"""Prices must be readable, and readable must not mean "below the floor"."""

from __future__ import annotations

from seller_agent.drops import from_xrp
from seller_agent.pricing import PRICE_INCREMENT_DROPS, quote


def test_every_price_lands_on_a_readable_increment():
    floor = from_xrp("1.20")
    opening = from_xrp("2.00")
    for elapsed in [i / 40 for i in range(0, 41)]:
        result = quote(
            floor_drops=floor,
            opening_drops=opening,
            current_drops=opening,
            elapsed_ratio=elapsed,
            quantity_total=60,
            quantity_remaining=60,
            enquiries=0,
        )
        assert result.unit_price_drops % PRICE_INCREMENT_DROPS == 0


def test_rounding_never_dips_under_an_awkward_floor():
    # A floor that is not a multiple of the increment is exactly where naive
    # rounding would shave a fraction off the seller's minimum.
    floor = from_xrp("1.205")
    opening = from_xrp("2.005")
    for elapsed in [i / 40 for i in range(0, 45)]:
        result = quote(
            floor_drops=floor,
            opening_drops=opening,
            current_drops=floor,
            elapsed_ratio=elapsed,
            quantity_total=10,
            quantity_remaining=10,
            enquiries=0,
        )
        assert result.unit_price_drops >= floor


def test_rounding_never_exceeds_an_awkward_opening_ask():
    floor = from_xrp("1.205")
    opening = from_xrp("2.005")
    result = quote(
        floor_drops=floor,
        opening_drops=opening,
        current_drops=floor,
        elapsed_ratio=0.0,
        quantity_total=10,
        quantity_remaining=1,
        enquiries=50,
    )
    assert result.unit_price_drops <= opening
