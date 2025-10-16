# Trade Analysis Tools - Quick Reference

## Overview

Three powerful tools for managing and analyzing your genetic stock trading system:

1. **After-Market Update** - Automated daily trading
2. **List Trades** - View and analyze trade history
3. **Blog Generator** - Create HTML reports

---

## 1. After-Market Update (06_after_market_update.py)

**Purpose**: Automatically fetch data and execute trades at market close

### Quick Use
```bash
python scripts/06_after_market_update.py
```

### Features
- ✅ Runs at 5:00 PM after market close
- ✅ Idempotent (safe to run multiple times)
- ✅ Skips weekends automatically
- ✅ Updates last 7 days of market data
- ✅ Executes trades for top 10 algorithms
- ✅ Comprehensive trade reports

### Schedule It
```bash
# Windows Task Scheduler
run_after_market.bat at 5:00 PM daily

# Linux/Mac cron (5PM weekdays)
0 17 * * 1-5 cd /path/to/genetic-stock && ./run_after_market.sh
```

### Sample Output
```
================================================================================
AFTER-MARKET TRADING REPORT - 2025-10-14 05:00 PM
================================================================================

Summary:
  Algorithms Analyzed: 10
  Algorithms with Trades: 3
  Total Trades Executed: 5

Algorithm 0:
  Portfolio Value: $1,050.25
  Trades:
    [BUY]  NVDA      10 shares @ $ 450.25 =  $4,502.50
    [SELL] AAPL      5 shares @ $ 175.80 =    $879.00
```

**Docs**: `README_AFTER_MARKET.md`, `SCHEDULING.md`

---

## 2. List Trades (07_list_trades.py)

**Purpose**: View and analyze trade history from database

### Quick Use
```bash
# Show last 20 trades
python scripts/07_list_trades.py

# Show last 50 trades
python scripts/07_list_trades.py -n 50

# Today's trades
python scripts/07_list_trades.py --today

# Specific stock
python scripts/07_list_trades.py -s NVDA

# Specific algorithm
python scripts/07_list_trades.py -a 0

# Summary by stock
python scripts/07_list_trades.py --by-stock
```

### Common Commands

| Task | Command |
|------|---------|
| Recent trades | `python scripts/07_list_trades.py` |
| Today's trades | `python scripts/07_list_trades.py --today` |
| Yesterday | `python scripts/07_list_trades.py --date 2025-10-13` |
| Specific stock | `python scripts/07_list_trades.py -s AAPL` |
| Only buys | `python scripts/07_list_trades.py --buy` |
| Only sells | `python scripts/07_list_trades.py --sell` |
| By algorithm | `python scripts/07_list_trades.py -a 0` |
| Stock summary | `python scripts/07_list_trades.py --by-stock` |

### Sample Outputs

**Recent Trades**:
```
   ID       Date  Algo  Stock Action    Qty      Price        Total      Portfolio
    13 10/14/2025     0   NVDA    BUY     10    $450.25    $4,502.50      $8,750.00
    12 10/14/2025     0   AAPL   SELL      5    $175.80      $879.00      $4,247.50
```

**By Stock Summary**:
```
 Stock  Trades  Buys Sells  Shares+  Shares-    Buy Value   Sell Value          Net
  NVDA      12     8     4       85       45    $38,250.00    $20,125.00   -$18,125.00
  AAPL      10     5     5       60       60    $10,500.00    $10,800.00       $300.00
```

**Docs**: `README_LIST_TRADES.md`

---

## 3. Blog Generator (05_generate_blog.py)

**Purpose**: Generate HTML reports of algorithm performance

### Quick Use
```bash
python scripts/05_generate_blog.py
```

### Output
Creates in `blog/` directory:
- `index.html` - Top 50 performers
- `chromosome_*.html` - Individual algorithm pages
- `generation_*.html` - Generation summary
- `results.json` - Raw data

### View Results
```bash
# Open in browser
start blog/index.html           # Windows
open blog/index.html            # Mac
xdg-open blog/index.html        # Linux
```

---

