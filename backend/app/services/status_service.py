from datetime import datetime, timezone
from typing import Optional
from app.models.models import RFQ


def resolve_auction_status(rfq: RFQ, t: datetime) -> str:
    """
    Authoritative logic implementing Scheduled / Active / Closed / Force Closed (PRD §4.4).
    
    1. If a terminal status is already persisted in the database, return it (immutable).
    2. Before start: SCHEDULED.
    3. Between start and effective close: ACTIVE.
    4. At or after effective close:
       - If current_close_time == forced_close_time -> FORCE_CLOSED
       - If current_close_time < forced_close_time -> CLOSED
    """
    if rfq.terminal_status:
        return rfq.terminal_status

    # Ensure tz-awareness
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    
    start = rfq.bid_start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
        
    current_close = rfq.current_close_time
    if current_close.tzinfo is None:
        current_close = current_close.replace(tzinfo=timezone.utc)

    forced_close = rfq.forced_close_time
    if forced_close.tzinfo is None:
        forced_close = forced_close.replace(tzinfo=timezone.utc)

    if t < start:
        return "SCHEDULED"

    if t < current_close:
        return "ACTIVE"

    # t >= current_close: Terminal
    if current_close >= forced_close:
        return "FORCE_CLOSED"
    else:
        return "CLOSED"
