"""
dashboard.py
------------
Streamlit dashboard for the SpaceBasic Meal Booking Agent.

Run with:
    streamlit run src/dashboard.py

Features
--------
  - Today's booking status
  - Upcoming working days
  - Booking history table + charts
  - Holiday calendar
  - Meal preferences viewer
  - Total expenditure
  - Agent running status
  - Pause / Resume / Run-now controls
  - Calendar file uploader
"""

import sys
import os
from pathlib import Path
from datetime import date, timedelta

# Ensure project root is on path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from src.database import Database
from src.logger_setup import setup_logger
from src.config_loader import load_config

# ── Page configuration ──────────────────────────────────────────────
st.set_page_config(
    page_title="SpaceBasic Agent Dashboard",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Init ─────────────────────────────────────────────────────────────
cfg = load_config()
setup_logger(
    log_dir=cfg.get("logging", {}).get("log_dir", "logs"),
    level=cfg.get("logging", {}).get("level", "INFO"),
)
db = Database()
db.init()


# ── Helper functions ─────────────────────────────────────────────────

def get_agent_paused() -> bool:
    return db.get_state("agent_paused", "false").lower() == "true"


def status_badge(status: str) -> str:
    icons = {"success": "✅", "failed": "❌", "skipped": "⏭️", "": "—"}
    return icons.get(status, status)


# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://via.placeholder.com/200x60?text=SpaceBasic+Agent", use_container_width=True)
    st.title("Agent Controls")

    paused = get_agent_paused()
    st.markdown(f"**Status:** {'⏸️ Paused' if paused else '▶️ Running'}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏸️ Pause" if not paused else "▶️ Resume"):
            db.set_state("agent_paused", "false" if paused else "true")
            st.rerun()
    with col2:
        if st.button("🔄 Run Now"):
            st.info("Triggering booking... check logs for result.")
            # Import and run agent synchronously
            try:
                from src.config_loader import load_config
                from src.notifier import Notifier
                from src.booking_agent import BookingAgent
                cfg2 = load_config()
                notifier = Notifier(cfg2)
                agent = BookingAgent(cfg2, db, notifier)
                result = agent.run_booking_cycle()
                st.success(f"Done: {result}")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")
    st.markdown("**DRY RUN mode:**")
    dry_run = cfg.get("agent", {}).get("dry_run", True)
    st.markdown(
        "🟢 **ON** — safe mode, no real bookings" if dry_run
        else "🔴 **OFF** — LIVE bookings enabled"
    )
    st.caption("Change in config/config.yaml → agent.dry_run")

    st.markdown("---")
    st.markdown("**Upload Calendar**")
    uploaded = st.file_uploader(
        "Drop your college calendar (PDF, CSV, XLSX)",
        type=["pdf", "csv", "xlsx", "xls", "png", "jpg"],
    )
    if uploaded:
        save_path = Path("data/calendar") / uploaded.name
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.success(f"Saved: {uploaded.name}")
        if st.button("📅 Parse Calendar Now"):
            from src.calendar_parser import CalendarParser
            from datetime import date as _date
            acad_cfg = cfg.get("calendar", {})
            parser = CalendarParser(
                academic_start=_date.fromisoformat(acad_cfg.get("academic_year_start", "2025-07-01")),
                academic_end=_date.fromisoformat(acad_cfg.get("academic_year_end", "2026-05-31")),
                saturday_working=acad_cfg.get("saturday_working", False),
                sunday_working=acad_cfg.get("sunday_working", False),
            )
            days = parser.parse(str(save_path))
            for d in days:
                db.upsert_working_day(d["date"], d["day_type"], d.get("description", ""), uploaded.name)
            st.success(f"Calendar loaded: {len(days)} days classified.")


# ── Main content ─────────────────────────────────────────────────────
st.title("🍽️ SpaceBasic Meal Booking Agent")
st.caption(f"Today: {date.today().strftime('%A, %d %B %Y')} | Timezone: Asia/Kolkata")

# ── Row 1: KPI metrics ───────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

today_bookings = db.get_today_bookings()
today_success = [b for b in today_bookings if b["status"] == "success"]
summary = db.booking_summary()
total_spend = db.total_spend()
working_days_loaded = db.count_working_days_loaded()

with col1:
    st.metric("Today's Bookings", len(today_success), help="Successful bookings today")

with col2:
    st.metric("Total Successful", summary.get("success", 0))

with col3:
    st.metric("Total Spend (₹)", f"₹{total_spend:.2f}")

with col4:
    st.metric("Working Days in Calendar", working_days_loaded)

st.markdown("---")

# ── Row 2: Today's status + Upcoming ────────────────────────────────
col_a, col_b = st.columns([1, 1])

with col_a:
    st.subheader("📅 Today's Bookings")
    day_info = db.get_day_type(date.today())
    if day_info:
        dtype = day_info["day_type"]
        desc = day_info.get("description", "")
        badges = {"working": "🟢 Working Day", "holiday": "🔴 Holiday", "weekend": "🔵 Weekend", "vacation": "🟡 Vacation"}
        st.markdown(f"**{badges.get(dtype, dtype)}** {f'— {desc}' if desc else ''}")
    else:
        st.warning("⚠️ Today is not in the calendar. Agent will skip booking.")

    if today_bookings:
        for b in today_bookings:
            icon = status_badge(b["status"])
            st.markdown(f"{icon} **{b['meal_type'].title()}**: {b.get('meal_name') or '—'} "
                        f"(₹{b.get('price') or 0:.2f}) `{b.get('confirmation_id') or ''}`")
    else:
        st.info("No booking records for today yet.")

with col_b:
    st.subheader("🔮 Upcoming Working Days")
    upcoming = db.get_upcoming_working_days(n=7)
    holidays = db.get_upcoming_holidays(n=5)

    if upcoming:
        rows = []
        for d in upcoming:
            rows.append({"Date": d.strftime("%a %d %b"), "Type": "✅ Working"})
        for h in holidays:
            rows.append({"Date": h["day_date"], "Type": f"🎉 {h.get('description', 'Holiday')}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No upcoming working days found. Upload your college calendar.")

st.markdown("---")

# ── Row 3: Booking history ───────────────────────────────────────────
st.subheader("📋 Booking History")

date_range = st.date_input(
    "Filter by date range",
    value=(date.today() - timedelta(days=30), date.today()),
)
from_d, to_d = (date_range[0], date_range[1]) if len(date_range) == 2 else (None, None)

records = db.get_bookings(from_date=from_d, to_date=to_d)
if records:
    df = pd.DataFrame(records)
    df["status_icon"] = df["status"].map(lambda s: status_badge(s) + " " + s)
    display_cols = ["booking_date", "meal_type", "meal_name", "status_icon", "price", "confirmation_id", "booked_at"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols].rename(columns={
        "booking_date": "Date",
        "meal_type": "Meal",
        "meal_name": "Item",
        "status_icon": "Status",
        "price": "₹",
        "confirmation_id": "Ref ID",
        "booked_at": "Booked At",
    }), use_container_width=True, hide_index=True)

    # Spend chart
    df["booking_date"] = pd.to_datetime(df["booking_date"])
    df_success = df[df["status"] == "success"].copy()
    if not df_success.empty:
        daily_spend = df_success.groupby("booking_date")["price"].sum().reset_index()
        fig = px.bar(
            daily_spend, x="booking_date", y="price",
            title="Daily Expenditure (₹)", labels={"booking_date": "Date", "price": "₹"},
            color_discrete_sequence=["#4CAF50"],
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No booking history in the selected date range.")

st.markdown("---")

# ── Row 4: Meal preferences summary ─────────────────────────────────
st.subheader("⚙️ Meal Preferences (from config.yaml)")
prefs = cfg.get("meal_preferences", {})
pref_data = {
    "Breakfast": ", ".join(prefs.get("breakfast_preferences", [])) or "Any",
    "Lunch": ", ".join(prefs.get("lunch_preferences", [])) or "Any",
    "Dinner": ", ".join(prefs.get("dinner_preferences", [])) or "Any",
    "Diet": prefs.get("diet_type", "—").title(),
    "Max Daily Budget": f"₹{prefs.get('max_daily_budget', 0)}" if prefs.get("max_daily_budget") else "No limit",
    "Allow Alternative": "Yes" if prefs.get("allow_alternative") else "No",
}
st.table(pd.DataFrame(list(pref_data.items()), columns=["Setting", "Value"]))

st.markdown("---")
st.caption("SpaceBasic Meal Booking Agent • Logs in `logs/agent.log` • Config in `config/config.yaml`")

