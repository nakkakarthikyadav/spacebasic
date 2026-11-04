@echo off
REM ============================================================
REM git_push.bat — Initialize git repo and push to GitHub
REM RUN THIS ONCE after creating your GitHub repo
REM ============================================================

cd /d "%~dp0"

echo [1/6] Initialising git repository...
git init

echo [2/6] Setting up .gitignore (protect secrets)...
REM .gitignore already exists in the project

echo [3/6] Configuring git user (edit these if needed)...
git config user.name "Karthik N"
git config user.email "your_email@example.com"

echo [4/6] Staging all files (secrets excluded by .gitignore)...
git add .

echo [5/6] Creating initial commit...
git commit -m "Initial commit: SpaceBasic WhatsApp Meal Booking Agent"

echo [6/6] Pushing to GitHub...
echo.
echo BEFORE RUNNING: Replace YOUR_GITHUB_USERNAME and YOUR_REPO_NAME below
echo Example: git remote add origin https://github.com/karthikn/spacebasic-agent.git
echo.
set /p REPO_URL="Paste your GitHub repo URL (e.g. https://github.com/username/repo.git): "

git remote add origin %REPO_URL%
git branch -M main
git push -u origin main

echo.
echo ============================================================
echo Done! Check your GitHub repo.
echo ============================================================
pause
