"""
webhook_server.py
-----------------
Flask webhook → WhatsApp → portal.spacebasic.com meal booking

Booking URL: https://portal.spacebasic.com/module/messmanager/bookings

COMMANDS (send to Twilio WhatsApp number)
  book              → book all meals for today
  book lunch        → book lunch only
  book breakfast    → book breakfast only
  book dinner       → book dinner only
  status            → today's booking status + session health
  schedule          → next 7 working days
  history           → last 7 days
  pause / resume    → toggle bot on/off
  help              → command list
"""

import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

import yaml
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# ── Bootstrap ─────────────────────────────────────────────────────────
load_dotenv(".env", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/webhook.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("spacebasic.webhook")

# Create logs dir if missing
Path("logs").mkdir(exist_ok=True)

# ── Config + DB ────────────────────────────────────────────────────────
def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

cfg = load_config()

from calendar_db import CalendarDB
from booking_agent import SpaceBasicBooker

db = CalendarDB()
booker = SpaceBasicBooker(cfg)

# ── Security: only accept messages from YOUR WhatsApp number ──────────
MY_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER", "")   # e.g. whatsapp:+91XXXXXXXXXX
PAUSED = [False]  # mutable flag (simple in-process toggle)

app = Flask(__name__)


# ── Helpers ────────────────────────────────────────────────────────────

MEAL_TYPES_ALL = ["breakfast", "lunch", "dinner"]
MEAL_EMOJIS = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙"}


def reply(text: str) -> str:
    """Build a Twilio TwiML MessagingResponse."""
    resp = MessagingResponse()
    resp.message(text)
    return str(resp)


def booking_status_text() -> str:
    """Human-readable today's booking status."""
    today_records = db.today_summary()
    if not today_records:
        return "📭 No bookings recorded for today yet."

    lines = [f"📋 Today's status ({date.today().strftime('%a %d %b')}):"]
    for r in today_records:
        emoji = MEAL_EMOJIS.get(r["meal_type"], "🍽️")
        status_icon = "✅" if r["status"] == "success" else "❌"
        name = r.get("meal_name") or "—"
        lines.append(f"  {emoji} {status_icon} {r['meal_type'].title()}: {name}")
        if r["status"] == "success" and r.get("confirmation_id"):
            lines.append(f"       Ref: {r['confirmation_id']}")
    return "\n".join(lines)


def schedule_text() -> str:
    """Upcoming working days + holidays."""
    days = db.upcoming_working_days(n=7)
    holidays = db.upcoming_holidays(n=3)
    lines = ["📅 Upcoming schedule:"]
    for d in days:
        lines.append(f"  ✅ {d.strftime('%a %d %b')} — Working day")
    for h in holidays:
        lines.append(f"  🎉 {h['day_date']} — {h.get('description') or 'Holiday'}")
    if not days and not holidays:
        lines.append("  No calendar data. Upload your college calendar first.")
    return "\n".join(lines)


async def run_booking(meal_types: list[str]) -> str:
    """Run bookings for given meal types and return WhatsApp reply text."""
    today = date.today()
    lines = []

    # Check if today is a working day
    if db.count_working_days() > 0 and not db.is_working_day(today):
        return f"📅 Today ({today.strftime('%a %d %b')}) is not a college working day. No booking made."

    prefs = cfg.get("meal_preferences", {})
    dry_run = cfg["agent"].get("dry_run", True)

    if dry_run:
        lines.append("⚠️ DRY RUN MODE — no real booking made")
        lines.append("   (Set agent.dry_run: false in config.yaml to go live)")

    for meal_type in meal_types:
        # Duplicate guard
        if db.is_booked(today, meal_type):
            lines.append(f"  {MEAL_EMOJIS.get(meal_type,'🍽️')} {meal_type.title()}: already booked ✅")
            continue

        meal_prefs = prefs.get(f"{meal_type}_preferences", [])

        result = await booker.book(meal_type, meal_prefs)

        if result.success:
            db.record(today, meal_type, "success",
                      meal_name=result.meal_name,
                      confirmation_id=result.confirmation_id,
                      price=result.price)
            tag = " (dry run)" if result.dry_run else ""
            lines.append(
                f"  {MEAL_EMOJIS.get(meal_type,'🍽️')} ✅ {meal_type.title()}{tag}: {result.meal_name}\n"
                f"       Ref: {result.confirmation_id}"
            )
        else:
            db.record(today, meal_type, "failed", error=result.error)
            lines.append(f"  {MEAL_EMOJIS.get(meal_type,'🍽️')} ❌ {meal_type.title()}: {result.error}")

    if not lines:
        lines.append("Nothing to book.")

    header = f"🍽️ Booking result for {today.strftime('%a %d %b')}:\n"
    return header + "\n".join(lines)


# ── WhatsApp webhook route ─────────────────────────────────────────────

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender = request.values.get("From", "")
    body   = request.values.get("Body", "").strip()

    logger.info("Message from %s: %s", sender, body)

    # ── Security: reject messages not from YOUR number ────────────────
    if MY_NUMBER and sender != MY_NUMBER:
        logger.warning("Rejected message from unknown number: %s", sender)
        return reply("❌ Unauthorised.")

    cmd = body.lower().strip()

    # ── Command: help ─────────────────────────────────────────────────
    if cmd in ("help", "hi", "hello", "?"):
        text = (
            "🤖 *SpaceBasic Meal Bot*\n\n"
            "Commands:\n"
            "  *book*           — book all meals today\n"
            "  *book lunch*     — book lunch only\n"
            "  *book breakfast* — book breakfast only\n"
            "  *book dinner*    — book dinner only\n"
            "  *status*         — today's booking status\n"
            "  *schedule*       — upcoming working days\n"
            "  *history*        — last 7 days bookings\n"
            "  *pause*          — pause auto-booking\n"
            "  *resume*         — resume auto-booking\n"
            "  *help*           — show this menu"
        )
        return reply(text)

    # ── Command: status ───────────────────────────────────────────────
    if cmd == "status":
        # Check session health too
        portal_status = asyncio.run(booker.get_status())
        lines = []
        if portal_status.get("logged_in"):
            already_booked = portal_status.get("booked_today", [])
            lines.append("🔐 Session: ✅ Logged in to SpaceBasic")
            if already_booked:
                lines.append(f"✅ Already booked: {', '.join(already_booked)}")
        else:
            err = portal_status.get("error", "")
            lines.append(
                "🔐 Session: ❌ Expired!\n"
                "  → Log in to portal.spacebasic.com in Chrome\n"
                "  → Then run: python session_helper.py"
            )
            if err:
                lines.append(f"  Error: {err}")
        lines.append("")
        lines.append(booking_status_text())
        return reply("\n".join(lines))

    # ── Command: schedule ─────────────────────────────────────────────
    if cmd in ("schedule", "calendar"):
        return reply(schedule_text())

    # ── Command: history ──────────────────────────────────────────────
    if cmd == "history":
        records = db.history(days=7)
        if not records:
            return reply("📭 No booking history in the last 7 days.")
        lines = ["📋 Last 7 days:"]
        for r in records:
            icon = "✅" if r["status"] == "success" else "❌"
            lines.append(f"  {icon} {r['booking_date']} {r['meal_type']}: {r.get('meal_name') or r.get('error_message') or '—'}")
        lines.append(f"\n💰 Total spend: ₹{db.total_spend():.2f}")
        return reply("\n".join(lines))

    # ── Command: pause ────────────────────────────────────────────────
    if cmd == "pause":
        PAUSED[0] = True
        return reply("⏸️ Auto-booking paused. Send *resume* to re-enable.")

    # ── Command: resume ───────────────────────────────────────────────
    if cmd == "resume":
        PAUSED[0] = False
        return reply("▶️ Auto-booking resumed!")

    # ── Command: book [meal_type] ─────────────────────────────────────
    if cmd.startswith("book"):
        if PAUSED[0]:
            return reply("⏸️ Bot is paused. Send *resume* first.")

        parts = cmd.split()
        if len(parts) == 1:
            # "book" → book all enabled meals
            prefs = cfg.get("meal_preferences", {})
            meal_types = [m for m in MEAL_TYPES_ALL if prefs.get(f"book_{m}", False)]
            if not meal_types:
                return reply("⚠️ No meals enabled in config.yaml → meal_preferences.")
        elif len(parts) == 2 and parts[1] in MEAL_TYPES_ALL:
            meal_types = [parts[1]]
        else:
            return reply(f"❓ Unknown command: {body}\nSend *help* for commands.")

        # Run async booking in the sync Flask context
        result_text = asyncio.run(run_booking(meal_types))
        return reply(result_text)

    # ── Unknown command ───────────────────────────────────────────────
    return reply(f"❓ Unknown: '{body}'\nSend *help* for commands.")


# ── Health check endpoint (for monitoring) ────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "dry_run": cfg["agent"].get("dry_run", True)}, 200


# ── Entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    port = cfg.get("server", {}).get("port", 5000)
    logger.info("Starting SpaceBasic WhatsApp webhook server on port %d", port)
    logger.info("Dry run: %s", cfg["agent"].get("dry_run", True))
    logger.info("Authorised WhatsApp: %s", MY_NUMBER or "(not set — all numbers accepted!)")

    if not MY_NUMBER:
        logger.warning("MY_WHATSAPP_NUMBER not set in .env — ALL numbers can control the bot!")

    try:
        from waitress import serve
        logger.info("Using waitress production server")
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        logger.info("Using Flask dev server (install waitress for production)")
        app.run(host="0.0.0.0", port=port, debug=False)

