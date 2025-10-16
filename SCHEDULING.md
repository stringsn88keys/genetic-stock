# Scheduling After-Market Updates

The `06_after_market_update.py` script is designed to run automatically at 5:00 PM after market close. Here's how to set it up:

## Features

✅ **Idempotent** - Safe to run multiple times per day (won't create duplicate trades)
✅ **Market Day Check** - Automatically skips weekends
✅ **Comprehensive Reporting** - Shows all trades executed
✅ **Data Updates** - Fetches latest market data before trading
✅ **Top Algorithms Only** - Runs best 10 algorithms by default

## Manual Execution

You can run the script manually anytime:

```bash
# Windows
python scripts\06_after_market_update.py

# Or use the batch file
run_after_market.bat

# Linux/Mac
python3 scripts/06_after_market_update.py

# Or use the shell script
./run_after_market.sh
```

## Automatic Scheduling

### Windows (Task Scheduler)

1. **Open Task Scheduler**
   - Press `Win + R`, type `taskschd.msc`, press Enter

2. **Create New Task**
   - Click "Create Task" (not "Create Basic Task")
   - Name: "Genetic Stock After-Market Update"
   - Description: "Update market data and execute trades at 5PM"

3. **Triggers Tab**
   - Click "New..."
   - Begin the task: "On a schedule"
   - Settings: Daily at 5:00 PM
   - Advanced: Check "Stop task if it runs longer than: 1 hour"
   - Click OK

4. **Actions Tab**
   - Click "New..."
   - Action: "Start a program"
   - Program/script: Browse to `run_after_market.bat`
   - Start in: Browse to your project folder (C:\projects\genetic-stock)
   - Click OK

5. **Conditions Tab**
   - Uncheck "Start only if on AC power" (if using laptop)
   - Check "Wake the computer to run this task"

6. **Settings Tab**
   - Check "Allow task to be run on demand"
   - Check "If task fails, restart every: 5 minutes, 3 times"
   - Click OK

### Linux/Mac (Cron)

1. **Make script executable**
   ```bash
   chmod +x run_after_market.sh
   ```

2. **Edit crontab**
   ```bash
   crontab -e
   ```

3. **Add cron job** (runs at 5:00 PM ET on weekdays)
   ```cron
   # After-market update - 5:00 PM ET Monday-Friday
   0 17 * * 1-5 cd /path/to/genetic-stock && ./run_after_market.sh >> C:\projects\logs\cron.log 2>&1
   ```

4. **For different timezone** (e.g., if you're in PST but want to run at 5PM ET):
   ```cron
   # 5:00 PM ET = 2:00 PM PT
   0 14 * * 1-5 cd /path/to/genetic-stock && ./run_after_market.sh >> C:\projects\logs\cron.log 2>&1
   ```

### Using systemd Timer (Linux Alternative)

Create `/etc/systemd/system/genetic-stock.service`:

```ini
[Unit]
Description=Genetic Stock After-Market Update
After=network.target

[Service]
Type=oneshot
User=yourusername
WorkingDirectory=/path/to/genetic-stock
ExecStart=/usr/bin/python3 scripts/06_after_market_update.py
StandardOutput=append:C:\projects\logs\after_market_trading.log
StandardError=append:C:\projects\logs\after_market_trading.log

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/genetic-stock.timer`:

```ini
[Unit]
Description=Run genetic stock update at 5PM weekdays
Requires=genetic-stock.service

[Timer]
OnCalendar=Mon..Fri 17:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable genetic-stock.timer
sudo systemctl start genetic-stock.timer
sudo systemctl status genetic-stock.timer
```

## Monitoring

### Check Logs

```bash
# View today's activity
tail -100 C:\projects\logs\after_market_trading.log

# Follow live
tail -f C:\projects\logs\after_market_trading.log

# Search for trades
grep "SELL\|BUY" C:\\projects\\logs\\after_market_trading.log
```

### Check Database

```bash
# Recent trades
python -c "
import sqlite3
conn = sqlite3.connect('data/cache.db')
df = pd.read_sql_query('''
    SELECT date, stock_ticker, action, quantity, price
    FROM transactions
    ORDER BY date DESC, transaction_id DESC
    LIMIT 20
''', conn)
print(df)
"
```

## Customization

### Change Number of Algorithms

Edit line 76 in `06_after_market_update.py`:

```python
# Run top 10 algorithms (default)
algorithms = load_algorithms(top_n=10)

# Or run more/less
algorithms = load_algorithms(top_n=5)   # Top 5
algorithms = load_algorithms(top_n=50)  # Top 50
```

### Change Schedule Time

For 6:00 PM instead of 5:00 PM:

- **Windows Task Scheduler**: Edit trigger time
- **Cron**: Change `0 17` to `0 18`
- **Systemd**: Change `OnCalendar=Mon..Fri 17:00:00` to `OnCalendar=Mon..Fri 18:00:00`

## Troubleshooting

### Script doesn't run

1. Check logs: `C:\projects\logs\after_market_trading.log`
2. Test manually: `python scripts\06_after_market_update.py`
3. Verify Python path in Task Scheduler/cron
4. Check working directory is set correctly

### "Already processed" message

This is normal! The script is idempotent - it won't run twice in the same day.
If you need to force re-run (for testing):

```sql
-- Delete today's portfolio values to allow re-run
DELETE FROM daily_portfolio_values WHERE date = '2025-10-14';
```

### No trades executed

This is normal! Trades only execute when:
- Algorithm generates buy/sell signal (not "hold")
- Signal score exceeds thresholds
- Portfolio has available cash/positions
- Risk management allows the trade

### Market data not updating

1. Check API keys in `.env`
2. Verify internet connection
3. Check if data source (Yahoo Finance) is accessible
4. Try running data collection script: `python scripts/01_collect_data.py`

## Email Notifications (Optional)

To receive email notifications of trades, you can modify the script to send emails.
Add at the end of `main()`:

```python
# Send email report
if total_trades > 0:
    send_email_report(report)
```

See the code comments for implementation details.
