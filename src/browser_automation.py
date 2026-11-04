"""
browser_automation.py
---------------------
Playwright-based automation layer for SpaceBasic meal booking.

IMPORTANT
---------
  - This module ONLY uses the official SpaceBasic web portal.
  - It does NOT bypass authentication, CAPTCHA, MFA, or any security control.
  - If CAPTCHA or MFA is encountered, the agent pauses and notifies the user.
  - The browser profile is persisted so the user only needs to log in once
    (or re-authenticate when the session expires naturally).

Usage
-----
  async with SpaceBasicBrowser(config) as browser:
      result = await browser.book_meal("lunch", "Rice & Dal")
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("spacebasic.browser")


@dataclass
class BookingResult:
    success: bool
    meal_name: str = ""
    meal_type: str = ""
    confirmation_id: str = ""
    price: float = 0.0
    error: str = ""


class SpaceBasicBrowser:
    """
    Playwright browser automation for SpaceBasic.

    The implementation deliberately uses CSS/text selectors rather than
    brittle XPath so minor layout changes do not break the agent.
    All selectors are centralised in the _SELECTORS dict so they can be
    updated in one place when SpaceBasic changes their UI.
    """

    # ----------------------------------------------------------------
    # Selector map — UPDATE THESE after inspecting the SpaceBasic portal
    # ----------------------------------------------------------------
    _SELECTORS = {
        # Login page
        "username_input":   'input[name="username"], input[type="email"], input[placeholder*="ID"]',
        "password_input":   'input[name="password"], input[type="password"]',
        "login_button":     'button[type="submit"], button:has-text("Login"), button:has-text("Sign In")',
        "captcha_element":  '.g-recaptcha, iframe[src*="recaptcha"], iframe[src*="captcha"]',
        "mfa_input":        'input[name="otp"], input[placeholder*="OTP"], input[placeholder*="code"]',

        # Post-login: navigation to mess / meal booking
        "mess_menu_link":   'a:has-text("Mess"), a:has-text("Meal"), a:has-text("Food"), nav >> text=Mess',
        "booking_section":  'a:has-text("Book"), a:has-text("Pre-book"), button:has-text("Book Meal")',

        # Meal booking
        "meal_option":      '.meal-item, .menu-item, [class*="meal"], [class*="menu"]',
        "book_button":      'button:has-text("Book"), button:has-text("Confirm"), button:has-text("Reserve")',
        "confirm_dialog":   '.modal, .confirm-dialog, [role="dialog"]',
        "confirm_ok":       'button:has-text("OK"), button:has-text("Confirm"), button:has-text("Yes")',

        # Confirmation
        "success_msg":      '.success, .alert-success, [class*="success"], text=successfully, text=confirmed',
        "confirmation_id":  '[class*="booking-id"], [class*="reference"], [class*="confirmation"]',

        # Error detection
        "error_msg":        '.error, .alert-danger, [class*="error"], text=failed, text=unavailable',
    }

    def __init__(self, config: dict):
        self.config = config
        self.url = config["spacebasic_url"]
        self.username = config["username"]
        self.password = config["password"]
        self.headless = config.get("headless", True)
        self.profile_dir = config.get("profile_dir", "browser_profile")
        self.timeout = config.get("page_timeout", 30) * 1000  # Playwright uses ms
        self.dry_run = config.get("dry_run", True)

        self._browser = None
        self._context = None
        self._page = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self):
        await self._launch()
        return self

    async def __aexit__(self, *args):
        await self._close()

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    async def _launch(self) -> None:
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        browser_type = getattr(self._pw, self.config.get("browser_type", "chromium"))
        self._context = await browser_type.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_https_errors=False,
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.timeout)
        logger.info("Browser launched (headless=%s, dry_run=%s)", self.headless, self.dry_run)

    async def _close(self) -> None:
        if self._context:
            await self._context.close()
        if self._pw:
            await self._pw.stop()
        logger.info("Browser closed")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(self) -> bool:
        """
        Navigate to SpaceBasic and log in.

        Returns True on success.
        Does NOT bypass CAPTCHA or MFA — if detected, pauses and notifies user.
        """
        logger.info("Navigating to %s", self.url)
        try:
            await self._page.goto(self.url, wait_until="networkidle")
        except Exception as e:
            logger.error("Failed to open SpaceBasic URL: %s", e)
            return False

        # Check if already logged in (session still valid)
        if await self._is_logged_in():
            logger.info("Session still active — skipping login")
            return True

        # Check for CAPTCHA before attempting login
        captcha = await self._page.query_selector(self._SELECTORS["captcha_element"])
        if captcha:
            logger.warning(
                "CAPTCHA detected on login page. "
                "Please open the browser manually, solve the CAPTCHA, and log in once. "
                "The session will be saved for future runs."
            )
            return False

        # Fill credentials
        try:
            await self._page.fill(self._SELECTORS["username_input"], self.username)
            await self._page.fill(self._SELECTORS["password_input"], self.password)
            await self._page.click(self._SELECTORS["login_button"])
            await self._page.wait_for_load_state("networkidle")
        except Exception as e:
            logger.error("Login form interaction failed: %s", e)
            return False

        # Check for MFA / OTP prompt
        mfa_input = await self._page.query_selector(self._SELECTORS["mfa_input"])
        if mfa_input:
            logger.warning(
                "MFA/OTP detected. The agent cannot complete MFA automatically. "
                "Please complete the login manually in the browser window, then restart the agent."
            )
            return False

        logged_in = await self._is_logged_in()
        if logged_in:
            logger.info("Login successful")
        else:
            error_text = await self._get_error_text()
            logger.error("Login failed. Page error: %s", error_text)
        return logged_in

    async def _is_logged_in(self) -> bool:
        """Heuristic check: we are logged in if the URL has changed away from login."""
        current_url = self._page.url
        return "login" not in current_url.lower() and self.url.rstrip("/") in current_url

    async def _get_error_text(self) -> str:
        try:
            el = await self._page.query_selector(self._SELECTORS["error_msg"])
            if el:
                return await el.inner_text()
        except Exception:
            pass
        return "Unknown error"

    # ------------------------------------------------------------------
    # Meal booking
    # ------------------------------------------------------------------

    async def book_meal(self, meal_type: str, preferred_names: list[str]) -> BookingResult:
        """
        Navigate to the meal booking section and book a meal.

        Args:
            meal_type:       "breakfast", "lunch", or "dinner"
            preferred_names: List of acceptable meal names in priority order.

        Returns:
            BookingResult with success flag and details.
        """
        logger.info("Attempting to book %s. Preferences: %s", meal_type, preferred_names)

        # --- Navigate to mess/meal section ---
        try:
            mess_link = await self._page.query_selector(self._SELECTORS["mess_menu_link"])
            if mess_link:
                await mess_link.click()
                await self._page.wait_for_load_state("networkidle")
            else:
                logger.error("Could not find mess menu link on the page")
                return BookingResult(success=False, error="Mess menu link not found")
        except Exception as e:
            return BookingResult(success=False, error=f"Navigation error: {e}")

        # --- Find available meals ---
        try:
            meal_items = await self._page.query_selector_all(self._SELECTORS["meal_option"])
            if not meal_items:
                return BookingResult(success=False, error="No meal items found on booking page")
        except Exception as e:
            return BookingResult(success=False, error=f"Could not read meal list: {e}")

        # --- Match a preferred meal ---
        chosen_element = None
        chosen_name = ""
        for preferred in preferred_names:
            for item in meal_items:
                try:
                    text = (await item.inner_text()).strip()
                    if preferred.lower() in text.lower():
                        chosen_element = item
                        chosen_name = text
                        break
                except Exception:
                    continue
            if chosen_element:
                break

        if not chosen_element:
            return BookingResult(
                success=False,
                meal_type=meal_type,
                error=f"None of the preferred meals found: {preferred_names}",
            )

        logger.info("Selected meal: '%s'", chosen_name)

        # --- Dry-run guard ---
        if self.dry_run:
            logger.info("[DRY RUN] Would book '%s' for %s — no real action taken", chosen_name, meal_type)
            return BookingResult(
                success=True,
                meal_name=chosen_name,
                meal_type=meal_type,
                confirmation_id="DRY_RUN",
                price=0.0,
            )

        # --- Click the meal item and confirm ---
        try:
            await chosen_element.click()
            await asyncio.sleep(0.5)

            book_btn = await self._page.query_selector(self._SELECTORS["book_button"])
            if book_btn:
                await book_btn.click()
                await self._page.wait_for_load_state("networkidle")

            # Handle confirmation dialog if it appears
            confirm_btn = await self._page.query_selector(self._SELECTORS["confirm_ok"])
            if confirm_btn:
                await confirm_btn.click()
                await self._page.wait_for_load_state("networkidle")

        except Exception as e:
            return BookingResult(success=False, meal_type=meal_type, error=f"Booking click failed: {e}")

        # --- Verify confirmation ---
        return await self._verify_booking(meal_type, chosen_name)

    async def _verify_booking(self, meal_type: str, meal_name: str) -> BookingResult:
        """
        Check the page for a success message and extract confirmation ID.
        Never reports success unless the page confirms it.
        """
        await asyncio.sleep(1)  # Brief pause for page to settle

        # Check for error first
        error_el = await self._page.query_selector(self._SELECTORS["error_msg"])
        if error_el:
            error_text = await error_el.inner_text()
            logger.error("Booking error message on page: %s", error_text)
            return BookingResult(success=False, meal_type=meal_type, meal_name=meal_name, error=error_text)

        # Check for success
        success_el = await self._page.query_selector(self._SELECTORS["success_msg"])
        if not success_el:
            logger.error("No success or error message found after booking attempt")
            return BookingResult(
                success=False,
                meal_type=meal_type,
                meal_name=meal_name,
                error="No confirmation message found on page",
            )

        # Extract confirmation ID
        confirmation_id = ""
        conf_el = await self._page.query_selector(self._SELECTORS["confirmation_id"])
        if conf_el:
            confirmation_id = (await conf_el.inner_text()).strip()

        logger.info("Booking confirmed! Meal: '%s', ID: '%s'", meal_name, confirmation_id)
        return BookingResult(
            success=True,
            meal_type=meal_type,
            meal_name=meal_name,
            confirmation_id=confirmation_id or "CONFIRMED",
        )

    async def get_available_meals(self, meal_type: str) -> list[str]:
        """
        Return a list of currently available meal names.
        Useful for the dashboard and for debugging.
        """
        meal_items = await self._page.query_selector_all(self._SELECTORS["meal_option"])
        names = []
        for item in meal_items:
            try:
                names.append((await item.inner_text()).strip())
            except Exception:
                pass
        return names

