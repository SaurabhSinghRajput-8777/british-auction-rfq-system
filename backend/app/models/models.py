from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Boolean,
    Numeric,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(160), nullable=False, unique=True)
    role = Column(String(20), nullable=False)  # BUYER, SUPPLIER, ADMIN
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    supplier_profile = relationship("Supplier", back_populates="user", uselist=False)

    __table_args__ = (
        CheckConstraint("role IN ('BUYER', 'SUPPLIER', 'ADMIN')", name="chk_user_role"),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    carrier_name = Column(String(160), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="supplier_profile")
    bids = relationship("Bid", back_populates="supplier")
    current_bids = relationship("CurrentBid", back_populates="supplier")


class RFQ(Base):
    __tablename__ = "rfqs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(60), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)

    bid_start_time = Column(DateTime(timezone=True), nullable=False)
    original_close_time = Column(DateTime(timezone=True), nullable=False)
    current_close_time = Column(DateTime(timezone=True), nullable=False)
    forced_close_time = Column(DateTime(timezone=True), nullable=False)
    pickup_date = Column(DateTime(timezone=True), nullable=False)

    british_auction_enabled = Column(Boolean, default=True, nullable=False)
    trigger_window_minutes = Column(Integer, nullable=True)
    extension_minutes = Column(Integer, nullable=True)
    extension_trigger = Column(String(30), nullable=True)  # BID_RECEIVED, ANY_RANK_CHANGE, L1_RANK_CHANGE

    terminal_status = Column(String(20), nullable=True)  # CLOSED, FORCE_CLOSED
    extension_count = Column(Integer, default=0, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    bids = relationship("Bid", back_populates="rfq", cascade="all, delete-orphan")
    current_bids = relationship("CurrentBid", back_populates="rfq", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="rfq", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("original_close_time > bid_start_time", name="chk_close_after_start"),
        CheckConstraint("forced_close_time > original_close_time", name="chk_forced_after_original"),
        CheckConstraint("current_close_time <= forced_close_time", name="chk_current_not_after_forced"),
        CheckConstraint("current_close_time >= original_close_time", name="chk_current_not_before_original"),
        CheckConstraint("extension_count >= 0", name="chk_extension_count_non_negative"),
        CheckConstraint(
            """(british_auction_enabled = 0 OR british_auction_enabled = FALSE) OR (
                trigger_window_minutes IS NOT NULL AND trigger_window_minutes > 0
                AND extension_minutes IS NOT NULL AND extension_minutes > 0
                AND extension_trigger IS NOT NULL
                AND extension_trigger IN ('BID_RECEIVED', 'ANY_RANK_CHANGE', 'L1_RANK_CHANGE')
            )""",
            name="chk_british_config",
        ),
    )


class Bid(Base):
    """Immutable history of all accepted quote submissions."""
    __tablename__ = "bid_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rfq_id = Column(BigInteger, ForeignKey("rfqs.id"), nullable=False)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=False)

    freight_charges = Column(Numeric(14, 2), nullable=False)
    origin_charges = Column(Numeric(14, 2), nullable=False)
    destination_charges = Column(Numeric(14, 2), nullable=False)
    total_price = Column(Numeric(14, 2), nullable=False)
    transit_time_days = Column(Integer, nullable=False)
    quote_valid_until = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False)

    rfq = relationship("RFQ", back_populates="bids")
    supplier = relationship("Supplier", back_populates="bids")

    __table_args__ = (
        CheckConstraint("freight_charges >= 0", name="chk_freight_non_negative"),
        CheckConstraint("origin_charges >= 0", name="chk_origin_non_negative"),
        CheckConstraint("destination_charges >= 0", name="chk_dest_non_negative"),
        CheckConstraint("total_price > 0", name="chk_total_positive"),
        CheckConstraint("transit_time_days > 0", name="chk_transit_positive"),
        Index("idx_bids_rfq_time", "rfq_id", "accepted_at"),
    )


class CurrentBid(Base):
    """Exactly one current active bid per (rfq, supplier) used directly for ranking."""
    __tablename__ = "current_bids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rfq_id = Column(BigInteger, ForeignKey("rfqs.id"), nullable=False)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=False)
    bid_id = Column(BigInteger, ForeignKey("bid_submissions.id"), nullable=False)

    total_price = Column(Numeric(14, 2), nullable=False)
    freight_charges = Column(Numeric(14, 2), nullable=False)
    origin_charges = Column(Numeric(14, 2), nullable=False)
    destination_charges = Column(Numeric(14, 2), nullable=False)
    transit_time_days = Column(Integer, nullable=False)
    quote_valid_until = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False)

    rfq = relationship("RFQ", back_populates="current_bids")
    supplier = relationship("Supplier", back_populates="current_bids")

    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id", name="uq_current_bid_rfq_supplier"),
        Index("idx_current_bids_ranking", "rfq_id", "total_price", "accepted_at", "id"),
    )


class ActivityLog(Base):
    """Immutable audit trail of auction events with detailed reasons."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rfq_id = Column(BigInteger, ForeignKey("rfqs.id"), nullable=False)
    bid_id = Column(BigInteger, ForeignKey("bid_submissions.id"), nullable=True)
    event_type = Column(String(40), nullable=False)
    # RFQ_CREATED, BID_SUBMITTED, TIME_EXTENDED, EXTENSION_SKIPPED_FORCED_CAP, AUCTION_CLOSED, AUCTION_FORCE_CLOSED
    message = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    rfq = relationship("RFQ", back_populates="activity_logs")

    __table_args__ = (
        Index("idx_activity_logs_rfq_time", "rfq_id", "created_at", "id"),
    )
