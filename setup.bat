@echo off
REM ============================================================
REM SpaceBasic Agent — One-click Windows setup script
REM Run this ONCE after installing Python 3.11+
REM ============================================================

echo [1/5] Creating virtual environment...
python -m venv .venv

echo [2/5] Activating...
call .venv\Scripts\activate.bat

echo [3/5] Upgrading pip...
python -m pip install --upgrade pip

echo [4/5] Installing dependencies...
pip install -r requirements.txt

echo [5/5] Installing Playwright browsers...
python -m playwright install chromium

echo.
echo ============================================================
echo Setup complete!
echo.
echo Next steps:
echo   1. Copy .env.example to .env and fill in your credentials
echo   2. Place your college calendar in data\calendar\
echo   3. Run:  python main.py --parse-calendar
echo   4. Run:  python main.py --run-now  (dry run test)
echo   5. Open: streamlit run src\dashboard.py
echo ============================================================
pause

