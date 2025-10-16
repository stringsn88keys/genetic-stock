"""After-market update script - Run at 5PM after market close

IMPORTANT: This script generates trade signals based on today's closing data.
In a live trading system, these signals would be executed at tomorrow's market open.
For backtesting purposes, the signals are stored but the actual execution timing
(next day's open price) is handled by the backtesting engine to avoid look-ahead bias.
"""

import sys
import os
import logging
import yaml
import json
from datetime import datetime, timedelta, time
from dotenv import load_dotenv
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.fetchers import DataFetcher
from src.data.cache import DataCache
from src.data.normalizer import DataNormalizer
from src.genetic.chromosome import Chromosome
from src.trading.signals import SignalGenerator
from src.trading.portfolio import Portfolio
from src.trading.executor import TradeExecutor

# Load environment variables
load_dotenv()

# Setup logging\nlogging.basicConfig(\n    level=logging.INFO,\n    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',\n    handlers=[\n        logging.FileHandler('C:\\\\projects\\\\logs\\\\after_market_trading.log'),\n        logging.StreamHandler()\n    ]\n)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration files"""
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    with open('config/stocks.yaml', 'r') as f:
        stocks = yaml.safe_load(f)
    return config, stocks


def is_market_day():
    """Check if today is a market day (weekday)"""
    today = datetime.now()
    # 0 = Monday, 6 = Sunday
    return today.weekday() < 5


