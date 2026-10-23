from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status

from app.models.models import RFQ, Bid, CurrentBid, ActivityLog, Supplier
from app.schemas.schemas import BidCreate, BidResponse
from app.services.status_service import resolve_auction_status
from app.services.extension_engine import (
    calculate_new_close,
    is_within_trigger_window,
    evaluate_extension_trigger,
)


def get_db_clock(db: Session) -> datetime:
    """Fetches the current database clock timestamp."""
    try:
        res = db.execute(text("SELECT clock_timestamp()")).scalar()
        if res is not None:
            if res.tzinfo is None:
                return res.replace(tzinfo=timezone.utc)
            return res
    except Exception:
        pass
    return datetime.now(timezone.utc)


def get_current_supplier_ids(db: Session, rfq_id: int) -> List[int]:
    """Returns the ordered list of supplier IDs sorted by current ranking."""
    current_bids = (
        db.query(CurrentBid)
        .filter(CurrentBid.rfq_id == rfq_id)
        .order_by(CurrentBid.total_price.asc(), CurrentBid.accepted_at.asc(), CurrentBid.id.asc())
        .all()
    )
    return [cb.supplier_id for cb in current_bids]


def close_auction(rfq_id: int, db: Session, t_now: Optional[datetime] = None) -> Optional[str]:
    """
    Shared authoritative closure routine (PRD §4.4, HLD §3.2).
    Acquires exclusive lock, checks status, idempotently persists terminal_status & closed_at,
    and appends exactly one terminal activity log event.
    """
    if t_now is None:
        t_now = get_db_clock(db)

    # Lock RFQ row
    query = db.query(RFQ).filter(RFQ.id == rfq_id)
    if db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    rfq = query.first()

    if not rfq or rfq.terminal_status is not None:
        return rfq.terminal_status if rfq else None

    computed_status = resolve_auction_status(rfq, t_now)
    if computed_status in ("CLOSED", "FORCE_CLOSED"):
        rfq.terminal_status = computed_status
        rfq.closed_at = t_now

        event_name = "AUCTION_FORCE_CLOSED" if computed_status == "FORCE_CLOSED" else "AUCTION_CLOSED"
        msg = (
            f"Auction reached forced close cap ({rfq.forced_close_time.isoformat()}) and was force-closed"
            if computed_status == "FORCE_CLOSED"
            else f"Auction closed normally at deadline ({rfq.current_close_time.isoformat()})"
        )

        log_entry = ActivityLog(
            rfq_id=rfq.id,
            event_type=event_name,
            message=msg,
            metadata_json={
                "closed_at": t_now.isoformat(),
                "final_close_time": rfq.current_close_time.isoformat(),
                "forced_close_time": rfq.forced_close_time.isoformat(),
                "extension_count": rfq.extension_count,
            },
            created_at=t_now,
        )
        db.add(log_entry)
        db.commit()
        return computed_status

    return computed_status


