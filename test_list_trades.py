"""Insert sample trades for testing the list_trades script"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.data.cache import DataCache

def insert_sample_trades():
    """Insert sample trades for demonstration"""

    with DataCache('data/cache.db') as cache:
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        sample_trades = [
            # Today's trades
            (0, today.strftime('%Y-%m-%d'), 'NVDA', 'buy', 10, 450.25, 8750.00),
            (0, today.strftime('%Y-%m-%d'), 'AAPL', 'sell', 5, 175.80, 4247.50),
            (3, today.strftime('%Y-%m-%d'), 'GOOGL', 'buy', 8, 140.50, 9124.00),
            (1, today.strftime('%Y-%m-%d'), 'MSFT', 'buy', 12, 380.75, 9500.00),
            (2, today.strftime('%Y-%m-%d'), 'META', 'sell', 7, 492.30, 8800.00),

            # Yesterday's trades
            (0, yesterday.strftime('%Y-%m-%d'), 'CVX', 'sell', 15, 155.30, 12500.00),
            (2, yesterday.strftime('%Y-%m-%d'), 'BAC', 'buy', 50, 32.45, 7890.00),
            (1, yesterday.strftime('%Y-%m-%d'), 'TSLA', 'buy', 5, 245.60, 11200.00),
            (3, yesterday.strftime('%Y-%m-%d'), 'JPM', 'sell', 8, 155.25, 9800.00),

            # Two days ago trades
            (0, two_days_ago.strftime('%Y-%m-%d'), 'AAPL', 'buy', 10, 172.50, 9500.00),
            (1, two_days_ago.strftime('%Y-%m-%d'), 'NVDA', 'sell', 5, 445.00, 8200.00),
            (2, two_days_ago.strftime('%Y-%m-%d'), 'GOOGL', 'buy', 6, 138.75, 7250.00),
        ]

        print("Inserting sample trades...")
        for algo_id, date, ticker, action, qty, price, portfolio_val in sample_trades:
            cache.save_transaction(
                algorithm_id=algo_id,
                date=date,
                ticker=ticker,
                action=action,
                quantity=qty,
                price=price,
                portfolio_value=portfolio_val
            )

        print(f"[OK] Inserted {len(sample_trades)} sample trades")
        print("\nNow you can test the list_trades script:")
        print("  python scripts/07_list_trades.py")
        print("  python scripts/07_list_trades.py --today")
        print("  python scripts/07_list_trades.py --by-stock")
        print("  python scripts/07_list_trades.py -a 0")

if __name__ == '__main__':
    insert_sample_trades()
