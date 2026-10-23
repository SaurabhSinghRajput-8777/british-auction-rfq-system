import pytest
from datetime import datetime, timezone, timedelta
from app.services.extension_engine import (
    calculate_new_close,
    is_within_trigger_window,
    evaluate_extension_trigger,
)


def test_calculate_new_close_normal():
    # 18:00 + 5 min = 18:05, forced close 18:30
    c = datetime(2026, 10, 23, 18, 0, 0, tzinfo=timezone.utc)
    f = datetime(2026, 10, 23, 18, 30, 0, tzinfo=timezone.utc)
    res = calculate_new_close(c, f, 5)
    assert res == datetime(2026, 10, 23, 18, 5, 0, tzinfo=timezone.utc)


def test_calculate_new_close_capped_at_forced():
    # 18:28 + 5 min = 18:33, but capped at 18:30
    c = datetime(2026, 10, 23, 18, 28, 0, tzinfo=timezone.utc)
    f = datetime(2026, 10, 23, 18, 30, 0, tzinfo=timezone.utc)
    res = calculate_new_close(c, f, 5)
    assert res == datetime(2026, 10, 23, 18, 30, 0, tzinfo=timezone.utc)


def test_calculate_new_close_already_at_forced():
    # 18:30 + 5 min = 18:35, capped at 18:30
    c = datetime(2026, 10, 23, 18, 30, 0, tzinfo=timezone.utc)
    f = datetime(2026, 10, 23, 18, 30, 0, tzinfo=timezone.utc)
    res = calculate_new_close(c, f, 5)
    assert res == datetime(2026, 10, 23, 18, 30, 0, tzinfo=timezone.utc)


def test_is_within_trigger_window_boundaries():
    close = datetime(2026, 10, 23, 18, 0, 0, tzinfo=timezone.utc)
    x = 10  # window is 17:50:00 <= t < 18:00:00

    # Exactly 10 mins before (17:50:00) -> inclusive, so True
    t_start = datetime(2026, 10, 23, 17, 50, 0, tzinfo=timezone.utc)
    assert is_within_trigger_window(t_start, close, x) is True

    # 1 microsecond before start (17:49:59.999999) -> False
    t_before = t_start - timedelta(microseconds=1)
    assert is_within_trigger_window(t_before, close, x) is False

    # Inside window (17:55:00) -> True
    t_mid = datetime(2026, 10, 23, 17, 55, 0, tzinfo=timezone.utc)
    assert is_within_trigger_window(t_mid, close, x) is True

    # 1 microsecond before close (17:59:59.999999) -> True
    t_just_before = close - timedelta(microseconds=1)
    assert is_within_trigger_window(t_just_before, close, x) is True

    # Exactly close (18:00:00) -> exclusive, so False
    assert is_within_trigger_window(close, close, x) is False


def test_trigger_bid_received():
    qualifies, reason = evaluate_extension_trigger("BID_RECEIVED", [1, 2], [1, 2])
    assert qualifies is True
    assert "Bid received" in reason


def test_trigger_any_rank_change():
    # 1. First bid ever: [] -> [1] -> qualifies
    qualifies, _ = evaluate_extension_trigger("ANY_RANK_CHANGE", [], [1])
    assert qualifies is True

    # 2. New supplier enters in last position: [1, 2] -> [1, 2, 3] -> qualifies (full list changed)
    qualifies, _ = evaluate_extension_trigger("ANY_RANK_CHANGE", [1, 2], [1, 2, 3])
    assert qualifies is True

    # 3. Position swap: [1, 2] -> [2, 1] -> qualifies
    qualifies, _ = evaluate_extension_trigger("ANY_RANK_CHANGE", [1, 2], [2, 1])
    assert qualifies is True

    # 4. Supplier improves price, but order unchanged: [1, 2] -> [1, 2] -> False
    qualifies, reason = evaluate_extension_trigger("ANY_RANK_CHANGE", [1, 2], [1, 2])
    assert qualifies is False


def test_trigger_l1_rank_change():
    # 1. First bid ever: [] -> [1] -> qualifies (none -> first)
    qualifies, _ = evaluate_extension_trigger("L1_RANK_CHANGE", [], [1])
    assert qualifies is True

    # 2. New supplier enters in last position: [1, 2] -> [1, 2, 3] -> False (L1 is still 1)
    qualifies, _ = evaluate_extension_trigger("L1_RANK_CHANGE", [1, 2], [1, 2, 3])
    assert qualifies is False

    # 3. Supplier 2 overtakes Supplier 1 to become L1: [1, 2] -> [2, 1] -> True
    qualifies, _ = evaluate_extension_trigger("L1_RANK_CHANGE", [1, 2], [2, 1])
    assert qualifies is True

    # 4. Supplier 3 overtakes Supplier 2, but Supplier 1 remains L1: [1, 2, 3] -> [1, 3, 2] -> False
    qualifies, _ = evaluate_extension_trigger("L1_RANK_CHANGE", [1, 2, 3], [1, 3, 2])
    assert qualifies is False

    # 5. Current L1 lowers price and remains L1: [1, 2] -> [1, 2] -> False
    qualifies, _ = evaluate_extension_trigger("L1_RANK_CHANGE", [1, 2], [1, 2])
    assert qualifies is False
