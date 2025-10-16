#!/bin/bash
# After-market update script for Linux/Mac cron
# Run at 5:00 PM ET on weekdays

cd "$(dirname "$0")"
python3 scripts/06_after_market_update.py
