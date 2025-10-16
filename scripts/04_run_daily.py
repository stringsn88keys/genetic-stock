"""Run daily trading operations"""

import sys
import os
import logging
import yaml
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

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

# Setup logging\nlogging.basicConfig(\n    level=logging.INFO,\n    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',\n    handlers=[\n        logging.FileHandler('C:\\\\projects\\\\logs\\\\daily_trading.log'),\n        logging.StreamHandler()\n    ]\n)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration files"""
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    with open('config/stocks.yaml', 'r') as f:
        stocks = yaml.safe_load(f)
    return config, stocks


def load_algorithms():
    """Load trained algorithms"""
    logger.info("Loading trained algorithms...")

    # Load validation results to get best algorithms
    with open('results/validation_results.json', 'r') as f:
        validation_results = json.load(f)

    # Sort by validation fitness
    validation_results.sort(key=lambda x: x['val_fitness'], reverse=True)

    # Take top 1000 (or however many we have)
    algorithms = []
    for result in validation_results[:1000]:
        chromosome = Chromosome()
        chromosome.from_dict(result['chromosome'])
        algorithms.append({
            'id': result['algorithm_id'],
            'chromosome': chromosome,
            'fitness': result['val_fitness']
        })

    logger.info(f"Loaded {len(algorithms)} algorithms")
    return algorithms


def update_latest_data(cache, fetcher, stock_list):
    """Fetch latest data and update cache"""
    logger.info("Fetching latest market data...")

    today = datetime.now()
    yesterday = today - timedelta(days=7)  # Get last week to ensure we have data

    normalizer = DataNormalizer()

    for ticker in stock_list:
        try:
            # Fetch latest data
            df = fetcher.fetch_historical_data(
                ticker,
                yesterday.strftime('%Y-%m-%d'),
                today.strftime('%Y-%m-%d')
            )

            if not df.empty:
                # Normalize
                df_normalized = normalizer.normalize_full(df)

                # Update cache
                cache.save_price_data(ticker, df_normalized, source='yahoo')
                logger.info(f"Updated {ticker}: {len(df_normalized)} records")

        except Exception as e:
            logger.error(f"Error updating {ticker}: {e}")


def execute_daily_trades(algorithms, data_dict, config, cache):
    """Execute trades for all algorithms"""
    logger.info(f"Executing trades for {len(algorithms)} algorithms...")

    today = datetime.now().strftime('%Y-%m-%d')
    executed_count = 0

    for algo in algorithms:
        algo_id = algo['id']
        chromosome = algo['chromosome']

        try:
            # Get current portfolio state from database
            # For simplicity, we'll start fresh each day
            # In production, you'd load the actual portfolio state

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

            # Generate signals for today
            signals = {}
            for ticker, df in data_dict.items():
                if not df.empty:
                    # Get the last row of features
                    latest_features = df.iloc[-1]
                    signal = signal_gen.generate_signal(latest_features)
                    if signal != 'hold':
                        signals[ticker] = signal

            # Execute signals
            if signals:
                # execute_signals returns a dict of {ticker: action_string}
                # We need to extract prices for the trades
                prices = {ticker: df.iloc[-1]['close'] if 'close' in df.columns
                         else df.iloc[-1]['normalized_close']
                         for ticker, df in data_dict.items() if not df.empty}

                # Track number of trades before execution
                trades_before = len(portfolio.trade_history)

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

                if actions:
                    executed_count += 1

            # Save portfolio value
            cache.save_portfolio_value(
                algorithm_id=algo_id,
                date=today,
                cash=portfolio.cash,
                positions_value=portfolio.get_positions_value(),
                total_value=portfolio.get_total_value()
            )

        except Exception as e:
            logger.error(f"Error executing trades for algorithm {algo_id}: {e}")

    logger.info(f"Executed trades for {executed_count}/{len(algorithms)} algorithms")


def main():
    """Main daily execution"""
    logger.info("=" * 80)
    logger.info("Daily Trading Execution - " + datetime.now().strftime('%Y-%m-%d'))
    logger.info("=" * 80)

    # Load configuration
    config, stocks_config = load_config()
    stock_list = stocks_config['all_stocks']

    # Initialize components
    fetcher = DataFetcher(
        primary_source=config['data_sources']['primary'],
        fallback_enabled=config['data_sources']['fallback_enabled']
    )

    # Update data
    with DataCache('data/cache.db') as cache:
        update_latest_data(cache, fetcher, stock_list)

        # Load latest data
        data_dict = {}
        for ticker in stock_list:
            df = cache.get_price_data(ticker)
            if not df.empty:
                data_dict[ticker] = df

        # Load algorithms
        algorithms = load_algorithms()

        # Execute trades
        execute_daily_trades(algorithms, data_dict, config, cache)

    logger.info("Daily execution complete!")


if __name__ == '__main__':
    main()
