@echo off
REM After-market update script for Windows Task Scheduler
REM Run at 5:00 PM ET on weekdays

cd /d %~dp0
python scripts\06_after_market_update.py

REM Pause only if run manually (not from Task Scheduler)
if "%1"=="" pause
