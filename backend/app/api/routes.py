from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.core.auth import get_current_user, require_buyer, require_supplier
from app.models.models import User, Supplier, RFQ, Bid, CurrentBid, ActivityLog
from app.schemas.schemas import (
    RFQCreate,
    RFQListItem,
    RFQDetail,
    BidCreate,
    BidResponse,
    RankedBidItem,
    BidHistoryItem,
    ActivityLogItem,
    UserResponse,
)
from app.services.status_service import resolve_auction_status
from app.services.auction_service import submit_bid, close_auction, get_db_clock

router = APIRouter()


# -------------------------------------------------------------
# Demo Identity Switcher Endpoint
# -------------------------------------------------------------
@router.get("/users", response_model=List[UserResponse])
def list_demo_users(db: Session = Depends(get_db)):
    """List seeded demo users with role and carrier profile for the frontend user switcher."""
    users = db.query(User).all()
    results = []
    for u in users:
        carrier = u.supplier_profile.carrier_name if u.supplier_profile else None
        sup_id = u.supplier_profile.id if u.supplier_profile else None
        results.append(
            UserResponse(
                id=u.id,
                name=u.name,
                email=u.email,
                role=u.role,
                carrier_name=carrier,
                supplier_id=sup_id,
            )
        )
    return results


# -------------------------------------------------------------
# RFQ Endpoints
# -------------------------------------------------------------
@router.post("/rfqs", response_model=RFQDetail, status_code=status.HTTP_201_CREATED)
def create_rfq(
    payload: RFQCreate,
    buyer: User = Depends(require_buyer),
    db: Session = Depends(get_db),
):
    """
    Creates an RFQ with British Auction configuration.
    Restricted to Buyers. Initial current_close_time is set equal to original_close_time.
    """
    # Check reference_id uniqueness
    existing = db.query(RFQ).filter(RFQ.reference_id == payload.reference_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"RFQ with Reference ID '{payload.reference_id}' already exists",
        )

    t_now = get_db_clock(db)

    new_rfq = RFQ(
        reference_id=payload.reference_id,
        name=payload.name,
        created_by=buyer.id,
        currency=payload.currency,
        bid_start_time=payload.bid_start_time,
        original_close_time=payload.original_close_time,
        current_close_time=payload.original_close_time,  # Starts equal to original
        forced_close_time=payload.forced_close_time,
        pickup_date=payload.pickup_date,
        british_auction_enabled=payload.british_auction_enabled,
        trigger_window_minutes=payload.trigger_window_minutes,
        extension_minutes=payload.extension_minutes,
        extension_trigger=payload.extension_trigger,
        extension_count=0,
        created_at=t_now,
    )
    db.add(new_rfq)
    db.flush()

    # Log RFQ_CREATED
    config_summary = (
        f"British Auction Enabled (X={payload.trigger_window_minutes}m, Y={payload.extension_minutes}m, Trigger={payload.extension_trigger})"
        if payload.british_auction_enabled
        else "Standard RFQ (British Auction Disabled)"
    )
    create_log = ActivityLog(
        rfq_id=new_rfq.id,
        event_type="RFQ_CREATED",
        message=f"RFQ '{new_rfq.name}' created by {buyer.name}. {config_summary}",
        metadata_json={
            "created_by": buyer.name,
            "reference_id": new_rfq.reference_id,
            "british_auction_enabled": new_rfq.british_auction_enabled,
            "trigger_window_minutes": new_rfq.trigger_window_minutes,
            "extension_minutes": new_rfq.extension_minutes,
            "extension_trigger": new_rfq.extension_trigger,
        },
        created_at=t_now,
    )
    db.add(create_log)
    db.commit()
    db.refresh(new_rfq)

    computed_status = resolve_auction_status(new_rfq, t_now)

    return RFQDetail(
        id=new_rfq.id,
        reference_id=new_rfq.reference_id,
        name=new_rfq.name,
        currency=new_rfq.currency,
        bid_start_time=new_rfq.bid_start_time,
        original_close_time=new_rfq.original_close_time,
        current_close_time=new_rfq.current_close_time,
        forced_close_time=new_rfq.forced_close_time,
        pickup_date=new_rfq.pickup_date,
        british_auction_enabled=new_rfq.british_auction_enabled,
        trigger_window_minutes=new_rfq.trigger_window_minutes,
        extension_minutes=new_rfq.extension_minutes,
        extension_trigger=new_rfq.extension_trigger,
        status=computed_status,
        extension_count=new_rfq.extension_count,
        closed_at=new_rfq.closed_at,
        current_rankings=[],
        bid_history=[],
        activity_logs=[
            ActivityLogItem(
                id=create_log.id,
                event_type=create_log.event_type,
                message=create_log.message,
                metadata=create_log.metadata_json,
                created_at=create_log.created_at,
            )
        ],
    )


