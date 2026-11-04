"""
test_booking_dry_run.py
-----------------------
Integration-style test that runs a full booking cycle in DRY RUN mode.
No browser is opened; the BookingAgent's dry_run flag prevents any real action.

Prerequisites
-------------
  - .env file must exist with SPACEBASIC_URL, SPACEBASIC_USERNAME, SPACEBASIC_PASSWORD
  - config.yaml must have agent.dry_run: true  (enforced below even if not)

Run with:
    pytest tests/test_booking_dry_run.py -v
"""

import sys
import os
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import Database
from src.notifier import Notifier
from src.booking_agent import BookingAgent


def make_dry_run_config(tmp_path) -> dict:
    """Minimal config for dry-run testing."""
    return {
        "agent": {
            "name": "Test Agent",
            "dry_run": True,     # ALWAYS true in tests
            "timezone": "Asia/Kolkata",
        },
        "meal_preferences": {
            "book_breakfast": True,
            "book_lunch": True,
            "book_dinner": False,
            "diet_type": "vegetarian",
            "breakfast_preferences": ["Test Breakfast"],
            "lunch_preferences": ["Test Lunch"],
            "allow_alternative": True,
            "max_daily_budget": 0,
        },
        "browser": {
            "headless": True,
            "profile_dir": str(tmp_path / "browser_profile"),
            "browser_type": "chromium",
            "page_timeout": 15,
        },
        "notifications": {
            "desktop_notifications": False,
            "email_notifications": False,
        },
    }


@pytest.fixture
def setup(tmp_path):
    db = Database(db_path=tmp_path / "test.db")
    db.init()

    # Seed today as a working day so the agent does not skip
    db.upsert_working_day(date.today(), "working", "Test working day")

    config = make_dry_run_config(tmp_path)
    notifier = Notifier(config)
    agent = BookingAgent(config, db, notifier)
    return agent, db


class TestDryRunCycle:
    def test_cycle_skips_non_working_day(self, tmp_path):
        db = Database(db_path=tmp_path / "test2.db")
        db.init()
        # Do NOT seed today → agent should skip
        config = make_dry_run_config(tmp_path)
        notifier = Notifier(config)
        agent = BookingAgent(config, db, notifier)
        result = agent.run_booking_cycle()
        assert result["booked"] == []

    def test_duplicate_guard(self, setup):
        agent, db = setup
        # Pre-seed a successful booking
        db.record_booking(date.today(), "breakfast", "success", meal_name="Test Breakfast")
        db.record_booking(date.today(), "lunch", "success", meal_name="Test Lunch")
        result = agent.run_booking_cycle()
        # Both already booked — should not appear in booked list
        assert result["booked"] == []

    def test_dry_run_flag_enforced(self, setup):
        """Verify dry_run is always True in test config."""
        agent, _ = setup
        assert agent.dry_run is True, "dry_run must be True during tests!"

