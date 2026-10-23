import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.core.seeds import seed_demo_data
from app.services.scheduler import check_and_close_expired_auctions




def test_forced_close_cap_and_skip(client):
    """AC-22, AC-23, AC-24: Forced close cap and skip logging."""
    now = datetime.now(timezone.utc)
    # RFQ close time is 18:28, forced is 18:30, Y=5
    rfq_payload = {
        "reference_id": "RFQ-CAP-TEST",
        "name": "Forced Cap RFQ",
        "currency": "USD",
        "bid_start_time": (now - timedelta(minutes=10)).isoformat(),
        "original_close_time": (now + timedelta(minutes=3)).isoformat(),
        "forced_close_time": (now + timedelta(minutes=5)).isoformat(),  # only 5 mins total!
        "pickup_date": (now + timedelta(days=2)).isoformat(),
        "british_auction_enabled": True,
        "trigger_window_minutes": 10,
        "extension_minutes": 5,  # 3 + 5 = 8 mins, but capped at 5 mins!
        "extension_trigger": "BID_RECEIVED",
    }
    create_res = client.post("/api/v1/rfqs", json=rfq_payload, headers={"X-User-Id": "1"})
    rfq_id = create_res.json()["id"]

    # 1. First bid inside window extends to 5m (capped at forced)
    bid_1 = {
        "freight_charges": "800.00",
        "origin_charges": "50.00",
        "destination_charges": "50.00",
        "transit_time_days": 1,
        "quote_valid_until": (now + timedelta(days=5)).isoformat(),
    }
    res_b1 = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid_1, headers={"X-User-Id": "3"})
    assert res_b1.status_code == 201
    assert res_b1.json()["auction_extended"] is True

    # Check detail: current_close_time now equals forced_close_time
    detail_1 = client.get(f"/api/v1/rfqs/{rfq_id}", headers={"X-User-Id": "1"}).json()
    assert detail_1["current_close_time"] == detail_1["forced_close_time"]

    # 2. Second bid (AC-23): already at forced cap -> bid accepted, but extension skipped
    bid_2 = {
        "freight_charges": "700.00",
        "origin_charges": "50.00",
        "destination_charges": "50.00",
        "transit_time_days": 1,
        "quote_valid_until": (now + timedelta(days=5)).isoformat(),
    }
    res_b2 = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid_2, headers={"X-User-Id": "4"})
    assert res_b2.status_code == 201
    assert res_b2.json()["auction_extended"] is False  # Cannot extend beyond cap

    detail_2 = client.get(f"/api/v1/rfqs/{rfq_id}", headers={"X-User-Id": "1"}).json()
    events = [l["event_type"] for l in detail_2["activity_logs"]]
    assert "EXTENSION_SKIPPED_FORCED_CAP" in events


def test_closure_and_scheduler_immutability(client):
    """AC-26, AC-31, AC-32: Closure evaluation, scheduler, and terminal status immutability."""
    now = datetime.now(timezone.utc)
    # RFQ started and already expired
    rfq_payload = {
        "reference_id": "RFQ-EXPIRED-TEST",
        "name": "Expired RFQ",
        "currency": "USD",
        "bid_start_time": (now - timedelta(hours=2)).isoformat(),
        "original_close_time": (now - timedelta(minutes=10)).isoformat(),
        "forced_close_time": (now + timedelta(hours=1)).isoformat(),
        "pickup_date": (now + timedelta(days=1)).isoformat(),
        "british_auction_enabled": True,
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "extension_trigger": "BID_RECEIVED",
    }
    create_res = client.post("/api/v1/rfqs", json=rfq_payload, headers={"X-User-Id": "1"})
    rfq_id = create_res.json()["id"]

    # 1. Listing should report Closed immediately (lazy check)
    listing = client.get("/api/v1/rfqs", headers={"X-User-Id": "1"}).json()
    target = [r for r in listing if r["id"] == rfq_id][0]
    assert target["status"] == "CLOSED"

    # 2. Activity logs has AUCTION_CLOSED
    detail = client.get(f"/api/v1/rfqs/{rfq_id}", headers={"X-User-Id": "1"}).json()
    events = [l["event_type"] for l in detail["activity_logs"]]
    assert "AUCTION_CLOSED" in events
    assert events.count("AUCTION_CLOSED") == 1  # exactly one event!

    # 3. Any bid attempt on closed auction -> 409 AUCTION_NOT_ACTIVE (AC-8)
    bid = {
        "freight_charges": "500.00",
        "origin_charges": "50.00",
        "destination_charges": "50.00",
        "transit_time_days": 1,
        "quote_valid_until": (now + timedelta(days=5)).isoformat(),
    }
    reject_res = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid, headers={"X-User-Id": "3"})
    assert reject_res.status_code == 409
