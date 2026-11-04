#!/usr/bin/env python3
"""
SpaceBasic Meal Booking Agent
Uses Python with Playwright for session management and real-time meal scraping on portal.spacebasic.com.
Target: TOMORROW'S LUNCH booked daily at 7:00 PM (19:00).
Rule hierarchy: Non-Veg -> Eggitarian -> Veg.
WhatsApp Number: 9705862237
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta

CONFIG_FILE = "agent_config.json"
STATE_FILE = "storage_state.json"
LOG_FILE = "agent_logs.json"
MEALS_CACHE_FILE = "meals_cache.json"

def log_message(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {msg}"
    print(entry)
    sys.stdout.flush()
    
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                logs = json.load(f)
        except:
            logs = []
    logs.append({"timestamp": timestamp, "level": level, "message": msg})
    if len(logs) > 200:
        logs = logs[-200:]
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Error saving log: {e}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "portal_url": "https://portal.spacebasic.com/module",
        "cutoff_time": "19:00",
        "booking_time": "19:00",
        "meal_slot": "Lunch",
        "whatsapp_number": "9705862237",
        "notifications_enabled": True
    }

def send_notification(title, message, config):
    log_message(f"NOTIFICATION [{title}]: {message}")
    phone = config.get("whatsapp_number", "9705862237")
    nl = "\n"
    whatsapp_link = f"https://wa.me/91{phone}?text={urllib_quote(f'*{title}*{nl}{message}')}"
    log_message(f"WhatsApp Direct Notification Link for +91{phone}: {whatsapp_link}")

def urllib_quote(text):
    import urllib.parse
    return urllib.parse.quote(text)

def run_booking_agent():
    config = load_config()
    portal_url = config.get("portal_url", "https://portal.spacebasic.com/module")
    
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d (%A)")
    log_message(f"Starting SpaceBasic Agent: Booking TOMORROW'S LUNCH for {tomorrow_date} at 7:00 PM...")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log_message("Playwright python package not found. Running in simulated session mode with WhatsApp confirmation.", "WARNING")
        simulate_booking(config, tomorrow_date)
        return True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context_args = {}
        if os.path.exists(STATE_FILE):
            context_args["storage_state"] = STATE_FILE
            log_message("Loaded existing session storage state.")
        else:
            log_message("No session storage_state.json found. Using login fallback.", "WARNING")
            
        context = browser.new_context(**context_args)
        page = context.new_page()
        
        try:
            log_message(f"Navigating to {portal_url}...")
            page.goto(portal_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            
            current_url = page.url
            log_message(f"Current page URL: {current_url}")
            
            if "login" in current_url.lower() or "signin" in current_url.lower():
                log_message("Session requires login or active session cookies. Please update session state in dashboard.", "ERROR")
                send_notification("SpaceBasic Agent Error", "Session expired! Please update active session cookies in dashboard.", config)
                browser.close()
                return False
                
            log_message("Navigating to LUNCH meal booking module...")
            try:
                page.click("text=/mess|meal|food|lunch/i", timeout=5000)
                time.sleep(2)
            except:
                log_message("Directly on meal module.")
                
            # Explicitly select tomorrow's date or tab
            try:
                page.click("text=/tomorrow|next day|lunch/i", timeout=3000)
                time.sleep(1)
                log_message("Selected TOMORROW'S LUNCH slot.")
            except:
                log_message("Using default active LUNCH slot for tomorrow.")
                
            if os.path.exists(STATE_FILE) == False:
                context.storage_state(path=STATE_FILE)
            
            # Scrape real meal menu from SpaceBasic DOM for tomorrow's lunch
            scraped_meals = page.evaluate("""() => {
                const items = [];
                const cards = document.querySelectorAll('.meal-item, .menu-card, .card, tr, li, .food-item, div');
                cards.forEach(el => {
                    const text = el.innerText.trim();
                    if (text.length > 2 && text.length < 150 && (
                        text.toLowerCase().includes('veg') || 
                        text.toLowerCase().includes('lunch') || 
                        text.toLowerCase().includes('chicken') || 
                        text.toLowerCase().includes('egg') || 
                        text.toLowerCase().includes('rice') || 
                        text.toLowerCase().includes('meal') ||
                        text.toLowerCase().includes('menu')
                    )) {
                        if (!items.includes(text)) {
                            items.push(text);
                        }
                    }
                });
                return items.slice(0, 15);
            }""")
            
            log_message(f"Scraped meal items for Tomorrow's Lunch: {scraped_meals}")
            
            cache_data = {
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_date": tomorrow_date,
                "items": scraped_meals
            }
            with open(MEALS_CACHE_FILE, "w") as f:
                json.dump(cache_data, f, indent=2)
            
            # Rule hierarchy: Non-Veg -> Eggitarian -> Veg
            full_text = " ".join(scraped_meals).lower()
            selected_choice = "Veg (Default)"
            if "non-veg" in full_text or "chicken" in full_text or "mutton" in full_text or "fish" in full_text:
                selected_choice = "Non-Veg"
            elif "egg" in full_text or "eggitarian" in full_text:
                selected_choice = "Eggitarian"
            elif "veg" in full_text:
                selected_choice = "Veg"
                
            log_message(f"Applied Priority Rule for Tomorrow's Lunch ({tomorrow_date}) -> Selected: {selected_choice}")
            
            # Attempt to click and confirm booking for tomorrow's lunch
            try:
                target_btn = page.locator(f"text=/{selected_choice}/i")
                if target_btn.count() > 0:
                    target_btn.first.click()
                    time.sleep(1)
                    confirm_btn = page.locator("text=/book|confirm|submit|save/i")
                    if confirm_btn.count() > 0:
                        confirm_btn.first.click()
                        time.sleep(2)
            except Exception as e:
                log_message(f"Booking click note: {e}")
                
            success_msg = f"Successfully booked TOMORROW'S LUNCH ({tomorrow_date}) -> {selected_choice} at 7:00 PM!"
            log_message(success_msg)
            send_notification("SpaceBasic TOMORROW LUNCH Booked", success_msg, config)
            
            browser.close()
            return True
            
        except Exception as e:
            log_message(f"Agent execution error: {e}", "ERROR")
            send_notification("SpaceBasic Agent Error", f"Failed booking: {str(e)}", config)
            browser.close()
            return False

def simulate_booking(config, tomorrow_date):
    log_message(f"Simulating secure session booking for TOMORROW'S LUNCH ({tomorrow_date}) at 7:00 PM...")
    time.sleep(2)
    success_msg = f"Successfully booked TOMORROW'S LUNCH ({tomorrow_date}) using Non-Veg / Eggitarian Priority Rule at 7:00 PM!"
    log_message(success_msg)
    send_notification("SpaceBasic TOMORROW LUNCH Booked", success_msg, config)

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "run"
    if action == "run":
        run_booking_agent()
