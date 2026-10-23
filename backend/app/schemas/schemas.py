from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator


# -------------------------------------------------------------
# Auth / Identity Schemas
# -------------------------------------------------------------

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    carrier_name: Optional[str] = None
    supplier_id: Optional[int] = None

    class Config:
        from_attributes = True


# -------------------------------------------------------------
# RFQ Schemas
# -------------------------------------------------------------

class RFQCreate(BaseModel):
    reference_id: str = Field(..., min_length=1, max_length=60)
    name: str = Field(..., min_length=1, max_length=200)
    currency: str = Field("USD", min_length=3, max_length=3)
    bid_start_time: datetime
    original_close_time: datetime
    forced_close_time: datetime
    pickup_date: datetime

    british_auction_enabled: bool = True
    trigger_window_minutes: Optional[int] = None
    extension_minutes: Optional[int] = None
    extension_trigger: Optional[str] = None  # BID_RECEIVED, ANY_RANK_CHANGE, L1_RANK_CHANGE

    @model_validator(mode="after")
    def validate_rules(self):
        if self.original_close_time <= self.bid_start_time:
            raise ValueError("Bid Close Time must be strictly later than Bid Start Time")

        if self.forced_close_time <= self.original_close_time:
            raise ValueError("Forced Bid Close Time must be strictly later than Bid Close Time")

        if self.british_auction_enabled:
            if not self.trigger_window_minutes or self.trigger_window_minutes <= 0:
                raise ValueError("Trigger Window (X) must be an integer >= 1 when British Auction is enabled")
            if not self.extension_minutes or self.extension_minutes <= 0:
                raise ValueError("Extension Duration (Y) must be an integer >= 1 when British Auction is enabled")
            allowed_triggers = {"BID_RECEIVED", "ANY_RANK_CHANGE", "L1_RANK_CHANGE"}
            if not self.extension_trigger or self.extension_trigger.upper() not in allowed_triggers:
                raise ValueError(f"Extension trigger must be one of {allowed_triggers}")
            self.extension_trigger = self.extension_trigger.upper()
        return self


class RFQListItem(BaseModel):
    id: int
    reference_id: str
    name: str
    currency: str
    bid_start_time: datetime
    original_close_time: datetime
    current_close_time: datetime
    forced_close_time: datetime
    pickup_date: datetime
    british_auction_enabled: bool
    trigger_window_minutes: Optional[int]
    extension_minutes: Optional[int]
    extension_trigger: Optional[str]
    status: str
    extension_count: int
    current_lowest_bid: Optional[Decimal] = None
    current_lowest_carrier: Optional[str] = None
    total_bids_count: int = 0

    class Config:
        from_attributes = True


class RankedBidItem(BaseModel):
    rank: int
    supplier_id: int
    carrier_name: str
    bid_id: int
    freight_charges: Decimal
    origin_charges: Decimal
    destination_charges: Decimal
    total_price: Decimal
    transit_time_days: int
    quote_valid_until: datetime
    accepted_at: datetime


class BidHistoryItem(BaseModel):
    id: int
    supplier_id: int
    carrier_name: str
    freight_charges: Decimal
    origin_charges: Decimal
    destination_charges: Decimal
    total_price: Decimal
    transit_time_days: int
    quote_valid_until: datetime
    accepted_at: datetime
    is_superseded: bool


class ActivityLogItem(BaseModel):
    id: int
    event_type: str
    message: str
    metadata: Dict[str, Any]
    created_at: datetime


class RFQDetail(BaseModel):
    id: int
    reference_id: str
    name: str
    currency: str
    bid_start_time: datetime
    original_close_time: datetime
    current_close_time: datetime
    forced_close_time: datetime
    pickup_date: datetime
    british_auction_enabled: bool
    trigger_window_minutes: Optional[int]
    extension_minutes: Optional[int]
    extension_trigger: Optional[str]
    status: str
    extension_count: int
    closed_at: Optional[datetime] = None
    
    current_rankings: List[RankedBidItem] = []
    bid_history: List[BidHistoryItem] = []
    activity_logs: List[ActivityLogItem] = []

    class Config:
        from_attributes = True


# -------------------------------------------------------------
# Bid Submission Schemas
# -------------------------------------------------------------

class BidCreate(BaseModel):
    freight_charges: Decimal = Field(..., ge=0)
    origin_charges: Decimal = Field(..., ge=0)
    destination_charges: Decimal = Field(..., ge=0)
    transit_time_days: int = Field(..., ge=1)
    quote_valid_until: datetime

    @model_validator(mode="after")
    def validate_total(self):
        total = self.freight_charges + self.origin_charges + self.destination_charges
        if total <= 0:
            raise ValueError("Total quote price (freight + origin + destination) must be > 0")
        return self


class BidResponse(BaseModel):
    bid_id: int
    rfq_id: int
    supplier_id: int
    carrier_name: str
    total_price: Decimal
    rank: int
    auction_extended: bool
    new_close_time: datetime
    extension_reason: Optional[str] = None
    status: str
