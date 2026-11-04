"""
session_helper.py
-----------------
Copies your existing Chrome login session (cookies) into the Playwright
browser profile so the agent is already logged in to SpaceBasic.

You only need to run this ONCE after logging in to SpaceBasic in Chrome.
After that, the Playwright session stays valid until SpaceBasic expires it.

Usage
-----
  python session_helper.py          # copy Chrome session → browser_profile/
  python session_helper.py --check  # check if session is still valid
"""

import os
import sys
import shutil
import logging
import argparse
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv(".env", override=False)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("session_helper")


def load_config(path="config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def copy_chrome_session(cfg: dict) -> bool:
    """
    Copy the Chrome Default profile into browser_profile/ so Playwright
    can load the existing SpaceBasic session.

    Chrome MUST be closed before running this, otherwise the profile
    files may be locked.
    """
    chrome_profile_root = Path(cfg["browser"]["chrome_profile_path"])
    chrome_profile_name = cfg["browser"].get("chrome_profile_name", "Default")
    chrome_profile_dir  = chrome_profile_root / chrome_profile_name

    playwright_profile = Path(cfg["browser"]["playwright_profile"])

    if not chrome_profile_dir.exists():
        logger.error("Chrome profile not found at: %s", chrome_profile_dir)
        logger.error(
            "Make sure Chrome is installed and you have logged into SpaceBasic at least once."
        )
        return False

    # Check if Chrome is running (profile will be locked if it is)
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            if "chrome" in proc.info["name"].lower():
                logger.warning(
                    "Chrome is currently running! Close Chrome first, "
                    "then re-run this script to copy the session."
                )
                return False
    except ImportError:
        logger.warning("psutil not installed — cannot check if Chrome is running. "
                       "Make sure Chrome is closed before continuing.")

    # Copy only the essential session files (cookies, local storage)
    # We don't copy the whole profile (too large); just the key files
    playwright_profile.mkdir(parents=True, exist_ok=True)

    essential_files = [
        "Cookies",
        "Cookies-journal",
        "Local State",
        "Preferences",
        "Web Data",
    ]
    essential_dirs = [
        "Local Storage",
        "Session Storage",
        "IndexedDB",
    ]

    copied = 0
    for fname in essential_files:
        src = chrome_profile_dir / fname
        dst = playwright_profile / fname
        if src.exists():
            try:
                shutil.copy2(src, dst)
                copied += 1
                logger.info("Copied: %s", fname)
            except Exception as e:
                logger.warning("Could not copy %s: %s", fname, e)

    for dname in essential_dirs:
        src = chrome_profile_dir / dname
        dst = playwright_profile / dname
        if src.exists():
            try:
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                copied += 1
                logger.info("Copied directory: %s", dname)
            except Exception as e:
                logger.warning("Could not copy %s: %s", dname, e)

    if copied == 0:
        logger.error("Nothing was copied. Check that Chrome profile path is correct.")
        return False

    logger.info("Session copied successfully! (%d items)", copied)
    logger.info("Playwright profile: %s", playwright_profile.resolve())
    return True


BOOKING_URL = "https://portal.spacebasic.com/module/messmanager/bookings"


async def check_session_valid(cfg: dict) -> bool:
    """
    Open the SpaceBasic booking page directly in Playwright.
    If session is valid, the booking page loads.
    If not, it redirects to the login form.
    """
    from playwright.async_api import async_playwright

    # Go straight to booking page — if session is expired we'll land on login
    url = os.environ.get("SPACEBASIC_BOOKING_URL", BOOKING_URL)

    profile_dir = cfg["browser"]["playwright_profile"]

    async with async_playwright() as pw:
        browser_type = getattr(pw, cfg["browser"].get("browser_type", "chromium") if "browser_type" in cfg.get("browser", {}) else "chromium")
        context = await browser_type.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,           # Show browser so you can see the result
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            current_url = page.url
            # SpaceBasic redirects to /login if session is expired
            is_logged_in = "/login" not in current_url.lower() and "messmanager" in current_url.lower()
            if is_logged_in:
                logger.info("✅ Session VALID — Booking page loaded (no login prompt)")
            else:
                logger.warning("❌ Session EXPIRED — SpaceBasic redirected to: %s", current_url)
                logger.warning(
                    "NOTE: SpaceBasic uses OTP login.\n"
                    "  1. Open Google Chrome\n"
                    "  2. Go to https://portal.spacebasic.com\n"
                    "  3. Log in with your email/mobile + OTP\n"
                    "  4. CLOSE Chrome completely\n"
                    "  5. Re-run: python session_helper.py"
                )
            return is_logged_in
        except Exception as e:
            logger.error("Error checking session: %s", e)
            return False
        finally:
            await context.close()


def main():
    parser = argparse.ArgumentParser(description="SpaceBasic Chrome Session Helper")
    parser.add_argument("--check", action="store_true", help="Check if session is still valid")
    args = parser.parse_args()

    cfg = load_config()

    if args.check:
        import asyncio
        valid = asyncio.run(check_session_valid(cfg))
        sys.exit(0 if valid else 1)
    else:
        success = copy_chrome_session(cfg)
        if success:
            print("\n✅ Chrome session copied to browser_profile/")
            print("   Now run:  python webhook_server.py")
        else:
            print("\n❌ Session copy failed. See errors above.")
            sys.exit(1)


if __name__ == "__main__":
    main()

