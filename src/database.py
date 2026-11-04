"""
database.py
-----------
SQLite persistence layer for the SpaceBasic booking agent.

Tables
------
  bookings       — every booking attempt (success or failure)
  working_days   — parsed calendar: dates classified as working / holiday
  agent_state    — key-value store for agent runtime flags

Usage
-----
  db = Database()
  db.init()
  db.record_booking(...)
"""

import sqlite3
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("spacebasic.database")

DB_PATH = Path("data") / "bookings.db"


class Database:
    """Thin wrapper around sqlite3 for the booking agent."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Create all tables if they do not already exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bookings (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_date      TEXT NOT NULL,          -- ISO-8601 date
                meal_type         TEXT NOT NULL,          -- breakfast / lunch / dinner
                meal_name         TEXT,
                status            TEXT NOT NULL,          -- success / failed / skipped
                confirmation_id   TEXT,
                price             REAL,
                booked_at         TEXT,                   -- ISO-8601 datetime
                error_message     TEXT
            );

            CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_date_meal
                ON bookings (booking_date, meal_type);

            CREATE TABLE IF NOT EXISTS working_days (
                day_date          TEXT PRIMARY KEY,       -- ISO-8601 date
                day_type          TEXT NOT NULL,          -- working / holiday / weekend / vacation
                description       TEXT,
                source_file       TEXT,
                loaded_at         TEXT
            );

            CREATE TABLE IF NOT EXISTS agent_state (
                key               TEXT PRIMARY KEY,
                value             TEXT,
                updated_at        TEXT
            );
        """)
        conn.commit()
        logger.info("Database initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # Booking records
    # ------------------------------------------------------------------

    def is_booked(self, booking_date: date, meal_type: str) -> bool:
        """Return True if a successful booking already exists for this date+meal."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id FROM bookings WHERE booking_date=? AND meal_type=? AND status='success'",
            (booking_date.isoformat(), meal_type),
        ).fetchone()
        return row is not None

    def record_booking(
        self,
        booking_date: date,
        meal_type: str,
        status: str,
        meal_name: str = "",
        confirmation_id: str = "",
        price: float = 0.0,
        error_message: str = "",
    ) -> None:
        """
        Insert or replace a booking record.

        status must be one of: 'success', 'failed', 'skipped'
        """
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO bookings
                (booking_date, meal_type, meal_name, status,
                 confirmation_id, price, booked_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(booking_date, meal_type) DO UPDATE SET
                meal_name       = excluded.meal_name,
                status          = excluded.status,
                confirmation_id = excluded.confirmation_id,
                price           = excluded.price,
                booked_at       = excluded.booked_at,
                error_message   = excluded.error_message
            """,
            (
                booking_date.isoformat(),
                meal_type,
                meal_name,
                status,
                confirmation_id,
                price,
                datetime.now().isoformat(timespec="seconds"),
                error_message,
            ),
        )
        conn.commit()
        logger.debug("Booking recorded: %s %s → %s", booking_date, meal_type, status)

    def get_bookings(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch booking records, optionally filtered by date range."""
        conn = self._get_conn()
        query = "SELECT * FROM bookings WHERE 1=1"
        params: list = []
        if from_date:
            query += " AND booking_date >= ?"
            params.append(from_date.isoformat())
        if to_date:
            query += " AND booking_date <= ?"
            params.append(to_date.isoformat())
        query += " ORDER BY booking_date DESC, meal_type"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_today_bookings(self) -> List[Dict[str, Any]]:
        return self.get_bookings(from_date=date.today(), to_date=date.today())

    # ------------------------------------------------------------------
    # Working-day calendar
    # ------------------------------------------------------------------

    def is_working_day(self, check_date: date) -> bool:
        """Return True if the calendar says this date is a working day."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT day_type FROM working_days WHERE day_date=?",
            (check_date.isoformat(),),
        ).fetchone()
        if row is None:
            return False  # Unknown date → do NOT book (conservative)
        return row["day_type"] == "working"

    def get_day_type(self, check_date: date) -> Optional[str]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT day_type, description FROM working_days WHERE day_date=?",
            (check_date.isoformat(),),
        ).fetchone()
        return dict(row) if row else None

    def upsert_working_day(
        self,
        day_date: date,
        day_type: str,
        description: str = "",
        source_file: str = "",
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO working_days (day_date, day_type, description, source_file, loaded_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(day_date) DO UPDATE SET
                day_type    = excluded.day_type,
                description = excluded.description,
                source_file = excluded.source_file,
                loaded_at   = excluded.loaded_at
            """,
            (
                day_date.isoformat(),
                day_type,
                description,
                source_file,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()

    def get_upcoming_working_days(self, n: int = 7) -> List[date]:
        conn = self._get_conn()
        today = date.today().isoformat()
        rows = conn.execute(
            "SELECT day_date FROM working_days WHERE day_type='working' AND day_date >= ? ORDER BY day_date LIMIT ?",
            (today, n),
        ).fetchall()
        return [date.fromisoformat(r["day_date"]) for r in rows]

    def get_upcoming_holidays(self, n: int = 5) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        today = date.today().isoformat()
        rows = conn.execute(
            "SELECT * FROM working_days WHERE day_type='holiday' AND day_date >= ? ORDER BY day_date LIMIT ?",
            (today, n),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_working_days_loaded(self) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM working_days WHERE day_type='working'"
        ).fetchone()
        return row["cnt"]

    # ------------------------------------------------------------------
    # Agent state (key-value store)
    # ------------------------------------------------------------------

    def set_state(self, key: str, value: str) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO agent_state (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, value, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()

    def get_state(self, key: str, default: str = "") -> str:
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM agent_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    # ------------------------------------------------------------------
    # Statistics helpers for dashboard
    # ------------------------------------------------------------------

    def total_spend(self) -> float:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COALESCE(SUM(price), 0) as total FROM bookings WHERE status='success'"
        ).fetchone()
        return float(row["total"])

    def booking_summary(self) -> Dict[str, int]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM bookings GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

