"""Kiểm thử đơn vị cho module tính toán compute_is_expired theo techrecruit-rules."""
from datetime import date, datetime, timedelta
import pytest

from app.services.saved_jobs_service import compute_is_expired


def test_status_not_published_is_expired():
    assert compute_is_expired("closed", None) is True
    assert compute_is_expired("draft", None) is True
    assert compute_is_expired(None, None) is True
    assert compute_is_expired("", None) is True
    assert compute_is_expired("paused", None) is True


def test_published_without_deadline_is_active():
    assert compute_is_expired("published", None) is False
    assert compute_is_expired("published", "") is False


def test_published_with_future_deadline():
    now = datetime(2026, 11, 15, 12, 0, 0)
    future_date = date(2026, 11, 20)
    future_dt = datetime(2026, 11, 20, 0, 0, 0)
    future_str = "2026-11-20"

    assert compute_is_expired("published", future_date, now=now) is False
    assert compute_is_expired("published", future_dt, now=now) is False
    assert compute_is_expired("published", future_str, now=now) is False


def test_published_with_past_deadline():
    now = datetime(2026, 11, 15, 12, 0, 0)
    past_date = date(2026, 11, 10)
    past_dt = datetime(2026, 11, 10, 0, 0, 0)
    past_str = "2026-11-10"

    assert compute_is_expired("published", past_date, now=now) is True
    assert compute_is_expired("published", past_dt, now=now) is True
    assert compute_is_expired("published", past_str, now=now) is True


def test_invalid_deadline_format_graceful():
    now = datetime(2026, 11, 15, 12, 0, 0)
    assert compute_is_expired("published", "invalid-date", now=now) is False
    assert compute_is_expired("published", 12345, now=now) is False
