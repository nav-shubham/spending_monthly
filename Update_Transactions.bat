@echo off
title UPI Spending Tracker Auto-Updater
cd /d "%~dp0"
echo ===================================================
echo 💵 UPI SPENDING TRACKER - AUTOMATIC SYNC & EXPORT
echo ===================================================
echo.
echo Scanning folder for new statements...
uv run python auto_update.py
echo.
echo ===================================================
echo Task finished. You can now open spending_tracker_final.xlsx.
echo ===================================================
pause