def submit_bid(
    rfq_id: int,
    supplier: Supplier,
    quote: BidCreate,
    db: Session,
) -> BidResponse:
    """
    Critical Path: Bid submission transaction (PRD §4, HLD §3.1, Tech-Design §4).
    1. Lock RFQ row FOR UPDATE.
    2. Read db clock (accepted_at) after lock.
    3. Check Active status against database time.
    4. Validate supplier and revision: strictly lower than supplier's own current bid.
    5. Compute ranking_before from current_bids.
    6. Insert immutable bid_submissions and upsert current_bids.
    7. Compute ranking_after from current_bids.
    8. Insert BID_SUBMITTED activity log.
    9. If British Auction enabled and accepted_at in trigger window [C-X, C):
       - Evaluate trigger using ranking_before and ranking_after.
       - If qualifies: calculate new_close = min(current_close + Y, forced_close).
       - If new_close > current_close: extend, bump count, log TIME_EXTENDED.
       - Else if current_close == forced_close: log EXTENSION_SKIPPED_FORCED_CAP.
    10. Commit and return response with updated rank and close time.
    On ANY failure, rolls back completely.
    """
    try:
        # 1. SELECT ... FOR UPDATE
        query = db.query(RFQ).filter(RFQ.id == rfq_id)
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update()
        rfq = query.first()

        if not rfq:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")

        # 2. Capture DB clock after acquiring lock
        accepted_at = get_db_clock(db)

        # 3. Check auction status
        current_status = resolve_auction_status(rfq, accepted_at)
        if current_status != "ACTIVE":
            # If expired, trigger lazy closure
            if current_status in ("CLOSED", "FORCE_CLOSED"):
                close_auction(rfq_id, db, accepted_at)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Auction is not active (current status: {current_status})"
            )

        # Boundary rule check: accepted_at must be strictly before current_close_time and forced_close_time
        close_tz = rfq.current_close_time if rfq.current_close_time.tzinfo else rfq.current_close_time.replace(tzinfo=timezone.utc)
        forced_tz = rfq.forced_close_time if rfq.forced_close_time.tzinfo else rfq.forced_close_time.replace(tzinfo=timezone.utc)

        if accepted_at >= close_tz or accepted_at >= forced_tz:
            close_auction(rfq_id, db, accepted_at)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bidding has concluded for this auction"
            )

        # Validate quote validity date is after accepted_at
        valid_until_tz = quote.quote_valid_until if quote.quote_valid_until.tzinfo else quote.quote_valid_until.replace(tzinfo=timezone.utc)
        if valid_until_tz <= accepted_at:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quote validity must be in the future relative to bid submission time"
            )

        # 4. Check supplier revision constraint (strictly lower than own current bid)
        total_price = quote.freight_charges + quote.origin_charges + quote.destination_charges

        existing_current = (
            db.query(CurrentBid)
            .filter(CurrentBid.rfq_id == rfq_id, CurrentBid.supplier_id == supplier.id)
            .first()
        )

        if existing_current and total_price >= existing_current.total_price:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bid total ${total_price:.2f} must be strictly lower than your current bid of ${existing_current.total_price:.2f}"
            )

        # 5. Capture ranking_before (list of supplier IDs)
        ranking_before = get_current_supplier_ids(db, rfq_id)

        # 6. Insert into immutable bid_submissions
        new_bid = Bid(
            rfq_id=rfq.id,
            supplier_id=supplier.id,
            freight_charges=quote.freight_charges,
            origin_charges=quote.origin_charges,
            destination_charges=quote.destination_charges,
            total_price=total_price,
            transit_time_days=quote.transit_time_days,
            quote_valid_until=quote.quote_valid_until,
            accepted_at=accepted_at,
        )
        db.add(new_bid)
        db.flush()  # assign new_bid.id

        # Upsert into current_bids
        if existing_current:
            existing_current.bid_id = new_bid.id
            existing_current.freight_charges = quote.freight_charges
            existing_current.origin_charges = quote.origin_charges
            existing_current.destination_charges = quote.destination_charges
            existing_current.total_price = total_price
            existing_current.transit_time_days = quote.transit_time_days
            existing_current.quote_valid_until = quote.quote_valid_until
            existing_current.accepted_at = accepted_at
        else:
            new_current = CurrentBid(
                rfq_id=rfq.id,
                supplier_id=supplier.id,
                bid_id=new_bid.id,
                freight_charges=quote.freight_charges,
                origin_charges=quote.origin_charges,
                destination_charges=quote.destination_charges,
                total_price=total_price,
                transit_time_days=quote.transit_time_days,
                quote_valid_until=quote.quote_valid_until,
                accepted_at=accepted_at,
            )
            db.add(new_current)
        db.flush()

        # 7. Capture ranking_after
        ranking_after = get_current_supplier_ids(db, rfq_id)
        supplier_rank = ranking_after.index(supplier.id) + 1

        # 8. Log BID_SUBMITTED event
        bid_log = ActivityLog(
            rfq_id=rfq.id,
            bid_id=new_bid.id,
            event_type="BID_SUBMITTED",
            message=f"{supplier.carrier_name} submitted a quote of ${total_price:.2f} (Rank L{supplier_rank})",
            metadata_json={
                "supplier_id": supplier.id,
                "carrier_name": supplier.carrier_name,
                "total_price": float(total_price),
                "rank": supplier_rank,
                "accepted_at": accepted_at.isoformat(),
            },
            created_at=accepted_at,
        )
        db.add(bid_log)

        # 9. British Auction extension evaluation
        auction_extended = False
        extension_reason = None

        if (
            rfq.british_auction_enabled
            and rfq.trigger_window_minutes
            and rfq.extension_minutes
            and rfq.extension_trigger
        ):
            in_window = is_within_trigger_window(
                accepted_at=accepted_at,
                current_close_time=close_tz,
                trigger_window_minutes=rfq.trigger_window_minutes,
            )

            if in_window:
                qualifies, reason = evaluate_extension_trigger(
                    trigger_type=rfq.extension_trigger,
                    ranking_before=ranking_before,
                    ranking_after=ranking_after,
                )

                if qualifies:
                    new_close = calculate_new_close(
                        current_close_time=close_tz,
                        forced_close_time=forced_tz,
                        extension_minutes=rfq.extension_minutes,
                    )

                    if new_close > close_tz:
                        old_close_str = close_tz.isoformat()
                        rfq.current_close_time = new_close
                        rfq.extension_count += 1
                        auction_extended = True
                        extension_reason = reason

                        capped = (new_close == forced_tz)
                        ext_msg = (
                            f"Auction extended by {rfq.extension_minutes}m to {new_close.strftime('%H:%M:%S UTC')} "
                            f"(capped at forced close) due to: {reason}"
                            if capped
                            else f"Auction extended by {rfq.extension_minutes}m to {new_close.strftime('%H:%M:%S UTC')} "
                            f"due to: {reason}"
                        )

                        ext_log = ActivityLog(
                            rfq_id=rfq.id,
                            bid_id=new_bid.id,
                            event_type="TIME_EXTENDED",
                            message=ext_msg,
                            metadata_json={
                                "trigger": rfq.extension_trigger,
                                "trigger_reason": reason,
                                "old_close_time": old_close_str,
                                "new_close_time": new_close.isoformat(),
                                "forced_close_time": forced_tz.isoformat(),
                                "extension_count": rfq.extension_count,
                                "capped_at_forced": capped,
                            },
                            created_at=accepted_at,
                        )
                        db.add(ext_log)
                    else:
                        # Already at forced close time cap!
                        skip_msg = (
                            f"Trigger '{rfq.extension_trigger}' qualified ({reason}), but auction is already at "
                            f"the forced close deadline ({forced_tz.strftime('%H:%M:%S UTC')}). No extra time added."
                        )
                        skip_log = ActivityLog(
                            rfq_id=rfq.id,
                            bid_id=new_bid.id,
                            event_type="EXTENSION_SKIPPED_FORCED_CAP",
                            message=skip_msg,
                            metadata_json={
                                "trigger": rfq.extension_trigger,
                                "trigger_reason": reason,
                                "current_close_time": close_tz.isoformat(),
                                "forced_close_time": forced_tz.isoformat(),
                            },
                            created_at=accepted_at,
                        )
                        db.add(skip_log)

        # 10. Commit transaction
        db.commit()

        return BidResponse(
            bid_id=new_bid.id,
            rfq_id=rfq.id,
            supplier_id=supplier.id,
            carrier_name=supplier.carrier_name,
            total_price=total_price,
            rank=supplier_rank,
            auction_extended=auction_extended,
            new_close_time=rfq.current_close_time,
            extension_reason=extension_reason,
            status=resolve_auction_status(rfq, accepted_at),
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit bid: {str(e)}"
        )
