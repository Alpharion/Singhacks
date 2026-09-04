from __future__ import annotations


def test_list_delivery_quotes_matches_pickup_sellers(client):
    payload = {
        "goalId": "goal_demo_001",
        "pickups": [
            {
                "sellerId": "seller_bakery_001",
                "offerId": "offer_bakery_001",
                "quantity": 60,
                "location": {"zone": "Queenstown"},
            }
        ],
        "destination": {"zone": "Queenstown"},
        "deliveryDeadline": "2099-01-01T00:00:00Z",
    }
    response = client.post("/api/delivery/quotes", json=payload)
    assert response.status_code == 200
    body = response.json()
    ids = {q["quoteId"] for q in body["quotes"]}
    assert ids == {"quote_fast_001", "quote_economy_001"}


def test_list_delivery_quotes_excludes_unrelated_sellers(client):
    payload = {
        "goalId": "goal_demo_002",
        "pickups": [
            {
                "sellerId": "seller_grill_001",
                "offerId": "offer_grill_001",
                "quantity": 10,
                "location": {"zone": "Outram"},
            }
        ],
        "destination": {"zone": "Outram"},
        "deliveryDeadline": "2099-01-01T00:00:00Z",
    }
    response = client.post("/api/delivery/quotes", json=payload)
    assert response.status_code == 200
    assert response.json()["quotes"] == []


def test_list_delivery_quotes_rejects_missing_fields(client):
    response = client.post("/api/delivery/quotes", json={"goalId": "goal_demo_003"})
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
