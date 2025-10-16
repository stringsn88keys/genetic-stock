# List Trades Tool

A command-line tool to view and analyze trades from your genetic stock trading system.

## Quick Start

```bash
# Show last 20 trades
python scripts/07_list_trades.py

# Or use the wrapper
./list_trades.sh          # Linux/Mac
list_trades.bat           # Windows
```

## Usage Examples

### Basic Usage

```bash
# Show last 20 trades (default)
python scripts/07_list_trades.py

# Show last 50 trades
python scripts/07_list_trades.py -n 50

# Show last 100 trades
python scripts/07_list_trades.py --number 100
```

### Filter by Algorithm

```bash
# Show trades for algorithm 0
python scripts/07_list_trades.py -a 0

# Show last 30 trades for algorithm 5
python scripts/07_list_trades.py -a 5 -n 30
```

### Filter by Stock

```bash
# Show all trades for AAPL
python scripts/07_list_trades.py -s AAPL

# Show last 50 trades for NVDA
python scripts/07_list_trades.py -s NVDA -n 50
```

### Filter by Action

```bash
# Show only buy trades
python scripts/07_list_trades.py --buy

# Show only sell trades
python scripts/07_list_trades.py --sell

# Show last 30 buy trades for algorithm 0
python scripts/07_list_trades.py -a 0 --buy -n 30
```

### View by Date

```bash
# Show today's trades
python scripts/07_list_trades.py --today

# Show trades for specific date
python scripts/07_list_trades.py --date 2025-10-14

# Show trades for yesterday
python scripts/07_list_trades.py --date 2025-10-13
```

### Summary Views

```bash
# Show trading summary by stock
python scripts/07_list_trades.py --by-stock
```

## Sample Output

### Recent Trades View

```
========================================================================================================================
RECENT TRADES
========================================================================================================================
   ID       Date  Algo  Stock Action    Qty      Price        Total      Portfolio
------------------------------------------------------------------------------------------------------------------------
  123 10/14/2025     0   NVDA    BUY     10    $450.25     $4,502.50      $8,750.00
  122 10/14/2025     0   AAPL   SELL      5    $175.80       $879.00      $4,247.50
  121 10/14/2025     3  GOOGL    BUY      8    $140.50     $1,124.00      $9,124.00
  120 10/13/2025     0    CVX   SELL     15    $155.30     $2,329.50     $12,500.00
  119 10/13/2025     2    BAC    BUY     50     $32.45     $1,622.50      $7,890.00
------------------------------------------------------------------------------------------------------------------------

Summary:
  Total Trades: 5
  Buys:    3 trades, Total Value: $7,248.50
  Sells:   2 trades, Total Value: $3,208.50
  Net:   -$4,040.00 (cost)
========================================================================================================================
```

### By Stock Summary

```
========================================================================================================================
TRADING ACTIVITY BY STOCK
========================================================================================================================
 Stock  Trades  Buys Sells  Shares+  Shares-    Buy Value   Sell Value          Net      First       Last
------------------------------------------------------------------------------------------------------------------------
  NVDA      12     8     4       85       45    $38,250.00    $20,125.00   -$18,125.00 10/01/2025 10/14/2025
  AAPL      10     5     5       60       60    $10,500.00    $10,800.00       $300.00 10/01/2025 10/14/2025
 GOOGL       8     6     2       48       16     $6,720.00     $2,240.00    -$4,480.00 10/02/2025 10/13/2025
   CVX       7     3     4       45       60     $6,975.00     $9,318.00     $2,343.00 10/03/2025 10/13/2025
   BAC       5     4     1      200       50     $6,490.00     $1,622.50    -$4,867.50 10/05/2025 10/13/2025
========================================================================================================================
```

### Today's Trades (grouped by algorithm)

```
========================================================================================================================
TRADES FOR 10/14/2025
========================================================================================================================

Algorithm 0:
     ID  Stock Action    Qty      Price        Total      Portfolio
  --------------------------------------------------------------------------------
    123   NVDA    BUY     10    $450.25     $4,502.50      $8,750.00
    122   AAPL   SELL      5    $175.80       $879.00      $4,247.50
    Algorithm 0 Summary: Buys: 1, Sells: 1, Net: -$3,623.50

Algorithm 3:
     ID  Stock Action    Qty      Price        Total      Portfolio
  --------------------------------------------------------------------------------
    121  GOOGL    BUY      8    $140.50     $1,124.00      $9,124.00
    Algorithm 3 Summary: Buys: 1, Sells: 0, Net: -$1,124.00

========================================================================================================================
```

## Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `-n, --number` | Number of trades to show | `-n 50` |
| `-a, --algorithm` | Filter by algorithm ID | `-a 0` |
| `-s, --stock` | Filter by stock ticker | `-s AAPL` |
| `--buy` | Show only buy trades | `--buy` |
| `--sell` | Show only sell trades | `--sell` |
| `--today` | Show today's trades | `--today` |
| `--date` | Show trades for date | `--date 2025-10-14` |
| `--by-stock` | Show summary by stock | `--by-stock` |
| `-h, --help` | Show help message | `--help` |

## Combining Filters

You can combine multiple filters:

```bash
# Show last 20 buy trades for NVDA
python scripts/07_list_trades.py -s NVDA --buy -n 20

# Show last 50 trades for algorithm 0 on AAPL
python scripts/07_list_trades.py -a 0 -s AAPL -n 50

# Show all sell trades for algorithm 3
python scripts/07_list_trades.py -a 3 --sell -n 1000
```

## Integration with Other Tools

### Export to CSV

```bash
# Use SQLite to export
sqlite3 -header -csv data/cache.db "SELECT * FROM transactions" > trades.csv
```

### Query Database Directly

```bash
# Recent trades
sqlite3 data/cache.db "SELECT * FROM transactions ORDER BY date DESC LIMIT 10"

# Trades for specific stock
sqlite3 data/cache.db "SELECT * FROM transactions WHERE stock_ticker='AAPL'"

# Total trades per day
sqlite3 data/cache.db "SELECT date, COUNT(*) FROM transactions GROUP BY date"
```

## Troubleshooting

**"No trades found"**: This is normal if:
- The after-market script hasn't run yet
- No algorithms generated buy/sell signals
- You're filtering with criteria that don't match any trades

**Database errors**: Ensure `data/cache.db` exists and is accessible

**Date format errors**: Use YYYY-MM-DD format (e.g., 2025-10-14)

## Tips

1. **Check recent activity**: `python scripts/07_list_trades.py` (no args)
2. **Monitor specific algorithm**: `python scripts/07_list_trades.py -a 0 -n 100`
3. **Track stock performance**: `python scripts/07_list_trades.py --by-stock`
4. **Daily review**: `python scripts/07_list_trades.py --today`
5. **Analyze patterns**: Use `--by-stock` to see which stocks are traded most

## See Also

- `06_after_market_update.py` - Execute trades automatically
- `05_generate_blog.py` - Generate HTML reports
- Database schema: See `src/data/cache.py`
