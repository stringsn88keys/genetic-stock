"""List recent trades from the database"""

import sys
import os
import argparse
import sqlite3
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.cache import DataCache


def format_currency(value):
    """Format value as currency"""
    return f"${value:,.2f}"


def format_date(date_str):
    """Format date string"""
    try:
        dt = datetime.strptime(str(date_str), '%Y-%m-%d')
        return dt.strftime('%m/%d/%Y')
    except:
        return str(date_str)


def list_recent_trades(n: int = 20, algorithm_id: Optional[int] = None,
                       ticker: Optional[str] = None, action: Optional[str] = None):
    """
    List recent trades from database

    Args:
        n: Number of trades to show
        algorithm_id: Filter by algorithm ID (optional)
        ticker: Filter by stock ticker (optional)
        action: Filter by action ('buy' or 'sell') (optional)
    """
    with DataCache('data/cache.db') as cache:
        # Build query
        query = """
            SELECT
                t.transaction_id,
                t.date,
                t.algorithm_id,
                t.stock_ticker,
                t.action,
                t.quantity,
                t.price,
                t.portfolio_value_after,
                (t.quantity * t.price) as total_value
            FROM transactions t
            WHERE 1=1
        """
        params = []

        if algorithm_id is not None:
            query += " AND t.algorithm_id = ?"
            params.append(algorithm_id)

        if ticker:
            query += " AND t.stock_ticker = ?"
            params.append(ticker.upper())

        if action:
            query += " AND t.action = ?"
            params.append(action.lower())

        query += " ORDER BY t.date DESC, t.transaction_id DESC LIMIT ?"
        params.append(n)

        # Execute query
        cursor = cache.conn.cursor()
        cursor.execute(query, params)
        trades = cursor.fetchall()

        if not trades:
            print("\nNo trades found matching criteria.\n")
            return

        # Print header
        print("\n" + "=" * 120)
        print("RECENT TRADES")
        print("=" * 120)

        # Print filter info if any
        filters = []
        if algorithm_id is not None:
            filters.append(f"Algorithm: {algorithm_id}")
        if ticker:
            filters.append(f"Stock: {ticker}")
        if action:
            filters.append(f"Action: {action.upper()}")

        if filters:
            print(f"Filters: {', '.join(filters)}")
            print("-" * 120)

        # Print column headers
        print(f"{'ID':>5} {'Date':>10} {'Algo':>5} {'Stock':>6} {'Action':>6} "
              f"{'Qty':>6} {'Price':>10} {'Total':>12} {'Portfolio':>14}")
        print("-" * 120)

        # Print trades
        total_buys = 0
        total_sells = 0
        total_buy_value = 0
        total_sell_value = 0

        for trade in trades:
            (tid, date, algo_id, stock, act, qty, price, portfolio_val, total_val) = trade

            action_str = act.upper()
            if act == 'buy':
                total_buys += 1
                total_buy_value += total_val
            else:
                total_sells += 1
                total_sell_value += total_val

            print(f"{tid:5d} {format_date(date):>10} {algo_id:5d} {stock:>6} {action_str:>6} "
                  f"{qty:6d} {format_currency(price):>10} {format_currency(total_val):>12} "
                  f"{format_currency(portfolio_val):>14}")

        # Print summary
        print("-" * 120)
        print(f"\nSummary:")
        print(f"  Total Trades: {len(trades)}")
        print(f"  Buys:  {total_buys:3d} trades, Total Value: {format_currency(total_buy_value)}")
        print(f"  Sells: {total_sells:3d} trades, Total Value: {format_currency(total_sell_value)}")
        print(f"  Net:   {format_currency(total_sell_value - total_buy_value)} "
              f"({'profit' if total_sell_value > total_buy_value else 'cost'})")

        print("=" * 120)
        print()