@router.get("/rfqs", response_model=List[RFQListItem])
def list_rfqs(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Auction Listing Page (PRD §5.3, HLD §3.3).
    Returns all RFQs with current lowest bid (L1), effective close time, and live status.
    Performs lazy closure if an RFQ deadline has elapsed.
    """
    t_now = get_db_clock(db)
    rfqs = db.query(RFQ).order_by(desc(RFQ.created_at)).all()
    results = []

    for rfq in rfqs:
        computed_status = resolve_auction_status(rfq, t_now)
        # Lazy closure check
        if computed_status in ("CLOSED", "FORCE_CLOSED") and rfq.terminal_status is None:
            close_auction(rfq.id, db, t_now)

        if status_filter and computed_status.upper() != status_filter.upper():
            continue

        # Lowest current bid
        l1_bid = (
            db.query(CurrentBid)
            .filter(CurrentBid.rfq_id == rfq.id)
            .order_by(CurrentBid.total_price.asc(), CurrentBid.accepted_at.asc(), CurrentBid.id.asc())
            .first()
        )

        total_bids = db.query(Bid).filter(Bid.rfq_id == rfq.id).count()

        results.append(
            RFQListItem(
                id=rfq.id,
                reference_id=rfq.reference_id,
                name=rfq.name,
                currency=rfq.currency,
                bid_start_time=rfq.bid_start_time,
                original_close_time=rfq.original_close_time,
                current_close_time=rfq.current_close_time,
                forced_close_time=rfq.forced_close_time,
                pickup_date=rfq.pickup_date,
                british_auction_enabled=rfq.british_auction_enabled,
                trigger_window_minutes=rfq.trigger_window_minutes,
                extension_minutes=rfq.extension_minutes,
                extension_trigger=rfq.extension_trigger,
                status=computed_status,
                extension_count=rfq.extension_count,
                current_lowest_bid=l1_bid.total_price if l1_bid else None,
                current_lowest_carrier=l1_bid.supplier.carrier_name if l1_bid else None,
                total_bids_count=total_bids,
            )
        )

    return results


@router.get("/rfqs/{id}", response_model=RFQDetail)
def get_rfq_details(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Auction Details Page (PRD §5.4).
    Displays current ranking, bid history (with superseded flag), and audit activity log.
    """
    t_now = get_db_clock(db)
    rfq = db.query(RFQ).filter(RFQ.id == id).first()
    if not rfq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")

    computed_status = resolve_auction_status(rfq, t_now)
    if computed_status in ("CLOSED", "FORCE_CLOSED") and rfq.terminal_status is None:
        close_auction(rfq.id, db, t_now)

    # 1. Current rankings
    current_bids = (
        db.query(CurrentBid)
        .filter(CurrentBid.rfq_id == rfq.id)
        .order_by(CurrentBid.total_price.asc(), CurrentBid.accepted_at.asc(), CurrentBid.id.asc())
        .all()
    )
    rankings = []
    active_bid_ids = set()
    for idx, cb in enumerate(current_bids):
        rankings.append(
            RankedBidItem(
                rank=idx + 1,
                supplier_id=cb.supplier_id,
                carrier_name=cb.supplier.carrier_name,
                bid_id=cb.bid_id,
                freight_charges=cb.freight_charges,
                origin_charges=cb.origin_charges,
                destination_charges=cb.destination_charges,
                total_price=cb.total_price,
                transit_time_days=cb.transit_time_days,
                quote_valid_until=cb.quote_valid_until,
                accepted_at=cb.accepted_at,
            )
        )
        active_bid_ids.add(cb.bid_id)

    # 2. Bid history
    all_bids = (
        db.query(Bid)
        .filter(Bid.rfq_id == rfq.id)
        .order_by(desc(Bid.accepted_at), desc(Bid.id))
        .all()
    )
    history = [
        BidHistoryItem(
            id=b.id,
            supplier_id=b.supplier_id,
            carrier_name=b.supplier.carrier_name,
            freight_charges=b.freight_charges,
            origin_charges=b.origin_charges,
            destination_charges=b.destination_charges,
            total_price=b.total_price,
            transit_time_days=b.transit_time_days,
            quote_valid_until=b.quote_valid_until,
            accepted_at=b.accepted_at,
            is_superseded=(b.id not in active_bid_ids),
        )
        for b in all_bids
    ]

    # 3. Activity logs
    logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.rfq_id == rfq.id)
        .order_by(desc(ActivityLog.created_at), desc(ActivityLog.id))
        .all()
    )
    log_items = [
        ActivityLogItem(
            id=l.id,
            event_type=l.event_type,
            message=l.message,
            metadata=l.metadata_json or {},
            created_at=l.created_at,
        )
        for l in logs
    ]

    return RFQDetail(
        id=rfq.id,
        reference_id=rfq.reference_id,
        name=rfq.name,
        currency=rfq.currency,
        bid_start_time=rfq.bid_start_time,
        original_close_time=rfq.original_close_time,
        current_close_time=rfq.current_close_time,
        forced_close_time=rfq.forced_close_time,
        pickup_date=rfq.pickup_date,
        british_auction_enabled=rfq.british_auction_enabled,
        trigger_window_minutes=rfq.trigger_window_minutes,
        extension_minutes=rfq.extension_minutes,
        extension_trigger=rfq.extension_trigger,
        status=computed_status,
        extension_count=rfq.extension_count,
        closed_at=rfq.closed_at,
        current_rankings=rankings,
        bid_history=history,
        activity_logs=log_items,
    )


# -------------------------------------------------------------
# Bid Submission Endpoint
# -------------------------------------------------------------
@router.post("/rfqs/{id}/bids", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
def post_bid(
    id: int,
    quote: BidCreate,
    supplier: Supplier = Depends(require_supplier),
    db: Session = Depends(get_db),
):
    """
    Submits a quote in an auction. Restricted to Suppliers.
    Enforces atomic row locking, price revision rules, and British Auction extension evaluation.
    """
    return submit_bid(rfq_id=id, supplier=supplier, quote=quote, db=db)
