"""
test_database.py
----------------
Unit tests for the SQLite database layer.
"""

import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import Database


@pytest.fixture
def db(tmp_path):
    """Fresh in-memory-style database per test."""
    d = Database(db_path=tmp_path / "test.db")
    d.init()
    yield d
    d.close()


class TestWorkingDays:
    def test_upsert_and_query(self, db):
        db.upsert_working_day(date(2025, 8, 4), "working", "Regular")
        assert db.is_working_day(date(2025, 8, 4)) is True

    def test_holiday_not_working(self, db):
        db.upsert_working_day(date(2025, 8, 15), "holiday", "Independence Day")
        assert db.is_working_day(date(2025, 8, 15)) is False

    def test_unknown_date_not_working(self, db):
        assert db.is_working_day(date(2025, 9, 1)) is False

    def test_upsert_overwrite(self, db):
        db.upsert_working_day(date(2025, 8, 4), "working", "Regular")
        db.upsert_working_day(date(2025, 8, 4), "holiday", "Revised")
        assert db.is_working_day(date(2025, 8, 4)) is False

    def test_upcoming_working_days(self, db):
        db.upsert_working_day(date(2099, 1, 6), "working")
        db.upsert_working_day(date(2099, 1, 7), "working")
        db.upsert_working_day(date(2099, 1, 8), "holiday")
        upcoming = db.get_upcoming_working_days(n=10)
        dates = [d for d in upcoming if d.year == 2099]
        assert date(2099, 1, 6) in dates
        assert date(2099, 1, 8) not in dates


class TestBookingRecords:
    def test_record_and_query_success(self, db):
        db.record_booking(date(2025, 8, 4), "lunch", "success", meal_name="Rice & Dal", price=65.0)
        assert db.is_booked(date(2025, 8, 4), "lunch") is True

    def test_failed_booking_not_counted_as_booked(self, db):
        db.record_booking(date(2025, 8, 4), "lunch", "failed", error_message="Login failed")
        assert db.is_booked(date(2025, 8, 4), "lunch") is False

    def test_duplicate_booking_updates_record(self, db):
        db.record_booking(date(2025, 8, 4), "lunch", "failed")
        db.record_booking(date(2025, 8, 4), "lunch", "success", meal_name="Rice", confirmation_id="ABC123")
        assert db.is_booked(date(2025, 8, 4), "lunch") is True

    def test_get_bookings_date_filter(self, db):
        db.record_booking(date(2025, 8, 1), "lunch", "success")
        db.record_booking(date(2025, 8, 5), "lunch", "success")
        results = db.get_bookings(from_date=date(2025, 8, 4), to_date=date(2025, 8, 10))
        assert len(results) == 1
        assert results[0]["booking_date"] == "2025-08-05"

    def test_total_spend(self, db):
        db.record_booking(date(2025, 8, 1), "lunch", "success", price=65.0)
        db.record_booking(date(2025, 8, 1), "dinner", "success", price=50.0)
        db.record_booking(date(2025, 8, 2), "lunch", "failed", price=65.0)  # should not count
        assert db.total_spend() == pytest.approx(115.0)


class TestAgentState:
    def test_set_and_get(self, db):
        db.set_state("agent_paused", "true")
        assert db.get_state("agent_paused") == "true"

    def test_default_value(self, db):
        assert db.get_state("nonexistent_key", "default") == "default"

    def test_overwrite(self, db):
        db.set_state("agent_paused", "true")
        db.set_state("agent_paused", "false")
        assert db.get_state("agent_paused") == "false"

