"""
main.py
-------
Entry point for the SpaceBasic Meal Booking Agent.

Usage
-----
  # Start the scheduler (runs daily at configured time)
  python main.py

  # Run a booking right now (for testing)
  python main.py --run-now

  # Parse/reload the college calendar
  python main.py --parse-calendar

  # Launch the dashboard (in a separate terminal)
  streamlit run src/dashboard.py
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# ── Bootstrap: ensure project root is on path ─────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.logger_setup import setup_logger
from src.config_loader import load_config
from src.database import Database
from src.notifier import Notifier
from src.booking_agent import BookingAgent
from src.scheduler import AgentScheduler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SpaceBasic Meal Booking Agent"
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run a booking cycle immediately and exit",
    )
    parser.add_argument(
        "--parse-calendar",
        action="store_true",
        help="Parse / reload the college calendar and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Override config dry_run=true (safe mode)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load config ───────────────────────────────────────────────────
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # ── Logging ───────────────────────────────────────────────────────
    log_cfg = config.get("logging", {})
    logger = setup_logger(
        log_dir=log_cfg.get("log_dir", "logs"),
        level=log_cfg.get("level", "INFO"),
        max_bytes=log_cfg.get("max_log_size_mb", 10) * 1024 * 1024,
        backup_count=log_cfg.get("backup_count", 5),
    )

    # ── Override dry_run from CLI flag ────────────────────────────────
    if args.dry_run:
        config.setdefault("agent", {})["dry_run"] = True
        logger.info("CLI flag --dry-run: dry_run forced to True")

    dry_run = config.get("agent", {}).get("dry_run", True)
    if dry_run:
        logger.warning("=" * 60)
        logger.warning("DRY RUN MODE — no real bookings will be made")
        logger.warning("Set agent.dry_run: false in config.yaml to go live")
        logger.warning("Also set LIVE_BOOKING_ENABLED=true in .env")
        logger.warning("=" * 60)

    # ── Database ──────────────────────────────────────────────────────
    db = Database()
    db.init()

    # ── Components ───────────────────────────────────────────────────
    notifier = Notifier(config)
    agent = BookingAgent(config, db, notifier)

    # ── Calendar parse mode ───────────────────────────────────────────
    if args.parse_calendar:
        _run_calendar_parse(config, db, logger)
        return

    # ── Immediate run mode ────────────────────────────────────────────
    if args.run_now:
        logger.info("--run-now flag: triggering booking cycle immediately")
        result = agent.run_booking_cycle()
        logger.info("Booking result: %s", result)
        return

    # ── Scheduler mode (default) ──────────────────────────────────────
    scheduler = AgentScheduler(config, db, agent, notifier)

    # Warn if calendar not loaded
    if db.count_working_days_loaded() == 0:
        logger.warning(
            "No working days in database! "
            "Upload your college calendar via the dashboard or run: python main.py --parse-calendar"
        )

    scheduler.start()  # Blocks until Ctrl+C or SIGTERM


def _run_calendar_parse(config: dict, db: Database, logger: logging.Logger) -> None:
    from src.calendar_parser import CalendarParser
    from datetime import date

    cal_cfg = config.get("calendar", {})
    file_path = cal_cfg.get("file_path", "data/calendar/college_calendar.pdf")

    logger.info("Parsing calendar: %s", file_path)
    parser = CalendarParser(
        academic_start=date.fromisoformat(cal_cfg.get("academic_year_start", "2025-07-01")),
        academic_end=date.fromisoformat(cal_cfg.get("academic_year_end", "2026-05-31")),
        saturday_working=cal_cfg.get("saturday_working", False),
        sunday_working=cal_cfg.get("sunday_working", False),
    )
    days = parser.parse(file_path)
    if not days:
        logger.error("Calendar parsing returned no results. Check the file path and format.")
        return

    for d in days:
        db.upsert_working_day(d["date"], d["day_type"], d.get("description", ""), file_path)

    working = sum(1 for d in days if d["day_type"] == "working")
    holidays = sum(1 for d in days if d["day_type"] in ("holiday", "vacation"))
    weekends = sum(1 for d in days if d["day_type"] == "weekend")
    logger.info(
        "Calendar loaded: %d working days, %d holidays/vacations, %d weekends",
        working, holidays, weekends,
    )


if __name__ == "__main__":
    main()

