"""
discover_selectors.py
---------------------
Opens portal.spacebasic.com/module/messmanager/bookings in a VISIBLE browser
using your saved session, then prints all clickable elements so you can
update SELECTORS in booking_agent.py.

Run AFTER running session_helper.py:
  python discover_selectors.py

The browser will stay open for 60 seconds — use this time to:
  1. Look at what elements are on the page
  2. Press F12 to inspect specific elements
  3. Update SELECTORS in booking_agent.py with what you find
"""

import asyncio
import yaml
from pathlib import Path


BOOKING_URL = "https://portal.spacebasic.com/module/messmanager/bookings"


async def main():
    from playwright.async_api import async_playwright

    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    profile_dir = cfg["browser"]["playwright_profile"]

    print("=" * 60)
    print("SpaceBasic Selector Discovery Tool")
    print("=" * 60)
    print(f"Opening: {BOOKING_URL}")
    print("Browser will stay open for 90 seconds.")
    print("Press F12 in the browser to inspect elements.\n")

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,          # VISIBLE — so you can inspect
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await context.new_page()
        await page.goto(BOOKING_URL, wait_until="networkidle")

        current_url = page.url
        print(f"Current URL: {current_url}")

        if "/login" in current_url.lower():
            print("\n❌ SESSION EXPIRED!")
            print("   Log in to portal.spacebasic.com in Chrome first,")
            print("   then run: python session_helper.py")
            await context.close()
            return

        print("\n✅ Session valid — scraping page structure...\n")

        # Extract all buttons
        buttons = await page.query_selector_all("button")
        print(f"Found {len(buttons)} buttons:")
        for i, btn in enumerate(buttons):
            try:
                txt = (await btn.inner_text()).strip()
                cls = await btn.get_attribute("class") or ""
                if txt:
                    print(f"  [{i}] Text='{txt}' Class='{cls[:60]}'")
            except Exception:
                pass

        # Extract all links
        links = await page.query_selector_all("a")
        print(f"\nFound {len(links)} links:")
        for i, link in enumerate(links[:20]):
            try:
                txt = (await link.inner_text()).strip()
                href = await link.get_attribute("href") or ""
                if txt:
                    print(f"  [{i}] Text='{txt}' href='{href}'")
            except Exception:
                pass

        # Look for cards / meal items
        card_selectors = [
            ".card", "[class*='card']", "[class*='meal']", "[class*='booking']",
            "[class*='slot']", "tr", "li"
        ]
        for sel in card_selectors:
            els = await page.query_selector_all(sel)
            if els:
                print(f"\nSelector '{sel}' matched {len(els)} elements:")
                for el in els[:3]:
                    try:
                        txt = (await el.inner_text()).strip()[:80]
                        cls = (await el.get_attribute("class") or "")[:60]
                        if txt:
                            print(f"    class='{cls}' → text='{txt}'")
                    except Exception:
                        pass

        print("\n" + "=" * 60)
        print("Browser staying open for 90 seconds — use F12 to inspect.")
        print("Update SELECTORS in booking_agent.py with what you find.")
        print("=" * 60)

        await asyncio.sleep(90)
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())

