"""
calendar_db.py
--------------
Lightweight SQLite store for working days + booking history.
(Simplified version of the original database.py)
"""

import sqlite3
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger("spacebasic.db")


class CalendarDB:
    def __init__(self, path="data/bookings.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS bookings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_date    TEXT NOT NULL,
                meal_type       TEXT NOT NULL,
                meal_name       TEXT,
                status          TEXT NOT NULL,
                confirmation_id TEXT,
                price           REAL DEFAULT 0,
                booked_at       TEXT,
                error_message   TEXT,
                UNIQUE(booking_date, meal_type)
            );

            CREATE TABLE IF NOT EXISTS working_days (
                day_date    TEXT PRIMARY KEY,
                day_type    TEXT NOT NULL,
                description TEXT,
                loaded_at   TEXT
            );
        """)
        self._conn.commit()

    # ── Working days ────────────────────────────────────────────────

    def is_working_day(self, d: date) -> bool:
        row = self._conn.execute(
            "SELECT day_type FROM working_days WHERE day_date=?", (d.isoformat(),)
        ).fetchone()
        return bool(row and row["day_type"] == "working")

    def upsert_day(self, d: date, day_type: str, description: str = ""):
        self._conn.execute(
            """INSERT INTO working_days (day_date, day_type, description, loaded_at)
               VALUES (?,?,?,?)
               ON CONFLICT(day_date) DO UPDATE SET
                   day_type=excluded.day_type,
                   description=excluded.description,
                   loaded_at=excluded.loaded_at""",
            (d.isoformat(), day_type, description, datetime.now().isoformat(timespec="seconds"))
        )
        self._conn.commit()

    def upcoming_working_days(self, n=5) -> List[date]:
        rows = self._conn.execute(
            "SELECT day_date FROM working_days WHERE day_type='working' AND day_date>=? ORDER BY day_date LIMIT ?",
            (date.today().isoformat(), n)
        ).fetchall()
        return [date.fromisoformat(r["day_date"]) for r in rows]

    def upcoming_holidays(self, n=3) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT * FROM working_days WHERE day_type IN ('holiday','vacation') AND day_date>=? ORDER BY day_date LIMIT ?",
            (date.today().isoformat(), n)
        ).fetchall()
        return [dict(r) for r in rows]

    def count_working_days(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as c FROM working_days WHERE day_type='working'"
        ).fetchone()
        return row["c"]

    # ── Bookings ─────────────────────────────────────────────────────

    def is_booked(self, d: date, meal_type: str) -> bool:
        row = self._conn.execute(
            "SELECT id FROM bookings WHERE booking_date=? AND meal_type=? AND status='success'",
            (d.isoformat(), meal_type)
        ).fetchone()
        return row is not None

    def record(self, d: date, meal_type: str, status: str, **kwargs):
        self._conn.execute(
            """INSERT INTO bookings
                (booking_date, meal_type, meal_name, status, confirmation_id, price, booked_at, error_message)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(booking_date, meal_type) DO UPDATE SET
                   meal_name=excluded.meal_name, status=excluded.status,
                   confirmation_id=excluded.confirmation_id, price=excluded.price,
                   booked_at=excluded.booked_at, error_message=excluded.error_message""",
            (
                d.isoformat(), meal_type,
                kwargs.get("meal_name", ""),
                status,
                kwargs.get("confirmation_id", ""),
                kwargs.get("price", 0.0),
                datetime.now().isoformat(timespec="seconds"),
                kwargs.get("error", ""),
            )
        )
        self._conn.commit()

    def today_summary(self) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT * FROM bookings WHERE booking_date=? ORDER BY meal_type",
            (date.today().isoformat(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def history(self, days=7) -> List[Dict]:
        from datetime import timedelta
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM bookings WHERE booking_date>=? ORDER BY booking_date DESC, meal_type",
            (since,)
        ).fetchall()
        return [dict(r) for r in rows]

    def total_spend(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(price),0) as t FROM bookings WHERE status='success'"
        ).fetchone()
        return float(row["t"])

