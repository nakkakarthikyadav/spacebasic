"""
scheduler.py
------------
APScheduler-based daily scheduler for the SpaceBasic booking agent.

Runs the booking cycle at a user-configured time every day.
Respects the Asia/Kolkata timezone.
Supports pause / resume / stop from the dashboard via agent_state DB flags.
"""

import logging
import signal
import sys
from datetime import datetime

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.database import Database
from src.booking_agent import BookingAgent
from src.notifier import Notifier

logger = logging.getLogger("spacebasic.scheduler")

TIMEZONE = pytz.timezone("Asia/Kolkata")


class AgentScheduler:
    """Wraps APScheduler with pause/resume/stop controls."""

    def __init__(self, config: dict, db: Database, agent: BookingAgent, notifier: Notifier):
        self.config = config
        self.db = db
        self.agent = agent
        self.notifier = notifier

        booking_time: str = config.get("agent", {}).get("booking_time", "07:30")
        hour, minute = booking_time.split(":")
        self._cron_hour = int(hour)
        self._cron_minute = int(minute)

        self._scheduler = BlockingScheduler(timezone=TIMEZONE)
        self._job_id = "daily_meal_booking"
        self._setup_jobs()
        self._setup_signal_handlers()

    # ------------------------------------------------------------------
    # Job setup
    # ------------------------------------------------------------------

    def _setup_jobs(self) -> None:
        # Main daily booking job
        self._scheduler.add_job(
            func=self._run_booking_job,
            trigger=CronTrigger(
                hour=self._cron_hour,
                minute=self._cron_minute,
                timezone=TIMEZONE,
            ),
            id=self._job_id,
            name="Daily Meal Booking",
            max_instances=1,          # Never run twice simultaneously
            misfire_grace_time=600,   # Run if missed by up to 10 min
            replace_existing=True,
        )

        # Daily summary job (evening)
        summary_time = self.config.get("notifications", {}).get("daily_summary_time", "20:00")
        s_hour, s_minute = summary_time.split(":")
        self._scheduler.add_job(
            func=self._send_upcoming_summary,
            trigger=CronTrigger(
                hour=int(s_hour),
                minute=int(s_minute),
                timezone=TIMEZONE,
            ),
            id="evening_summary",
            name="Evening Booking Summary",
            max_instances=1,
            misfire_grace_time=300,
            replace_existing=True,
        )

        logger.info(
            "Scheduler configured: booking at %02d:%02d IST, summary at %s IST",
            self._cron_hour, self._cron_minute, summary_time,
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _run_booking_job(self) -> None:
        """Called by APScheduler at the configured booking time."""
        # Check dashboard pause flag
        paused = self.db.get_state("agent_paused", "false").lower() == "true"
        if paused:
            logger.info("Agent is paused by dashboard — skipping today's booking")
            self.notifier.send("⏸️ Agent is paused — skipping today's booking.", level="info")
            return

        logger.info("Scheduler trigger: running booking cycle at %s", datetime.now(TIMEZONE))
        try:
            self.agent.run_booking_cycle()
        except Exception as e:
            logger.exception("Booking cycle crashed: %s", e)
            self.notifier.send(f"💥 Booking cycle crashed: {e}", level="error")

    def _send_upcoming_summary(self) -> None:
        """Send a preview of the next 7 days."""
        upcoming = self.db.get_upcoming_working_days(n=5)
        holidays = self.db.get_upcoming_holidays(n=3)
        lines = ["📅 Upcoming schedule:"]
        for d in upcoming:
            lines.append(f"   ✅ {d.strftime('%a %d %b')} — working day")
        for h in holidays:
            lines.append(f"   🎉 {h['day_date']} — {h.get('description', 'Holiday')}")
        self.notifier.send("\n".join(lines), level="info", is_summary=True)

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start(self) -> None:
        logger.info("Agent scheduler starting. Press Ctrl+C to stop.")
        self.notifier.send("🚀 SpaceBasic Booking Agent started.", level="info")
        self._scheduler.start()

    def stop(self) -> None:
        logger.info("Stopping scheduler...")
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

    # ------------------------------------------------------------------
    # Signal handling (graceful shutdown on Ctrl+C / SIGTERM)
    # ------------------------------------------------------------------

    def _setup_signal_handlers(self) -> None:
        def _handler(sig, frame):
            logger.info("Signal %s received — shutting down gracefully", sig)
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    # ------------------------------------------------------------------
    # Immediate run (for testing / manual trigger)
    # ------------------------------------------------------------------

    def run_now(self) -> dict:
        """Trigger the booking cycle immediately (bypasses schedule)."""
        logger.info("Manual trigger: running booking cycle now")
        return self.agent.run_booking_cycle()

