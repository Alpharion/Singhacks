"""The HTTP surface, and the parser's refusal to guess."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from seller_agent.drops import from_xrp
from seller_agent.main import app
from seller_agent.parsing import ParseError, build_goal

LISTING = (
    "Sell 60 vegetarian bakery meal boxes, collection by 9 PM, "
    "asking 2 XRP each but no less than 1.20 XRP."
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestParsing:
    def test_reads_the_whole_sentence(self):
        goal = build_goal(seller_id="seller_bakery_001", request_text=LISTING)
        assert goal.quantity == 60
        assert goal.dietary_tags == ["vegetarian"]
        assert goal.floor_unit_price_drops == str(from_xrp("1.20"))
        assert goal.opening_unit_price_drops == str(from_xrp("2"))

    def test_refuses_a_listing_with_no_floor(self):
        # Inventing a floor could sell a seller's food under cost.
        with pytest.raises(ParseError, match="floor price"):
            build_goal(
                seller_id="seller_bakery_001",
                request_text="Sell 60 vegetarian meal boxes, collection by 9 PM.",
            )

    def test_refuses_a_listing_with_no_quantity(self):
        with pytest.raises(ParseError, match="how many"):
            build_goal(
                seller_id="seller_bakery_001",
                request_text="Sell bakery boxes by 9 PM, no less than 1.20 XRP.",
            )

    def test_refuses_a_listing_with_no_deadline(self):
        with pytest.raises(ParseError, match="deadline"):
            build_goal(
                seller_id="seller_bakery_001",
                request_text="Sell 60 meal boxes, no less than 1.20 XRP each.",
            )

    def test_refuses_an_opening_below_the_floor(self):
        with pytest.raises(ParseError, match="below the floor"):
            build_goal(
                seller_id="seller_bakery_001",
                request_text=(
                    "Sell 60 meal boxes by 9 PM, asking 1 XRP each, no less than 1.20 XRP."
                ),
            )

    def test_opens_above_the_floor_when_no_ask_is_stated(self):
        goal = build_goal(
            seller_id="seller_bakery_001",
            request_text="Sell 60 meal boxes, collection by 9 PM, no less than 1.20 XRP each.",
        )
        # An agent that opens at the floor has been delegated nothing.
        assert int(goal.opening_unit_price_drops) > int(goal.floor_unit_price_drops)


class TestApi:
    def test_creating_a_listing_starts_the_agent(self, client):
        response = client.post(
            "/api/seller/listings",
            json={"sellerId": "seller_bakery_001", "requestText": LISTING},
            headers={"Idempotency-Key": "idem:seller:test:v1"},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] in ("listed", "repricing")
        assert body["quantityRemaining"] == 60
        assert body["unitPriceDrops"] == str(from_xrp("2"))
        assert body["goal"]["floorUnitPriceDrops"] == str(from_xrp("1.20"))
        assert [event["eventType"] for event in body["events"]][:2] == [
            "listing_parsed",
            "listing_published",
        ]

    def test_the_same_idempotency_key_returns_the_same_listing(self, client):
        payload = {"sellerId": "seller_bakery_001", "requestText": LISTING}
        headers = {"Idempotency-Key": "idem:seller:repeat:v1"}
        first = client.post("/api/seller/listings", json=payload, headers=headers).json()
        second = client.post("/api/seller/listings", json=payload, headers=headers).json()
        assert first["listingId"] == second["listingId"]

    def test_an_unparseable_listing_is_a_contract_error(self, client):
        response = client.post(
            "/api/seller/listings",
            json={"sellerId": "seller_bakery_001", "requestText": "Sell some bread."},
        )
        assert response.status_code == 422
        assert response.json()["error"] == "invalid_request"

    def test_demand_is_recorded_and_explained(self, client):
        created = client.post(
            "/api/seller/listings",
            json={"sellerId": "seller_bakery_001", "requestText": LISTING},
        ).json()

        response = client.post(
            f"/api/seller/listings/{created['listingId']}/demand",
            json={"quantity": 20, "source": "buyer_agent"},
        )
        assert response.status_code == 200
        body = response.json()
        assert any(event["eventType"] == "demand_observed" for event in body["events"])
        assert body["decisions"], "a demand signal should produce an explained decision"

    def test_a_sale_reduces_stock_and_records_uplift(self, client):
        created = client.post(
            "/api/seller/listings",
            json={"sellerId": "seller_bakery_001", "requestText": LISTING},
        ).json()

        body = client.post(
            f"/api/seller/listings/{created['listingId']}/sale",
            json={"quantity": 10},
        ).json()

        assert body["quantityRemaining"] == 50
        assert body["revenue"]["unitsSold"] == 10
        # Sold at the opening ask of 2 XRP against a 1.20 floor.
        assert body["revenue"]["grossDrops"] == str(from_xrp("20"))
        assert body["revenue"]["floorValueDrops"] == str(from_xrp("12"))
        assert body["revenue"]["upliftDrops"] == str(from_xrp("8"))

    def test_selling_everything_clears_the_listing(self, client):
        created = client.post(
            "/api/seller/listings",
            json={"sellerId": "seller_bakery_001", "requestText": LISTING},
        ).json()

        body = client.post(
            f"/api/seller/listings/{created['listingId']}/sale",
            json={"quantity": 60},
        ).json()

        assert body["status"] == "cleared"
        assert body["quantityRemaining"] == 0
        assert any(event["eventType"] == "listing_cleared" for event in body["events"])

    def test_unknown_listing_is_a_404(self, client):
        response = client.get("/api/seller/listings/listing_missing")
        assert response.status_code == 404
        assert response.json()["error"] == "not_found"

    def test_every_decision_respects_the_floor(self, client):
        created = client.post(
            "/api/seller/listings",
            json={"sellerId": "seller_bakery_001", "requestText": LISTING},
        ).json()
        listing_id = created["listingId"]

        for _ in range(5):
            client.post(
                f"/api/seller/listings/{listing_id}/demand", json={"quantity": 5}
            )

        body = client.get(f"/api/seller/listings/{listing_id}").json()
        floor = int(body["goal"]["floorUnitPriceDrops"])
        for decision in body["decisions"]:
            assert int(decision["unitPriceDrops"]) >= floor
        assert int(body["unitPriceDrops"]) >= floor


class TestSafety:
    def test_the_service_refuses_to_start_holding_a_wallet_seed(self, monkeypatch):
        from seller_agent import config

        monkeypatch.setenv("XRPL_SELLER_SEED", "sEdSomethingSecret")
        with pytest.raises(RuntimeError, match="never see a wallet seed"):
            config.assert_no_seed_access()

    def test_no_module_mentions_signing(self):
        import pathlib

        source_dir = pathlib.Path(__file__).resolve().parents[1] / "src" / "seller_agent"
        for path in source_dir.glob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            assert "wallet.sign" not in text
            assert "submit_and_wait" not in text
