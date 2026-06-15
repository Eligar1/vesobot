@echo off
setlocal
title Vesobot
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment was not found.
    echo Run these commands first:
    echo python -m venv .venv
    echo .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo .env was not found.
    echo Copy .env.example to .env and fill BOT_TOKEN.
    pause
    exit /b 1
)

echo Vesobot is starting...
echo Keep this window open while you want the bot to work.
echo Close this window to stop the bot.
echo.

".venv\Scripts\python.exe" bot.py

echo.
echo Vesobot stopped.
pause
