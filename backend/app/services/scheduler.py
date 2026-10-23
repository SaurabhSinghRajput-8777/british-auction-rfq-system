import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.models import RFQ
from app.services.auction_service import close_auction, get_db_clock

logger = logging.getLogger(__name__)


def check_and_close_expired_auctions():
    """
    Periodic job: Finds all RFQs whose effective close has passed and whose terminal_status is NULL,
    then executes the shared close_auction routine with row-level locks (SKIP LOCKED if on PostgreSQL).
    """
    db: Session = SessionLocal()
    try:
        t_now = get_db_clock(db)

        # Query candidates whose effective close time has arrived
        query = (
            db.query(RFQ.id)
            .filter(
                RFQ.terminal_status.is_(None),
                RFQ.current_close_time <= t_now,
            )
        )

        # On postgresql, use FOR UPDATE SKIP LOCKED
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)

        candidate_ids = [row[0] for row in query.all()]

        for rfq_id in candidate_ids:
            try:
                final_status = close_auction(rfq_id, db, t_now)
                if final_status:
                    logger.info(f"Scheduler persisted terminal state '{final_status}' for RFQ {rfq_id}")
            except Exception as e:
                logger.error(f"Error closing RFQ {rfq_id} in scheduler: {e}")
                db.rollback()

    except Exception as e:
        logger.error(f"Error in scheduler execution loop: {e}")
    finally:
        db.close()