def check_if_already_run_today(cache):
    """Check if we've already processed trades today (idempotent check)"""
    today = datetime.now().strftime('%Y-%m-%d')

    cursor = cache.conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM daily_portfolio_values
        WHERE date = ?
    """, (today,))

    count = cursor.fetchone()[0]
    return count > 0


def load_algorithms(top_n=10):
    """Load top N algorithms by validation fitness"""
    logger.info(f"Loading top {top_n} algorithms...")

    with open('results/validation_results.json', 'r') as f:
        validation_results = json.load(f)

    # Sort by validation fitness
    validation_results.sort(key=lambda x: x['val_fitness'], reverse=True)

    algorithms = []
    for result in validation_results[:top_n]:
        chromosome = Chromosome()
        chromosome.from_dict(result['chromosome'])
        algorithms.append({
            'id': result['algorithm_id'],
            'chromosome': chromosome,
            'fitness': result['val_fitness'],
            'return': result.get('val_return', 0),
            'sharpe': result.get('val_sharpe', 0)
        })

    logger.info(f"Loaded {len(algorithms)} algorithms")
    return algorithms


def update_market_data(cache, fetcher, stock_list):
    """Fetch latest market data and update cache"""
    logger.info("Fetching latest market data...")

    today = datetime.now()
    week_ago = today - timedelta(days=7)

    normalizer = DataNormalizer()
    updated_count = 0

    for ticker in stock_list:
        try:
            # Fetch latest data
            df = fetcher.fetch_historical_data(
                ticker,
                week_ago.strftime('%Y-%m-%d'),
                today.strftime('%Y-%m-%d')
            )

            if not df.empty:
                # Normalize
                df_normalized = normalizer.normalize_full(df)

                # Update cache
                cache.save_price_data(ticker, df_normalized, source='yahoo')
                updated_count += 1
                logger.debug(f"Updated {ticker}: {len(df_normalized)} records")

        except Exception as e:
            logger.error(f"Error updating {ticker}: {e}")

    logger.info(f"Updated {updated_count}/{len(stock_list)} stocks")
    return updated_count


def execute_algorithm_trades(algo, data_dict, config, cache, today):
    """Execute trades for a single algorithm"""
    algo_id = algo['id']
    chromosome = algo['chromosome']

    # Create portfolio with initial capital
    portfolio = Portfolio(
        initial_capital=config['population']['initial_capital'],
        commission=config['trading']['commission'],
        slippage=config['trading']['slippage']
    )

    # Create executor and signal generator
    executor = TradeExecutor(
        portfolio=portfolio,
        chromosome=chromosome,
        max_positions=config['trading']['max_positions'],
        min_cash_reserve=config['trading']['min_cash_reserve']
    )
    signal_gen = SignalGenerator(chromosome)

    # Generate signals based on today's closing data
    # NOTE: In a real trading system, these signals would be queued for execution
    # at tomorrow's market open. For demonstration/backtesting, we record them now,
    # but the backtest engine correctly executes at next day's open to avoid look-ahead bias.
    signals = {}
    for ticker, df in data_dict.items():
        if not df.empty:
            # Get the last row of features (today's close data)
            latest_features = df.iloc[-1]
            signal = signal_gen.generate_signal(latest_features)
            if signal != 'hold':
                signals[ticker] = signal

    # Record signals for tracking/demonstration purposes
    # In live trading: these would execute at tomorrow's open
    # In backtesting: execution timing is handled correctly by BacktestEngine
    new_trades = []
    if signals:
        # Use today's close price for recording purposes only
        # Real execution would use tomorrow's open price
        prices = {
            ticker: df.iloc[-1]['close'] if 'close' in df.columns
            else df.iloc[-1]['normalized_close']
            for ticker, df in data_dict.items() if not df.empty
        }

        # Track number of trades before execution
        trades_before = len(portfolio.trade_history)

        # Execute signals
        actions = executor.execute_signals(signals, prices, today)

        # Get new trades that were added to portfolio history
        new_trades = portfolio.trade_history[trades_before:]

        # Save trades to database
        if new_trades:
            for trade in new_trades:
                cache.save_transaction(
                    algorithm_id=algo_id,
                    date=today,
                    ticker=trade.ticker,
                    action=trade.action,
                    quantity=trade.shares,
                    price=trade.price,
                    portfolio_value=portfolio.get_total_value()
                )

    # Save portfolio value
    cache.save_portfolio_value(
        algorithm_id=algo_id,
        date=today,
        cash=portfolio.cash,
        positions_value=portfolio.get_positions_value(),
        total_value=portfolio.get_total_value()
    )

    return {
        'algorithm_id': algo_id,
        'signals': signals,
        'trades': new_trades,
        'portfolio_value': portfolio.get_total_value()
    }


def format_trade_report(results):
    """Format a nice report of today's trades"""
    report = []
    report.append("=" * 80)
    report.append(f"AFTER-MARKET TRADING REPORT - {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    report.append("=" * 80)

    total_trades = sum(len(r['trades']) for r in results)
    algos_with_trades = sum(1 for r in results if len(r['trades']) > 0)

    report.append(f"\nSummary:")
    report.append(f"  Algorithms Analyzed: {len(results)}")
    report.append(f"  Algorithms with Trades: {algos_with_trades}")
    report.append(f"  Total Trades Executed: {total_trades}")

    if total_trades > 0:
        report.append("\n" + "=" * 80)
        report.append("TRADES BY ALGORITHM")
        report.append("=" * 80)

        for result in results:
            if result['trades']:
                report.append(f"\nAlgorithm {result['algorithm_id']}:")
                report.append(f"  Portfolio Value: ${result['portfolio_value']:,.2f}")
                report.append(f"  Trades:")

                for trade in result['trades']:
                    action_symbol = "[BUY] " if trade.action == 'buy' else "[SELL]"
                    report.append(
                        f"    {action_symbol} {trade.ticker:6s} "
                        f"{int(trade.shares):4d} shares @ ${trade.price:7.2f} "
                        f"= ${trade.shares * trade.price:10,.2f}"
                    )

        # Group trades by ticker
        report.append("\n" + "=" * 80)
        report.append("TRADES BY STOCK")
        report.append("=" * 80)

        ticker_trades = {}
        for result in results:
            for trade in result['trades']:
                if trade.ticker not in ticker_trades:
                    ticker_trades[trade.ticker] = {'buy': 0, 'sell': 0, 'total_value': 0}

                if trade.action == 'buy':
                    ticker_trades[trade.ticker]['buy'] += trade.shares
                else:
                    ticker_trades[trade.ticker]['sell'] += trade.shares

                ticker_trades[trade.ticker]['total_value'] += trade.shares * trade.price

        for ticker in sorted(ticker_trades.keys()):
            info = ticker_trades[ticker]
            report.append(
                f"\n{ticker:6s}: "
                f"Buy: {info['buy']:4d} shares, "
                f"Sell: {info['sell']:4d} shares, "
                f"Total Value: ${info['total_value']:,.2f}"
            )
    else:
        report.append("\n[OK] No trades executed today - all algorithms holding positions")

    report.append("\n" + "=" * 80)

    return "\n".join(report)


def main():
    """Main execution"""
    start_time = datetime.now()

    logger.info("=" * 80)
    logger.info(f"After-Market Update Starting - {start_time.strftime('%Y-%m-%d %I:%M %p')}")
    logger.info("=" * 80)

    # Check if it's a market day
    if not is_market_day():
        logger.info("Not a market day (weekend). Skipping update.")
        print("\n>> Market closed today (weekend). No update needed.\n")
        return

    # Check current time (optional - for logging purposes)
    current_time = datetime.now().time()
    market_close = time(16, 0)  # 4:00 PM
    if current_time < market_close:
        logger.warning(f"Running before market close ({current_time.strftime('%I:%M %p')})")
        print(f"\n>> Note: Market closes at 4:00 PM ET. Current time: {current_time.strftime('%I:%M %p')}\n")

    # Load configuration
    config, stocks_config = load_config()
    stock_list = stocks_config['all_stocks']

    # Initialize components
    fetcher = DataFetcher(
        primary_source=config['data_sources']['primary'],
        fallback_enabled=config['data_sources']['fallback_enabled']
    )

    today = datetime.now().strftime('%Y-%m-%d')

    with DataCache('data/cache.db') as cache:
        # Idempotent check - skip if already run today
        if check_if_already_run_today(cache):
            logger.info(f"Already processed trades for {today}. Skipping (idempotent).")
            print(f"\n[OK] Already processed trades for {today}. No duplicate execution.\n")

            # Still show what was traded today
            cursor = cache.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM transactions WHERE date = ?
            """, (today,))
            trade_count = cursor.fetchone()[0]

            if trade_count > 0:
                print(f"[INFO] {trade_count} trades were executed earlier today.")
                print(f"       Check C:\projects\logs\after_market_trading.log for details.\n")

            return

        # Update market data
        update_market_data(cache, fetcher, stock_list)

        # Load latest data
        data_dict = {}
        for ticker in stock_list:
            df = cache.get_price_data(ticker)
            if not df.empty:
                data_dict[ticker] = df

        if not data_dict:
            logger.error("No market data available. Cannot execute trades.")
            print("\n[ERROR] No market data available.\n")
            return

        # Load top algorithms
        algorithms = load_algorithms(top_n=10)

        # Execute trades for each algorithm
        logger.info(f"Executing trades for {len(algorithms)} algorithms...")
        results = []

        for algo in algorithms:
            try:
                result = execute_algorithm_trades(algo, data_dict, config, cache, today)
                results.append(result)
            except Exception as e:
                logger.error(f"Error executing trades for algorithm {algo['id']}: {e}")

        # Generate and display report
        report = format_trade_report(results)
        print("\n" + report)
        logger.info("\n" + report)

    # Log completion time
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"After-market update complete! Duration: {duration:.1f}s")
    print(f"\n[SUCCESS] Update complete in {duration:.1f}s\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[WARN] Update interrupted by user\n")
        logger.warning("Update interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n[ERROR] Fatal error: {e}\n")
        raise
