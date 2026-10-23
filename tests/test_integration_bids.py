import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models.models import User, Supplier, RFQ, CurrentBid, ActivityLog
from app.core.seeds import seed_demo_data




# -------------------------------------------------------------
# Acceptance Criteria Tests
# -------------------------------------------------------------

def test_ac_1_and_ac_2_validation(client):
    # AC-1: forced_close_time <= original_close_time -> 422
    now = datetime.now(timezone.utc)
    payload = {
        "reference_id": "RFQ-TEST-001",
        "name": "Invalid Config RFQ",
        "currency": "USD",
        "bid_start_time": now.isoformat(),
        "original_close_time": (now + timedelta(hours=1)).isoformat(),
        "forced_close_time": (now + timedelta(minutes=30)).isoformat(),  # Earlier than original!
        "pickup_date": (now + timedelta(days=2)).isoformat(),
        "british_auction_enabled": True,
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "extension_trigger": "BID_RECEIVED",
    }
    response = client.post("/api/v1/rfqs", json=payload, headers={"X-User-Id": "1"})
    assert response.status_code == 422


def test_ac_38_and_ac_39_auth_and_roles(client):
    now = datetime.now(timezone.utc)
    payload = {
        "reference_id": "RFQ-TEST-AUTH",
        "name": "Auth Test RFQ",
        "currency": "USD",
        "bid_start_time": now.isoformat(),
        "original_close_time": (now + timedelta(hours=1)).isoformat(),
        "forced_close_time": (now + timedelta(hours=2)).isoformat(),
        "pickup_date": (now + timedelta(days=2)).isoformat(),
        "british_auction_enabled": True,
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "extension_trigger": "BID_RECEIVED",
    }
    # AC-38: No auth header -> 401
    res_no_auth = client.post("/api/v1/rfqs", json=payload)
    assert res_no_auth.status_code == 401

    # AC-39: Supplier user (id=3) tries to create RFQ -> 403
    res_supplier_create = client.post("/api/v1/rfqs", json=payload, headers={"X-User-Id": "3"})
    assert res_supplier_create.status_code == 403


def test_bidding_flow_and_revisions(client):
    now = datetime.now(timezone.utc)
    # 1. Create active RFQ as Buyer (User 1)
    rfq_payload = {
        "reference_id": "RFQ-LANE-NYC-CHI",
        "name": "NYC to Chicago Reefer Freight",
        "currency": "USD",
        "bid_start_time": (now - timedelta(minutes=10)).isoformat(),
        "original_close_time": (now + timedelta(minutes=30)).isoformat(),
        "forced_close_time": (now + timedelta(hours=1)).isoformat(),
        "pickup_date": (now + timedelta(days=3)).isoformat(),
        "british_auction_enabled": True,
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "extension_trigger": "L1_RANK_CHANGE",
    }
    create_res = client.post("/api/v1/rfqs", json=rfq_payload, headers={"X-User-Id": "1"})
    assert create_res.status_code == 201
    rfq_id = create_res.json()["id"]

    # 2. Supplier 1 (DHL, User 3) bids $1200
    bid_1 = {
        "freight_charges": "1000.00",
        "origin_charges": "100.00",
        "destination_charges": "100.00",
        "transit_time_days": 2,
        "quote_valid_until": (now + timedelta(days=10)).isoformat(),
    }
    res_b1 = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid_1, headers={"X-User-Id": "3"})
    assert res_b1.status_code == 201
    b1_data = res_b1.json()
    assert b1_data["total_price"] == "1200.00"
    assert b1_data["rank"] == 1  # L1

    # 3. Supplier 2 (FedEx, User 4) bids $1100 -> takes L1
    bid_2 = {
        "freight_charges": "900.00",
        "origin_charges": "100.00",
        "destination_charges": "100.00",
        "transit_time_days": 2,
        "quote_valid_until": (now + timedelta(days=10)).isoformat(),
    }
    res_b2 = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid_2, headers={"X-User-Id": "4"})
    assert res_b2.status_code == 201
    assert res_b2.json()["rank"] == 1

    # Check that DHL (Supplier 1) is now rank L2 on RFQ details
    detail_res = client.get(f"/api/v1/rfqs/{rfq_id}", headers={"X-User-Id": "1"})
    assert detail_res.status_code == 200
    rankings = detail_res.json()["current_rankings"]
    assert len(rankings) == 2
    assert rankings[0]["carrier_name"] == "FedEx Freight Services"
    assert rankings[1]["carrier_name"] == "DHL Global Forwarding"

    # 4. AC-10: Supplier 1 (DHL) attempts to submit equal or higher bid ($1200 or $1250) -> 409 BID_NOT_LOWER
    bid_higher = {
        "freight_charges": "1050.00",
        "origin_charges": "100.00",
        "destination_charges": "100.00",
        "transit_time_days": 2,
        "quote_valid_until": (now + timedelta(days=10)).isoformat(),
    }
    res_reject = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid_higher, headers={"X-User-Id": "3"})
    assert res_reject.status_code == 409

    # 5. Supplier 1 (DHL) successfully lowers bid to $1050 -> passes FedEx to regain L1!
    bid_lower = {
        "freight_charges": "850.00",
        "origin_charges": "100.00",
        "destination_charges": "100.00",
        "transit_time_days": 2,
        "quote_valid_until": (now + timedelta(days=10)).isoformat(),
    }
    res_regain = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid_lower, headers={"X-User-Id": "3"})
    assert res_regain.status_code == 201
    assert res_regain.json()["rank"] == 1


def test_extension_in_trigger_window(client):
    now = datetime.now(timezone.utc)
    # Create RFQ ending in 5 minutes with 10-minute trigger window (already inside window!)
    rfq_payload = {
        "reference_id": "RFQ-WINDOW-TEST",
        "name": "Late Extension RFQ",
        "currency": "USD",
        "bid_start_time": (now - timedelta(minutes=10)).isoformat(),
        "original_close_time": (now + timedelta(minutes=5)).isoformat(),
        "forced_close_time": (now + timedelta(minutes=30)).isoformat(),
        "pickup_date": (now + timedelta(days=2)).isoformat(),
        "british_auction_enabled": True,
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "extension_trigger": "BID_RECEIVED",
    }
    create_res = client.post("/api/v1/rfqs", json=rfq_payload, headers={"X-User-Id": "1"})
    rfq_id = create_res.json()["id"]

    # Submit bid as Supplier (User 3)
    bid = {
        "freight_charges": "1000.00",
        "origin_charges": "50.00",
        "destination_charges": "50.00",
        "transit_time_days": 1,
        "quote_valid_until": (now + timedelta(days=5)).isoformat(),
    }
    res = client.post(f"/api/v1/rfqs/{rfq_id}/bids", json=bid, headers={"X-User-Id": "3"})
    assert res.status_code == 201
    data = res.json()
    assert data["auction_extended"] is True

    # Details check: extension_count == 1, activity_logs has TIME_EXTENDED
    detail = client.get(f"/api/v1/rfqs/{rfq_id}", headers={"X-User-Id": "1"}).json()
    assert detail["extension_count"] == 1
    events = [l["event_type"] for l in detail["activity_logs"]]
    assert "TIME_EXTENDED" in events
