@echo off
REM ============================================================
REM SpaceBasic WhatsApp Agent — Start Server
REM ============================================================
cd /d "%~dp0"
call .venv\Scripts\activate.bat
echo Starting SpaceBasic WhatsApp Webhook Server...
echo.
echo [TIP] In another terminal, run:  ngrok http 5000
echo [TIP] Then paste the ngrok URL into Twilio Console
echo.
python webhook_server.py
pause

