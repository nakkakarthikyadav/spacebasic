"""
booking_agent.py
----------------
Orchestration layer: decides whether to book, which meal to book,
calls the browser automation, writes results to DB, and triggers notifications.

This is the "brain" of the agent. The scheduler calls run_booking_cycle()
once per day.
"""

import asyncio
import logging
from datetime import date
from typing import Optional

from src.database import Database
from src.browser_automation import SpaceBasicBrowser, BookingResult
from src.notifier import Notifier

logger = logging.getLogger("spacebasic.agent")

MEAL_TYPES = ["breakfast", "lunch", "dinner"]


class BookingAgent:
    """
    Orchestrates the daily meal booking workflow.

    Standing authorisation: the user authorises the agent once during setup.
    The agent books only the meal types / budget limits in config — no more.
    """

    def __init__(self, config: dict, db: Database, notifier: Notifier):
        self.config = config
        self.db = db
        self.notifier = notifier
        self.prefs = config.get("meal_preferences", {})
        self.dry_run = config.get("agent", {}).get("dry_run", True)

    # ------------------------------------------------------------------
    # Main entry point — called by scheduler once per day
    # ------------------------------------------------------------------

    def run_booking_cycle(self) -> dict:
        """
        Synchronous entry point. Internally runs the async cycle.
        Returns a summary dict.
        """
        return asyncio.run(self._async_booking_cycle())

    async def _async_booking_cycle(self) -> dict:
        today = date.today()
        summary = {"date": today.isoformat(), "booked": [], "skipped": [], "failed": []}

        logger.info("=== Booking cycle started for %s ===", today)

        # 1. Check whether today is a working day
        if not self.db.is_working_day(today):
            day_info = self.db.get_day_type(today)
            reason = day_info["description"] if day_info else "not in calendar"
            day_type = day_info["day_type"] if day_info else "unknown"
            logger.info("Skipping %s — %s (%s)", today, day_type, reason)
            self.notifier.send(
                f"📅 {today}: No booking — {day_type}. {reason}",
                level="info",
            )
            return summary

        # 2. Determine which meals to book
        meals_to_book = self._get_meals_to_book(today)
        if not meals_to_book:
            logger.info("All meals already booked or none configured for today.")
            return summary

        # 3. Open browser and execute bookings
        browser_config = self._build_browser_config()
        try:
            async with SpaceBasicBrowser(browser_config) as browser:
                logged_in = await browser.login()
                if not logged_in:
                    msg = "SpaceBasic login failed. Please check credentials or solve CAPTCHA/MFA manually."
                    logger.error(msg)
                    self.notifier.send(f"🔐 {msg}", level="error")
                    for meal_type in meals_to_book:
                        self.db.record_booking(
                            today, meal_type, "failed", error_message="Login failed"
                        )
                    summary["failed"].extend(meals_to_book)
                    return summary

                for meal_type in meals_to_book:
                    result = await self._book_single_meal(browser, today, meal_type)
                    self._handle_result(today, meal_type, result, summary)

        except Exception as e:
            logger.exception("Unexpected error during booking cycle: %s", e)
            self.notifier.send(f"💥 Unexpected agent error: {e}", level="error")

        # 4. Send daily summary
        self._send_daily_summary(summary)
        logger.info("=== Booking cycle complete: %s ===", summary)
        return summary

    # ------------------------------------------------------------------
    # Decide what to book
    # ------------------------------------------------------------------

    def _get_meals_to_book(self, today: date) -> list[str]:
        """Return list of meal types that still need to be booked today."""
        to_book = []
        for meal_type in MEAL_TYPES:
            config_key = f"book_{meal_type}"
            if not self.prefs.get(config_key, False):
                logger.debug("Meal type '%s' disabled in config — skipping", meal_type)
                continue
            if self.db.is_booked(today, meal_type):
                logger.info("'%s' already booked for %s — skipping (duplicate guard)", meal_type, today)
                continue
            to_book.append(meal_type)
        return to_book

    def _get_preferences_for(self, meal_type: str) -> list[str]:
        key = f"{meal_type}_preferences"
        prefs = self.prefs.get(key, [])
        return prefs if prefs else []  # empty = accept any

    def _check_budget(self, price: float, meal_type: str) -> bool:
        max_price_key = f"max_{meal_type}_price"
        max_price = self.prefs.get(max_price_key, 0)
        max_daily = self.prefs.get("max_daily_budget", 0)
        if max_price and price > max_price:
            return False
        if max_daily:
            today_spend = sum(b["price"] or 0 for b in self.db.get_today_bookings() if b["status"] == "success")
            if today_spend + price > max_daily:
                return False
        return True

    # ------------------------------------------------------------------
    # Book a single meal
    # ------------------------------------------------------------------

    async def _book_single_meal(
        self, browser: SpaceBasicBrowser, today: date, meal_type: str
    ) -> BookingResult:
        prefs = self._get_preferences_for(meal_type)
        allow_alt = self.prefs.get("allow_alternative", True)

        # Build list of acceptable names
        acceptable = list(prefs)
        if allow_alt:
            # If alternatives allowed, pass an empty fallback (any available)
            acceptable_for_browser = acceptable if acceptable else ["__any__"]
        else:
            acceptable_for_browser = acceptable

        logger.info("Booking %s. Acceptable meals: %s", meal_type, acceptable_for_browser)
        return await browser.book_meal(meal_type, acceptable_for_browser)

    # ------------------------------------------------------------------
    # Handle and persist result
    # ------------------------------------------------------------------

    def _handle_result(
        self, today: date, meal_type: str, result: BookingResult, summary: dict
    ) -> None:
        if result.success:
            self.db.record_booking(
                today,
                meal_type,
                status="success",
                meal_name=result.meal_name,
                confirmation_id=result.confirmation_id,
                price=result.price,
            )
            summary["booked"].append({"meal_type": meal_type, "meal_name": result.meal_name})
            tag = "[DRY RUN] " if self.dry_run else ""
            self.notifier.send(
                f"✅ {tag}{meal_type.title()} booked: {result.meal_name} (ID: {result.confirmation_id})",
                level="success",
            )
        else:
            self.db.record_booking(
                today, meal_type, status="failed", error_message=result.error
            )
            summary["failed"].append({"meal_type": meal_type, "error": result.error})
            self.notifier.send(
                f"❌ {meal_type.title()} booking failed: {result.error}",
                level="error",
            )

    # ------------------------------------------------------------------
    # Summary notification
    # ------------------------------------------------------------------

    def _send_daily_summary(self, summary: dict) -> None:
        lines = [f"📋 Daily Booking Summary — {summary['date']}"]
        if summary["booked"]:
            lines.append("✅ Booked:")
            for b in summary["booked"]:
                lines.append(f"   • {b['meal_type']}: {b['meal_name']}")
        if summary["failed"]:
            lines.append("❌ Failed:")
            for f in summary["failed"]:
                lines.append(f"   • {f['meal_type']}: {f['error']}")
        if summary["skipped"]:
            lines.append("⏭️ Skipped: " + ", ".join(summary["skipped"]))
        self.notifier.send("\n".join(lines), level="info", is_summary=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_browser_config(self) -> dict:
        import os
        return {
            "spacebasic_url": os.environ.get("SPACEBASIC_URL", ""),
            "username": os.environ.get("SPACEBASIC_USERNAME", ""),
            "password": os.environ.get("SPACEBASIC_PASSWORD", ""),
            "headless": self.config.get("browser", {}).get("headless", True),
            "profile_dir": self.config.get("browser", {}).get("profile_dir", "browser_profile"),
            "browser_type": self.config.get("browser", {}).get("browser_type", "chromium"),
            "page_timeout": self.config.get("browser", {}).get("page_timeout", 30),
            "dry_run": self.dry_run,
        }

