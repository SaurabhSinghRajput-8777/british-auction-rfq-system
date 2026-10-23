from datetime import datetime, timedelta
from typing import Optional, List, Tuple


def calculate_new_close(
    current_close_time: datetime,
    forced_close_time: datetime,
    extension_minutes: int,
) -> datetime:
    """
    Computes the extended close time capped at forced_close_time.
    Formula: new_close = min(current_close + Y, forced_close)
    """
    candidate = current_close_time + timedelta(minutes=extension_minutes)
    return min(candidate, forced_close_time)


def is_within_trigger_window(
    accepted_at: datetime,
    current_close_time: datetime,
    trigger_window_minutes: int,
) -> bool:
    """
    Checks if accepted_at falls in [current_close_time - X minutes, current_close_time).
    Window start is inclusive; close time is exclusive.
    """
    window_start = current_close_time - timedelta(minutes=trigger_window_minutes)
    return window_start <= accepted_at < current_close_time


def evaluate_extension_trigger(
    trigger_type: str,
    ranking_before: List[int],
    ranking_after: List[int],
) -> Tuple[bool, str]:
    """
    Evaluates whether the trigger conditions are met:
    - BID_RECEIVED: Always qualifies if inside the trigger window.
    - ANY_RANK_CHANGE: Full ordered list of supplier IDs differs (supplier_ids_before != supplier_ids_after).
      Explicitly fires if a new supplier enters.
    - L1_RANK_CHANGE: L1 supplier ID changed (l1_before != l1_after).
      Fires if no prior bidder exists and first bidder enters.

    Returns:
        (qualifies: bool, reason: str)
    """
    t_type = trigger_type.upper()

    if t_type == "BID_RECEIVED":
        return True, "Bid received within trigger window"

    elif t_type == "ANY_RANK_CHANGE":
        if ranking_before != ranking_after:
            if not ranking_before and ranking_after:
                return True, f"New supplier {ranking_after[0]} submitted the first bid and established initial ranking"
            return True, f"Supplier ranking order changed from {ranking_before} to {ranking_after}"
        return False, "Bid accepted, but supplier ranking order did not change"

    elif t_type == "L1_RANK_CHANGE":
        l1_before = ranking_before[0] if ranking_before else None
        l1_after = ranking_after[0] if ranking_after else None

        if l1_before != l1_after:
            if l1_before is None:
                return True, f"Supplier {l1_after} placed the first bid and became L1"
            return True, f"Lowest bidder (L1) changed from Supplier {l1_before} to Supplier {l1_after}"
        return False, f"Lowest bidder (L1) remained Supplier {l1_before}"

    else:
        raise ValueError(f"Unknown extension trigger type: {trigger_type}")
