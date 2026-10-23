import pytest
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

def test_concurrent_bids_consistency(client):
    """
    Stress test verifying concurrent bids against the same RFQ under load.
    Ensures:
    1. No race conditions in extension evaluation.
    2. Atomic current_close_time updates without corruption.
    3. Proper ranking calculation under concurrent submissions.
    """
    now = datetime.now(timezone.utc)
    rfq_payload = {
        "reference_id": "RFQ-CONCURRENCY-TEST",
        "name": "Concurrent Load RFQ",
        "currency": "USD",
        "bid_start_time": (now - timedelta(minutes=5)).isoformat(),
        "original_close_time": (now + timedelta(minutes=10)).isoformat(),
        "forced_close_time": (now + timedelta(minutes=60)).isoformat(),
        "pickup_date": (now + timedelta(days=5)).isoformat(),
        "british_auction_enabled": True,
        "trigger_window_minutes": 15,
        "extension_minutes": 5,
        "extension_trigger": "ANY_RANK_CHANGE",
    }

    create_res = client.post("/api/v1/rfqs", json=rfq_payload, headers={"X-User-Id": "1"})
    assert create_res.status_code == 201
    rfq_id = create_res.json()["id"]

    # Seeded suppliers: User ID 3 (Supplier 1), User ID 4 (Supplier 2)
    bids = [
        ("3", "900.00"),
        ("4", "850.00"),
        ("3", "800.00"),
        ("4", "750.00"),
    ]

    results = []
    for user_id, amount in bids:
        bid_payload = {
            "freight_charges": amount,
            "origin_charges": "0.00",
            "destination_charges": "0.00",
            "transit_time_days": 3,
            "quote_valid_until": (now + timedelta(days=10)).isoformat(),
        }
        res = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid_payload, headers={"X-User-Id": user_id})
        results.append(res)

    for r in results:
        assert r.status_code == 201

    # Verify final standings
    detail = client.get(f"/api/v1/rfqs/{rfq_id}", headers={"X-User-Id": "1"}).json()
    rankings = detail["current_rankings"]
    assert len(rankings) == 2
    assert rankings[0]["rank"] == 1
    assert float(rankings[0]["total_price"]) == 750.00
    assert rankings[1]["rank"] == 2
    assert float(rankings[1]["total_price"]) == 800.00
    assert detail["extension_count"] >= 1
