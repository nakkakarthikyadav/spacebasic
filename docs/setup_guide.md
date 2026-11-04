# SpaceBasic Meal Booking Agent — Setup Guide

## 1. Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11 or newer |
| pip | latest |
| Windows / macOS / Linux | Any |

---

## 2. Installation

```bash
# 1. Clone or copy the project
cd "C:\Users\Karthik N\spacebasic_agent"

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
python -m playwright install chromium
```

---

## 3. Configure Credentials (Secure)

> **NEVER put your password in config.yaml or any source file.**

```bash
# Copy the template
copy .env.example .env
```

Open `.env` in any text editor and fill in:

```dotenv
SPACEBASIC_URL=https://your-college.spacebasic.io
SPACEBASIC_USERNAME=your_student_id@college.edu
SPACEBASIC_PASSWORD=your_actual_password
```

`.env` is already in `.gitignore` — it will never be accidentally committed.

---

## 4. Configure Meal Preferences

Open `config/config.yaml` and edit the `meal_preferences` section:

```yaml
meal_preferences:
  book_breakfast: true
  book_lunch: true
  book_dinner: true
  diet_type: "vegetarian"
  breakfast_preferences:
    - "Idli & Sambar"
  lunch_preferences:
    - "Rice & Dal"
  dinner_preferences:
    - "Chapati & Sabzi"
  max_daily_budget: 200        # INR — set 0 for no limit
```

---

## 5. Upload Your College Calendar

### Option A — Via Dashboard (Recommended)

```bash
streamlit run src/dashboard.py
```

1. Open the browser at http://localhost:8501
2. In the left sidebar, click "Browse files" under **Upload Calendar**
3. Upload your PDF, CSV, or Excel file
4. Click **Parse Calendar Now**

### Option B — Via Command Line

1. Place your calendar file in `data/calendar/`
2. Set the path in `config.yaml`:
   ```yaml
   calendar:
     file_path: "data/calendar/my_calendar.pdf"
   ```
3. Run:
   ```bash
   python main.py --parse-calendar
   ```

### CSV Calendar Format

If you prepare a CSV, use these columns:

| date | day_type | description |
|------|----------|-------------|
| 2025-08-15 | holiday | Independence Day |
| 2025-08-04 | working | Regular class |
| 2025-12-25 | vacation | Winter break |

---

## 6. Test in Safe Mode (DRY RUN)

Before enabling real bookings, **always test first**:

```bash
# Ensure dry_run: true in config.yaml (it is by default)
python main.py --run-now --dry-run
```

Check `logs/agent.log` to verify the agent would have booked correctly.

Run the unit tests:

```bash
pytest tests/ -v
```

---

## 7. Enable Live Bookings

Only after testing is successful:

1. Open `config/config.yaml`:
   ```yaml
   agent:
     dry_run: false
   ```
2. Open `.env`:
   ```dotenv
   LIVE_BOOKING_ENABLED=true
   ```
3. Start the agent:
   ```bash
   python main.py
   ```

---

## 8. Update the Browser Selectors

SpaceBasic's web UI may differ per institution. If the agent fails to
find elements, open `src/browser_automation.py` and update `_SELECTORS`:

```python
_SELECTORS = {
    "username_input": 'input[name="username"]',   # Inspect your login page
    ...
}
```

To inspect selectors:
```bash
python -m playwright codegen https://your-college.spacebasic.io
```
Playwright's code generator will record your actions and show the selectors.

---

## 9. Deploy for 24/7 Operation

### Option A — Windows Task Scheduler (runs on your PC)

```
Task Scheduler → Create Basic Task
  Name: SpaceBasic Agent
  Trigger: Daily at 07:00
  Action: Start a program
    Program: C:\Users\Karthik N\spacebasic_agent\.venv\Scripts\python.exe
    Arguments: main.py --run-now
    Start in: C:\Users\Karthik N\spacebasic_agent
```

### Option B — Always-on cloud server (PC can be off)

Deploy to a free/cheap cloud VM (e.g. Oracle Free Tier, AWS t2.micro):

```bash
# On the server (Linux):
git clone <your-repo> spacebasic_agent
cd spacebasic_agent
pip install -r requirements.txt
python -m playwright install --with-deps chromium

# Create a systemd service:
sudo nano /etc/systemd/system/spacebasic.service
```

```ini
[Unit]
Description=SpaceBasic Meal Booking Agent
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/spacebasic_agent
ExecStart=/home/ubuntu/spacebasic_agent/.venv/bin/python main.py
Restart=always
RestartSec=60
EnvironmentFile=/home/ubuntu/spacebasic_agent/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable spacebasic
sudo systemctl start spacebasic
```

---

## 10. Dashboard

```bash
streamlit run src/dashboard.py
```

Open http://localhost:8501 in your browser.

Features:
- Today's booking status
- Upcoming working days
- Full booking history
- Meal preferences
- Pause / Resume / Run Now buttons
- Calendar uploader

