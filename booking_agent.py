"""
booking_agent.py  — portal.spacebasic.com specific
----------------------------------------------------
Books meals at: https://portal.spacebasic.com/module/messmanager/bookings

SpaceBasic portal facts (confirmed):
  - Login: Email or Mobile + OTP (NOT password-based)
  - Booking URL: /module/messmanager/bookings
  - Meal types: Breakfast / Lunch / Dinner (opt-in/opt-out model)
  - Session: JWT token stored in browser localStorage / cookies

Because SpaceBasic uses OTP login, this agent ALWAYS uses the
Chrome session copy approach — you log in once in Chrome, we
copy the session, and the agent reuses it. No OTP needed again.

HOW TO UPDATE SELECTORS
  1. Log in to portal.spacebasic.com in Chrome
  2. Press F12 → Elements tab
  3. Click the inspect cursor and click on the element you want
  4. Note the class / id / text and update SELECTORS below
  OR
  Run: python -m playwright codegen https://portal.spacebasic.com/module/messmanager/bookings
"""

import asyncio
import logging
import os
from datetime import date
from dataclasses import dataclass
from typing import Optional

import yaml
from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger("spacebasic.booking")

# ── URLs ──────────────────────────────────────────────────────────────
BASE_URL    = "https://portal.spacebasic.com"
LOGIN_URL   = "https://portal.spacebasic.com"          # Root redirects to login if not authed
BOOKING_URL = "https://portal.spacebasic.com/module/messmanager/bookings"

# ── Selectors for portal.spacebasic.com ──────────────────────────────
# These are based on known SpaceBasic portal patterns.
# If any selector breaks, inspect the page with F12 and update here.
SELECTORS = {
    # ── Session validity ───────────────────────────────────────────
    # Present when logged in (dashboard / sidebar navigation)
    "logged_in":     'nav, .sidebar, [class*="navbar"], [class*="dashboard"], .user-name, .profile',
    # Present when NOT logged in (login form)
    "login_form":    'input[type="email"], input[placeholder*="Email"], input[placeholder*="Mobile"], form',

    # ── Booking page ───────────────────────────────────────────────
    # The page title / heading on the booking page
    "page_heading":  'h1, h2, h3, [class*="heading"], [class*="title"]',

    # Individual booking cards (one card per meal slot per day)
    # SpaceBasic typically renders meal slots as cards/rows
    "meal_cards":    '[class*="booking-card"], [class*="meal-card"], [class*="slot-card"], '
                     '[class*="mess-card"], .card, [class*="food-item"], tr[class*="meal"]',

    # Text labels inside a meal card that identify meal type
    "meal_type_text": '[class*="meal-type"], [class*="slot-type"], [class*="category"], '
                      '.meal-label, .slot-label, td.meal-type',

    # Date display inside a meal card
    "meal_date_text": '[class*="date"], .date-label, td.date',

    # ── Booking action buttons ─────────────────────────────────────
    # "Book" / "Opt In" button inside a meal card
    "book_btn":      'button:has-text("Book"), button:has-text("Opt In"), '
                     'button:has-text("Opt-in"), button:has-text("Pre Book"), '
                     'button:has-text("Add"), [class*="book-btn"], [class*="opt-btn"]',

    # Confirmation / submit button in any dialog that appears
    "confirm_btn":   'button:has-text("Confirm"), button:has-text("OK"), '
                     'button:has-text("Yes"), button:has-text("Submit"), '
                     '.confirm-btn, [class*="confirm"]',

    # Cancel / remove button (to detect if already booked)
    "cancel_btn":    'button:has-text("Cancel"), button:has-text("Opt Out"), '
                     'button:has-text("Remove"), [class*="cancel-btn"], [class*="opted"]',

    # ── Result detection ───────────────────────────────────────────
    "success_toast":  '.toast-success, .alert-success, [class*="success"], '
                      'text=successfully, text=booked, text=confirmed',
    "error_toast":    '.toast-error, .alert-danger, .alert-error, [class*="error"], '
                      'text=failed, text=error, text=unavailable',
    "booking_ref":    '[class*="booking-id"], [class*="reference"], [class*="token"], '
                      '[class*="qr"], [class*="confirmation-id"]',

    # ── Status indicator ───────────────────────────────────────────
    # SpaceBasic shows a badge/tag when a meal is already booked
    "booked_badge":  '[class*="booked"], [class*="opted-in"], [class*="active"], '
                     '.badge-success, text=Booked, text=Opted In',
}

MEAL_KEYWORDS = {
    "breakfast": ["breakfast", "morning", "सुबह", "tiffin", "snack"],
    "lunch":     ["lunch", "afternoon", "दोपहर", "meal", "दोप"],
    "dinner":    ["dinner", "evening", "रात", "night", "supper"],
}