def list_trades_by_date(date: Optional[str] = None):
    """
    List all trades for a specific date

    Args:
        date: Date in YYYY-MM-DD format (defaults to today)
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    with DataCache('data/cache.db') as cache:
        query = """
            SELECT
                t.transaction_id,
                t.algorithm_id,
                t.stock_ticker,
                t.action,
                t.quantity,
                t.price,
                t.portfolio_value_after,
                (t.quantity * t.price) as total_value
            FROM transactions t
            WHERE t.date = ?
            ORDER BY t.algorithm_id, t.transaction_id
        """

        cursor = cache.conn.cursor()
        cursor.execute(query, (date,))
        trades = cursor.fetchall()

        if not trades:
            print(f"\nNo trades found for {format_date(date)}\n")
            return

        # Print header
        print("\n" + "=" * 120)
        print(f"TRADES FOR {format_date(date)}")
        print("=" * 120)

        # Group by algorithm
        current_algo = None
        algo_buys = 0
        algo_sells = 0
        algo_buy_value = 0
        algo_sell_value = 0

        for trade in trades:
            (tid, algo_id, stock, act, qty, price, portfolio_val, total_val) = trade

            # Print algorithm header if changed
            if current_algo != algo_id:
                if current_algo is not None:
                    # Print previous algorithm summary
                    print(f"    Algorithm {current_algo} Summary: "
                          f"Buys: {algo_buys}, Sells: {algo_sells}, "
                          f"Net: {format_currency(algo_sell_value - algo_buy_value)}")
                    print()

                current_algo = algo_id
                algo_buys = 0
                algo_sells = 0
                algo_buy_value = 0
                algo_sell_value = 0
                print(f"\nAlgorithm {algo_id}:")
                print(f"  {'ID':>5} {'Stock':>6} {'Action':>6} {'Qty':>6} "
                      f"{'Price':>10} {'Total':>12} {'Portfolio':>14}")
                print("  " + "-" * 80)

            # Print trade
            action_str = act.upper()
            if act == 'buy':
                algo_buys += 1
                algo_buy_value += total_val
            else:
                algo_sells += 1
                algo_sell_value += total_val

            print(f"  {tid:5d} {stock:>6} {action_str:>6} {qty:6d} "
                  f"{format_currency(price):>10} {format_currency(total_val):>12} "
                  f"{format_currency(portfolio_val):>14}")

        # Print last algorithm summary
        if current_algo is not None:
            print(f"    Algorithm {current_algo} Summary: "
                  f"Buys: {algo_buys}, Sells: {algo_sells}, "
                  f"Net: {format_currency(algo_sell_value - algo_buy_value)}")

        print("\n" + "=" * 120)
        print()


def list_trades_by_stock():
    """Show trading activity summary by stock"""
    with DataCache('data/cache.db') as cache:
        query = """
            SELECT
                stock_ticker,
                COUNT(*) as total_trades,
                SUM(CASE WHEN action = 'buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN action = 'sell' THEN 1 ELSE 0 END) as sells,
                SUM(CASE WHEN action = 'buy' THEN quantity ELSE 0 END) as shares_bought,
                SUM(CASE WHEN action = 'sell' THEN quantity ELSE 0 END) as shares_sold,
                SUM(CASE WHEN action = 'buy' THEN quantity * price ELSE 0 END) as buy_value,
                SUM(CASE WHEN action = 'sell' THEN quantity * price ELSE 0 END) as sell_value,
                MIN(date) as first_trade,
                MAX(date) as last_trade
            FROM transactions
            GROUP BY stock_ticker
            ORDER BY total_trades DESC
        """

        cursor = cache.conn.cursor()
        cursor.execute(query)
        stocks = cursor.fetchall()

        if not stocks:
            print("\nNo trades found in database.\n")
            return

        print("\n" + "=" * 120)
        print("TRADING ACTIVITY BY STOCK")
        print("=" * 120)
        print(f"{'Stock':>6} {'Trades':>7} {'Buys':>5} {'Sells':>5} "
              f"{'Shares+':>8} {'Shares-':>8} {'Buy Value':>12} {'Sell Value':>12} "
              f"{'Net':>12} {'First':>10} {'Last':>10}")
        print("-" * 120)

        for stock in stocks:
            (ticker, trades, buys, sells, shares_bought, shares_sold,
             buy_val, sell_val, first, last) = stock

            net = sell_val - buy_val

            print(f"{ticker:>6} {trades:7d} {buys:5d} {sells:5d} "
                  f"{shares_bought:8d} {shares_sold:8d} "
                  f"{format_currency(buy_val):>12} {format_currency(sell_val):>12} "
                  f"{format_currency(net):>12} {format_date(first):>10} {format_date(last):>10}")

        print("=" * 120)
        print()


def main():
    parser = argparse.ArgumentParser(
        description='List recent trades from the genetic stock trading system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Show last 20 trades
  %(prog)s -n 50                    # Show last 50 trades
  %(prog)s -a 0                     # Show trades for algorithm 0
  %(prog)s -s AAPL                  # Show trades for AAPL
  %(prog)s --buy                    # Show only buy trades
  %(prog)s --sell                   # Show only sell trades
  %(prog)s --today                  # Show today's trades
  %(prog)s --date 2025-10-14        # Show trades for specific date
  %(prog)s --by-stock               # Show summary by stock
        """
    )

    parser.add_argument('-n', '--number', type=int, default=20,
                        help='Number of recent trades to show (default: 20)')
    parser.add_argument('-a', '--algorithm', type=int,
                        help='Filter by algorithm ID')
    parser.add_argument('-s', '--stock', type=str,
                        help='Filter by stock ticker (e.g., AAPL)')
    parser.add_argument('--buy', action='store_true',
                        help='Show only buy trades')
    parser.add_argument('--sell', action='store_true',
                        help='Show only sell trades')
    parser.add_argument('--today', action='store_true',
                        help='Show all trades from today')
    parser.add_argument('--date', type=str,
                        help='Show all trades from specific date (YYYY-MM-DD)')
    parser.add_argument('--by-stock', action='store_true',
                        help='Show trading summary by stock')

    args = parser.parse_args()

    # Validate mutually exclusive options
    if args.buy and args.sell:
        print("Error: Cannot use --buy and --sell together")
        sys.exit(1)

    # Route to appropriate function
    if args.by_stock:
        list_trades_by_stock()
    elif args.today:
        list_trades_by_date()
    elif args.date:
        list_trades_by_date(args.date)
    else:
        action = None
        if args.buy:
            action = 'buy'
        elif args.sell:
            action = 'sell'

        list_recent_trades(
            n=args.number,
            algorithm_id=args.algorithm,
            ticker=args.stock,
            action=action
        )


if __name__ == '__main__':
    main()
