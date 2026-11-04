@echo off
REM ============================================================
REM SpaceBasic WhatsApp Agent — Complete Windows Installer
REM Run this ONCE after installing Python 3.11+
REM ============================================================
echo.
echo ============================================================
echo  SpaceBasic WhatsApp Meal Booking Agent - INSTALLER
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.11+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)

echo [OK] Python found:
python --version

echo.
echo [1/6] Creating virtual environment...
python -m venv .venv

echo [2/6] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/6] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [4/6] Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [5/6] Installing Playwright Chromium browser...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Playwright install failed
    pause
    exit /b 1
)

echo [6/6] Creating .env from template...
if not exist .env (
    copy .env.example .env
    echo [OK] Created .env — PLEASE EDIT IT NOW with your credentials
) else (
    echo [SKIP] .env already exists
)

echo.
echo ============================================================
echo  Installation Complete!
echo ============================================================
echo.
echo NEXT STEPS:
echo.
echo  1. Edit .env with your SpaceBasic URL + Twilio credentials
echo     (Open: notepad .env)
echo.
echo  2. Log in to SpaceBasic in Google Chrome (do this once)
echo     Then run:  python session_helper.py
echo.
echo  3. Upload your college calendar via:
echo     python src\calendar_parser_cli.py
echo.
echo  4. Test (safe mode):
echo     python webhook_server.py
echo.
echo  5. In a NEW terminal, expose via ngrok:
echo     ngrok http 5000
echo.
echo  6. Paste the ngrok URL into Twilio Console
echo     (Messaging > Sandbox > When a message comes in)
echo.
echo  7. Send "help" to the Twilio WhatsApp number to test!
echo.
pause

