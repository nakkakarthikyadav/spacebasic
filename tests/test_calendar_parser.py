"""
test_calendar_parser.py
-----------------------
Unit tests for the calendar parsing module.
Run with: pytest tests/
"""

import pytest
from datetime import date
from pathlib import Path
import tempfile, csv, os

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calendar_parser import CalendarParser, DAY_TYPE_WORKING, DAY_TYPE_HOLIDAY, DAY_TYPE_WEEKEND, DAY_TYPE_VACATION


ACAD_START = date(2025, 7, 1)
ACAD_END   = date(2026, 5, 31)

@pytest.fixture
def parser():
    return CalendarParser(
        academic_start=ACAD_START,
        academic_end=ACAD_END,
        saturday_working=False,
        sunday_working=False,
    )


def make_csv(rows: list[dict]) -> str:
    """Write rows to a temp CSV and return the path."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "day_type", "description"])
        writer.writeheader()
        writer.writerows(rows)
    return path


class TestCSVParsing:
    def test_working_day(self, parser):
        path = make_csv([{"date": "2025-08-04", "day_type": "working", "description": "Regular class"}])
        days = parser.parse(path)
        match = next((d for d in days if d["date"] == date(2025, 8, 4)), None)
        assert match is not None
        assert match["day_type"] == DAY_TYPE_WORKING

    def test_holiday(self, parser):
        path = make_csv([{"date": "2025-08-15", "day_type": "holiday", "description": "Independence Day"}])
        days = parser.parse(path)
        match = next((d for d in days if d["date"] == date(2025, 8, 15)), None)
        assert match is not None
        assert match["day_type"] == DAY_TYPE_HOLIDAY

    def test_weekend_auto_classification(self, parser):
        # 2025-08-03 is a Sunday
        path = make_csv([])
        days = parser.parse(path)
        sunday = next((d for d in days if d["date"] == date(2025, 8, 3)), None)
        assert sunday is not None
        assert sunday["day_type"] == DAY_TYPE_WEEKEND

    def test_monday_is_working_by_default(self, parser):
        path = make_csv([])
        days = parser.parse(path)
        # 2025-07-07 = Monday
        monday = next((d for d in days if d["date"] == date(2025, 7, 7)), None)
        assert monday is not None
        assert monday["day_type"] == DAY_TYPE_WORKING

    def test_vacation_keyword(self, parser):
        path = make_csv([{"date": "2025-12-25", "day_type": "vacation", "description": "Winter vacation"}])
        days = parser.parse(path)
        match = next((d for d in days if d["date"] == date(2025, 12, 25)), None)
        assert match is not None
        assert match["day_type"] == DAY_TYPE_VACATION

    def test_saturday_working_override(self):
        p = CalendarParser(ACAD_START, ACAD_END, saturday_working=True, sunday_working=False)
        path = make_csv([])
        days = p.parse(path)
        # 2025-07-05 = Saturday
        sat = next((d for d in days if d["date"] == date(2025, 7, 5)), None)
        assert sat is not None
        assert sat["day_type"] == DAY_TYPE_WORKING

    def test_out_of_range_date_excluded(self, parser):
        path = make_csv([{"date": "2024-01-01", "day_type": "working", "description": "Before acad year"}])
        days = parser.parse(path)
        match = next((d for d in days if d["date"] == date(2024, 1, 1)), None)
        assert match is None


class TestDateParsing:
    def test_iso_date(self, parser):
        d = parser._parse_date("2025-08-15")
        assert d == date(2025, 8, 15)

    def test_dd_mm_yyyy(self, parser):
        d = parser._parse_date("15/08/2025")
        assert d == date(2025, 8, 15)

    def test_invalid_date(self, parser):
        d = parser._parse_date("not-a-date")
        assert d is None

    def test_empty_string(self, parser):
        d = parser._parse_date("")
        assert d is None


class TestKeywordClassification:
    def test_holiday_keyword(self, parser):
        assert parser._classify_by_keywords("Diwali holiday closed") == DAY_TYPE_HOLIDAY

    def test_vacation_keyword(self, parser):
        assert parser._classify_by_keywords("summer vacation") == DAY_TYPE_VACATION

    def test_working_keyword(self, parser):
        assert parser._classify_by_keywords("regular class day") == DAY_TYPE_WORKING

    def test_ambiguous_returns_unknown(self, parser):
        from src.calendar_parser import DAY_TYPE_UNKNOWN
        assert parser._classify_by_keywords("misc entry") == DAY_TYPE_UNKNOWN

