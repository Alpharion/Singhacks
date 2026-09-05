from __future__ import annotations


def test_list_food_offers_returns_seeded_offers(client):
    response = client.get("/api/offers")
    assert response.status_code == 200
    body = response.json()
    assert {o["offerId"] for o in body["offers"]} == {
        "offer_bakery_001",
        "offer_hotel_001",
        "offer_grill_001",
    }
    assert "generatedAt" in body


def test_list_food_offers_filters_by_dietary_tag(client):
    response = client.get("/api/offers", params={"dietaryTag": "vegetarian"})
    assert response.status_code == 200
    ids = {o["offerId"] for o in response.json()["offers"]}
    assert ids == {"offer_bakery_001", "offer_hotel_001"}


def test_list_food_offers_filters_by_min_quantity(client):
    response = client.get("/api/offers", params={"minQuantity": 90})
    assert response.status_code == 200
    ids = {o["offerId"] for o in response.json()["offers"]}
    assert ids == {"offer_grill_001"}


def test_list_food_offers_rejects_invalid_dietary_tag(client):
    response = client.get("/api/offers", params={"dietaryTag": "not_a_real_tag"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_request"
    assert body["retryable"] is False
