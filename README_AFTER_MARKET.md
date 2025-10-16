# After-Market Automated Trading

## Quick Start

Run manually to test:
```bash
python scripts/06_after_market_update.py
```

## What It Does

1. **Checks if it's a weekday** (skips weekends automatically)
2. **Idempotent check** - won't run twice in the same day
3. **Fetches latest market data** (last 7 days for each stock)
4. **Loads top 10 algorithms** by validation fitness
5. **Generates trading signals** for each algorithm
6. **Executes trades** (buy/sell) based on signals
7. **Saves trades to database**
8. **Prints comprehensive report** of all activity

## Sample Output

```
================================================================================
AFTER-MARKET TRADING REPORT - 2025-10-14 05:00 PM
================================================================================

Summary:
  Algorithms Analyzed: 10
  Algorithms with Trades: 3
  Total Trades Executed: 5

================================================================================
TRADES BY ALGORITHM
================================================================================

Algorithm 0:
  Portfolio Value: $1,050.25
  Trades:
    [BUY]  NVDA      10 shares @ $ 450.25 =  $4,502.50
    [SELL] AAPL      5 shares @ $ 175.80 =    $879.00

Algorithm 3:
  Portfolio Value: $1,025.75
  Trades:
    [BUY]  GOOGL     8 shares @ $ 140.50 =  $1,124.00

================================================================================
TRADES BY STOCK
================================================================================

NVDA  : Buy:   10 shares, Sell:    0 shares, Total Value: $4,502.50
AAPL  : Buy:    0 shares, Sell:    5 shares, Total Value: $879.00
GOOGL : Buy:    8 shares, Sell:    0 shares, Total Value: $1,124.00

================================================================================

[SUCCESS] Update complete in 12.3s
```

## Scheduling

### Windows - Run at 5:00 PM daily

1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task
3. Name: "Genetic Stock Trading"
4. Trigger: Daily at 5:00 PM
5. Action: Start Program
6. Program: `C:\projects\genetic-stock\run_after_market.bat`
7. Finish

### Linux/Mac - Crontab

```bash
# Edit crontab
crontab -e

# Add this line (runs at 5:00 PM weekdays)
0 17 * * 1-5 cd /path/to/genetic-stock && ./run_after_market.sh
```

## Features

✅ **Idempotent** - Safe to run multiple times
✅ **Comprehensive Logging** - All activity logged to `C:\projects\logs\after_market_trading.log`
✅ **Market Day Detection** - Skips weekends automatically
✅ **Error Handling** - Continues even if individual stocks fail
✅ **Trade Reporting** - Clear summary of all trades
✅ **Database Persistence** - All trades saved for analysis

## Customization

### Change number of algorithms

Edit `scripts/06_after_market_update.py` line 345:

```python
algorithms = load_algorithms(top_n=10)  # Change 10 to desired number
```

### Change run time

Update your scheduler to run at a different time (e.g., 6:00 PM instead of 5:00 PM)

## Monitoring

### View logs
```bash
tail -f C:\projects\logs\after_market_trading.log
```

### Check recent trades
```bash
sqlite3 data/cache.db "SELECT * FROM transactions ORDER BY date DESC LIMIT 10"
```

### View portfolio values
```bash
sqlite3 data/cache.db "SELECT * FROM daily_portfolio_values ORDER BY date DESC LIMIT 10"
```

## Troubleshooting

**"Already processed" message**: This is normal! The script is idempotent and won't run twice per day.

**No trades executed**: This is normal if algorithms don't generate buy/sell signals.

**Market data errors**: Check API keys in `.env` file and internet connection.

For detailed setup instructions, see `SCHEDULING.md`.