## Typical Daily Workflow

### Morning (Before Market Open)
```bash
# Check yesterday's trades
python scripts/07_list_trades.py --date 2025-10-13

# Review performance by stock
python scripts/07_list_trades.py --by-stock
```

### After Market Close (5:00 PM)
```bash
# Let scheduled task run automatically
# Or run manually:
python scripts/06_after_market_update.py
```

### Evening (Review)
```bash
# Check today's trades
python scripts/07_list_trades.py --today

# See what algorithm 0 did
python scripts/07_list_trades.py -a 0 --today

# Generate updated blog
python scripts/05_generate_blog.py
```

### Weekly Review
```bash
# See last 100 trades
python scripts/07_list_trades.py -n 100

# Stock performance summary
python scripts/07_list_trades.py --by-stock

# Review blog for detailed analysis
start blog/index.html
```

---

## Database Queries

Direct SQLite queries for advanced analysis:

```bash
# Recent trades
sqlite3 data/cache.db "SELECT * FROM transactions ORDER BY date DESC LIMIT 10"

# Trades per day
sqlite3 data/cache.db "SELECT date, COUNT(*) FROM transactions GROUP BY date"

# Algorithm performance
sqlite3 data/cache.db "SELECT algorithm_id, COUNT(*) FROM transactions GROUP BY algorithm_id"

# Portfolio values
sqlite3 data/cache.db "SELECT * FROM daily_portfolio_values ORDER BY date DESC LIMIT 10"

# Export to CSV
sqlite3 -header -csv data/cache.db "SELECT * FROM transactions" > trades.csv
```

---

## File Locations

### Scripts
- `scripts/06_after_market_update.py` - Daily trading automation
- `scripts/07_list_trades.py` - Trade viewer
- `scripts/05_generate_blog.py` - HTML report generator

### Wrappers
- `run_after_market.bat` / `.sh` - After-market runner
- `list_trades.bat` / `.sh` - Trade list runner

### Data
- `data/cache.db` - SQLite database with all trades
- `results/validation_results.json` - Algorithm performance data
- `blog/` - Generated HTML reports
- `C:\projects\logs\after_market_trading.log` - Trading activity logs

### Documentation
- `README_AFTER_MARKET.md` - After-market update guide
- `README_LIST_TRADES.md` - Trade listing guide
- `SCHEDULING.md` - Detailed scheduling instructions

---

## Testing

### Insert Sample Trades
```bash
python test_list_trades.py
```

This creates sample trades for testing the list_trades tool.

### Test Views
```bash
# After inserting samples:
python scripts/07_list_trades.py
python scripts/07_list_trades.py --today
python scripts/07_list_trades.py --by-stock
python scripts/07_list_trades.py -s NVDA
```

---

## Troubleshooting

### No trades found
- After-market script hasn't run yet
- No algorithms generated signals
- Check: `python scripts/07_list_trades.py --by-stock`

### Script errors
- Check logs: `tail -f C:\projects\logs\after_market_trading.log`
- Verify database: `sqlite3 data/cache.db ".tables"`
- Test connection: `python -c "from src.data.cache import DataCache; DataCache('data/cache.db').connect()"`

### Scheduling issues
- Windows: Check Task Scheduler history
- Linux: Check cron logs: `grep CRON /var/log/syslog`
- Verify paths and working directory

---

## Quick Tips

1. **Daily Check**: `python scripts/07_list_trades.py --today`
2. **Monitor Stock**: `python scripts/07_list_trades.py -s AAPL -n 50`
3. **Algorithm Focus**: `python scripts/07_list_trades.py -a 0`
4. **Weekly Summary**: `python scripts/07_list_trades.py --by-stock`
5. **Export Data**: Use SQLite CSV export for spreadsheet analysis

---

## Next Steps

1. ✅ Set up after-market automation (see `SCHEDULING.md`)
2. ✅ Run daily and review trades
3. ✅ Analyze patterns with `--by-stock`
4. ✅ Generate weekly blog reports
5. ✅ Optimize algorithms based on results

Happy trading! 📈