@dataclass
class BookingResult:
    success: bool
    meal_type: str = ""
    meal_name: str = ""
    confirmation_id: str = ""
    price: float = 0.0
    error: str = ""
    dry_run: bool = False
    already_booked: bool = False


def load_config(path="config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


class SpaceBasicBooker:
    """
    Books meals on portal.spacebasic.com using your saved Chrome session.
    Direct navigation to the booking URL — no login step needed if session is valid.
    """

    def __init__(self, config: dict):
        self.cfg = config
        self.base_url    = os.environ.get("SPACEBASIC_URL", BASE_URL).rstrip("/")
        self.booking_url = os.environ.get("SPACEBASIC_BOOKING_URL", BOOKING_URL)
        self.profile_dir = config["browser"]["playwright_profile"]
        self.headless    = config["browser"].get("headless", True)
        self.timeout_ms  = config["browser"].get("page_timeout", 30) * 1000
        self.dry_run     = (
            config["agent"].get("dry_run", True)
            or os.environ.get("LIVE_BOOKING_ENABLED", "false").lower() != "true"
        )

    # ── Public API ─────────────────────────────────────────────────────

    async def book(self, meal_type: str, preferences: list[str]) -> BookingResult:
        """Book a meal. Returns BookingResult."""
        async with async_playwright() as pw:
            context = await self._open_context(pw)
            page = await context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                result = await self._do_booking(page, meal_type, preferences)
            except Exception as e:
                logger.exception("Booking error: %s", e)
                result = BookingResult(False, meal_type=meal_type, error=str(e))
            finally:
                await context.close()
        return result

    async def get_status(self) -> dict:
        """Check session validity + what's booked today."""
        async with async_playwright() as pw:
            context = await self._open_context(pw)
            page = await context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                await page.goto(self.booking_url, wait_until="networkidle")
                logged_in = await self._is_logged_in(page)
                booked_meals = []
                if logged_in:
                    booked_meals = await self._get_already_booked(page)
                return {
                    "logged_in": logged_in,
                    "url": page.url,
                    "booked_today": booked_meals,
                }
            except Exception as e:
                return {"logged_in": False, "error": str(e)}
            finally:
                await context.close()

    # ── Core booking flow ──────────────────────────────────────────────

    async def _do_booking(self, page: Page, meal_type: str, preferences: list[str]) -> BookingResult:
        # 1. Go directly to booking page (session cookie handles auth)
        logger.info("Navigating to booking page: %s", self.booking_url)
        try:
            await page.goto(self.booking_url, wait_until="networkidle")
        except Exception as e:
            return BookingResult(False, meal_type=meal_type, error=f"Cannot open booking page: {e}")

        # 2. Verify session is still valid
        if not await self._is_logged_in(page):
            return BookingResult(
                False, meal_type=meal_type,
                error=(
                    "⚠️ Session expired!\n"
                    "Please log in to portal.spacebasic.com in Google Chrome, "
                    "then run: python session_helper.py"
                ),
            )

        logger.info("Session valid ✅ — on booking page")

        # 3. Wait for booking cards to load
        try:
            await page.wait_for_selector(SELECTORS["meal_cards"], timeout=10000)
        except Exception:
            return BookingResult(
                False, meal_type=meal_type,
                error="Booking cards not found on page. Run with headless:false to debug."
            )

        # 4. Find the meal card for today + requested meal_type
        card, card_text = await self._find_meal_card(page, meal_type)
        if card is None:
            # Try to get what IS available for a better error message
            all_cards = await page.query_selector_all(SELECTORS["meal_cards"])
            all_texts = []
            for c in all_cards[:5]:
                try:
                    all_texts.append((await c.inner_text()).strip()[:60])
                except Exception:
                    pass
            return BookingResult(
                False, meal_type=meal_type,
                error=f"No {meal_type} card found for today. Visible cards: {all_texts}"
            )

        # 5. Check if already booked (Cancel/Opted-in button visible)
        already = await self._is_already_booked(card)
        if already:
            logger.info("%s is already booked for today.", meal_type)
            return BookingResult(
                True, meal_type=meal_type, meal_name=card_text,
                confirmation_id="ALREADY_BOOKED", already_booked=True
            )

        logger.info("Found %s card: '%s'", meal_type, card_text[:60])

        # 6. DRY RUN guard — never click in test mode
        if self.dry_run:
            logger.info("[DRY RUN] Would book %s — '%s'", meal_type, card_text[:60])
            return BookingResult(
                True, meal_type=meal_type, meal_name=card_text[:60],
                confirmation_id="DRY-RUN", dry_run=True
            )

        # 7. Click Book button
        try:
            book_btn = card.locator(SELECTORS["book_btn"]).first
            if await book_btn.count() == 0:
                # Try finding button relative to the card
                book_btn = page.locator(SELECTORS["book_btn"]).first
            await book_btn.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.8)
        except Exception as e:
            return BookingResult(False, meal_type=meal_type, error=f"Could not click Book button: {e}")

        # 8. Handle confirmation dialog if it appears
        try:
            confirm = page.locator(SELECTORS["confirm_btn"]).first
            if await confirm.is_visible(timeout=3000):
                await confirm.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(0.8)
        except Exception:
            pass  # No dialog — that's fine

        # 9. Verify — NEVER report success without page confirming
        return await self._verify_booking(page, meal_type, card_text)

    # ── Helper: find the right meal card ──────────────────────────────

    async def _find_meal_card(self, page: Page, meal_type: str):
        """
        Find the card on the booking page that corresponds to:
          - Today's date
          - The requested meal_type (breakfast / lunch / dinner)

        Returns (element, text) or (None, "").
        SpaceBasic typically shows cards for the current day prominently.
        """
        today_str = date.today().strftime("%d")   # Day of month for matching
        keywords = MEAL_KEYWORDS.get(meal_type, [meal_type])

        all_cards = await page.query_selector_all(SELECTORS["meal_cards"])
        logger.debug("Found %d meal cards on page", len(all_cards))

        for card in all_cards:
            try:
                text = (await card.inner_text()).strip().lower()
                # Match meal type keyword
                if any(kw in text for kw in keywords):
                    # Prefer cards that also mention today's date
                    if today_str in text or len(all_cards) <= 3:
                        full_text = (await card.inner_text()).strip()
                        logger.debug("Matched card for %s: %s", meal_type, full_text[:80])
                        return card, full_text
            except Exception:
                continue

        # Fallback: if only one card per meal type shown, return first keyword match
        for card in all_cards:
            try:
                text = (await card.inner_text()).strip().lower()
                if any(kw in text for kw in keywords):
                    full_text = (await card.inner_text()).strip()
                    return card, full_text
            except Exception:
                continue

        return None, ""

    async def _is_already_booked(self, card) -> bool:
        """Return True if a cancel/opted-in button is visible on this card."""
        try:
            badge = card.locator(SELECTORS["booked_badge"]).first
            cancel = card.locator(SELECTORS["cancel_btn"]).first
            return (await badge.count() > 0) or (await cancel.count() > 0)
        except Exception:
            return False

    async def _get_already_booked(self, page: Page) -> list[str]:
        """Return list of meal types that are already booked today."""
        booked = []
        for meal_type in ["breakfast", "lunch", "dinner"]:
            card, _ = await self._find_meal_card(page, meal_type)
            if card and await self._is_already_booked(card):
                booked.append(meal_type)
        return booked

    # ── Helper: verify booking result ─────────────────────────────────

    async def _verify_booking(self, page: Page, meal_type: str, card_text: str) -> BookingResult:
        """
        Check the page for a success toast/alert.
        ONLY returns success=True if the page explicitly confirms it.
        """
        await asyncio.sleep(1.5)

        # Check for error first
        err_el = page.locator(SELECTORS["error_toast"]).first
        if await err_el.count() > 0:
            try:
                err_text = (await err_el.inner_text()).strip()
            except Exception:
                err_text = "Booking failed (error element found)"
            logger.error("Booking error on page: %s", err_text)
            return BookingResult(False, meal_type=meal_type, error=err_text)

        # Check for success
        ok_el = page.locator(SELECTORS["success_toast"]).first
        if await ok_el.count() == 0:
            # Last resort: check if Cancel button appeared (means booking went through)
            card, _ = await self._find_meal_card(page, meal_type)
            if card and await self._is_already_booked(card):
                return BookingResult(
                    True, meal_type=meal_type, meal_name=card_text[:60],
                    confirmation_id="CONFIRMED"
                )
            return BookingResult(
                False, meal_type=meal_type,
                error="No confirmation found on page. Booking may have failed."
            )

        # Extract booking reference if shown
        ref_id = ""
        ref_el = page.locator(SELECTORS["booking_ref"]).first
        if await ref_el.count() > 0:
            try:
                ref_id = (await ref_el.inner_text()).strip()
            except Exception:
                pass

        logger.info("✅ %s booked! Ref: %s", meal_type, ref_id or "CONFIRMED")
        return BookingResult(
            True, meal_type=meal_type, meal_name=card_text[:60],
            confirmation_id=ref_id or "CONFIRMED"
        )

    # ── Helper: session check ──────────────────────────────────────────

    async def _is_logged_in(self, page: Page) -> bool:
        """Return True if we are on an authenticated page (not login form)."""
        current = page.url
        # Redirected to login = not logged in
        if "/login" in current or current.rstrip("/") == self.base_url:
            login_form = page.locator(SELECTORS["login_form"]).first
            if await login_form.count() > 0:
                return False
        # Check for navigation/dashboard elements
        nav = page.locator(SELECTORS["logged_in"]).first
        return await nav.count() > 0

    async def _open_context(self, pw) -> BrowserContext:
        """Open Playwright context with persisted Chrome session."""
        return await pw.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            ignore_https_errors=False,
        )
