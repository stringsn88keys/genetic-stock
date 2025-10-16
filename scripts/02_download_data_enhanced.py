"""Enhanced data download script with incremental updates"""

import sys
import os
import logging
from datetime import datetime, timedelta
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.fetchers import DataFetcher
from src.data.cache import DataCache
from src.data.normalizer import DataNormalizer
from src.data.validators import DataValidator

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration files"""
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    with open('config/stocks.yaml', 'r') as f:
        stocks = yaml.safe_load(f)
    return config, stocks


def get_missing_date_ranges(cache, ticker, start_date, end_date):
    """
    Determine what date ranges are missing for a ticker

    Returns:
        List of (start, end) tuples for missing ranges
    """
    # Check what data we have
    existing_start, existing_end = cache.get_date_range(ticker)

    if not existing_start:
        # No data at all
        return [(start_date, end_date)]

    # Convert to datetime for comparison
    existing_start = datetime.strptime(str(existing_start), '%Y-%m-%d').date()
    existing_end = datetime.strptime(str(existing_end), '%Y-%m-%d').date()
    target_start = datetime.strptime(start_date, '%Y-%m-%d').date()
    target_end = datetime.strptime(end_date, '%Y-%m-%d').date()

    missing_ranges = []

    # Check for data before existing range
    if target_start < existing_start:
        missing_ranges.append((
            target_start.strftime('%Y-%m-%d'),
            (existing_start - timedelta(days=1)).strftime('%Y-%m-%d')
        ))

    # Check for data after existing range
    if target_end > existing_end:
        # Add buffer to catch up recent days
        catchup_start = max(existing_end + timedelta(days=1), target_start)
        if catchup_start <= target_end:
            missing_ranges.append((
                catchup_start.strftime('%Y-%m-%d'),
                target_end.strftime('%Y-%m-%d')
            ))

    return missing_ranges


def main(incremental=True, force_full=False):
    """
    Download and cache stock data

    Args:
        incremental: If True, only download missing data
        force_full: If True, re-download all data
    """
    logger.info("=" * 80)
    logger.info("Enhanced Data Download")
    logger.info(f"Mode: {'Full Download' if force_full else 'Incremental Update'}")
    logger.info("=" * 80)

    # Load configuration
    config, stocks_config = load_config()
    stock_list = stocks_config['all_stocks']

    # Calculate date range
    years = config['data']['historical_years']

    # Use yesterday as end date (market data not available for today)
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=years * 365)

    # If it's weekend/Monday morning, go back further
    # This ensures we don't try to fetch non-trading days
    while end_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
        end_date -= timedelta(days=1)

    logger.info(f"Target date range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Processing {len(stock_list)} stocks")

    # Initialize components
    fetcher = DataFetcher(
        primary_source=config['data_sources']['primary'],
        fallback_enabled=config['data_sources']['fallback_enabled']
    )
    normalizer = DataNormalizer(volume_ma_window=config['data']['volume_ma_window'])

    # Track statistics
    stats = {
        'updated': 0,
        'skipped': 0,
        'failed': 0,
        'new_records': 0
    }

    with DataCache('data/cache.db') as cache:
        for ticker in tqdm(stock_list, desc="Processing stocks"):
            try:
                if incremental and not force_full:
                    # Check what data is missing
                    missing_ranges = get_missing_date_ranges(
                        cache, ticker,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )

                    if not missing_ranges:
                        logger.info(f"{ticker}: Up to date")
                        stats['skipped'] += 1
                        continue

                    # Download missing ranges
                    all_dfs = []
                    for range_start, range_end in missing_ranges:
                        logger.info(f"{ticker}: Fetching {range_start} to {range_end}")

                        df = fetcher.fetch_historical_data(
                            ticker, range_start, range_end
                        )

                        if df is not None and not df.empty:
                            all_dfs.append(df)

                    if not all_dfs:
                        logger.warning(f"{ticker}: No new data available")
                        stats['skipped'] += 1
                        continue

                    # Combine all downloaded data
                    import pandas as pd
                    df_combined = pd.concat(all_dfs).drop_duplicates()
                    df_normalized = normalizer.normalize_full(df_combined)

                else:
                    # Full download
                    logger.info(f"{ticker}: Full download")
                    df = fetcher.fetch_historical_data(
                        ticker,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )

                    if df is None or df.empty:
                        logger.warning(f"{ticker}: No data available")
                        stats['failed'] += 1
                        continue

                    df_normalized = normalizer.normalize_full(df)

                # Save to cache
                cache.save_price_data(ticker, df_normalized, source='yahoo')
                stats['updated'] += 1
                stats['new_records'] += len(df_normalized)

                logger.info(f"{ticker}: Saved {len(df_normalized)} records")

            except Exception as e:
                logger.error(f"{ticker}: Error - {e}")
                stats['failed'] += 1
                continue

    # Validate data
    logger.info("Validating downloaded data...")
    data_dict = {}

    with DataCache('data/cache.db') as cache:
        for ticker in stock_list:
            df = cache.get_price_data(ticker)
            if not df.empty:
                data_dict[ticker] = df

    validation_results = DataValidator.validate_multiple_tickers(data_dict)

    # Save validation results
    import json
    os.makedirs('results', exist_ok=True)
    with open('results/data_validation.json', 'w') as f:
        json.dump(validation_results, f, indent=2, default=str)

    # Summary
    logger.info("=" * 80)
    logger.info("Download Summary:")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Skipped (up to date): {stats['skipped']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info(f"  New records: {stats['new_records']}")

    valid_count = sum(1 for r in validation_results.values() if r.get('is_valid', False))
    logger.info(f"  Validation: {valid_count}/{len(validation_results)} stocks valid")
    logger.info("=" * 80)

    logger.info("Data download complete!")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Download stock data')
    parser.add_argument('--full', action='store_true',
                       help='Force full download (ignore existing data)')
    parser.add_argument('--no-incremental', action='store_true',
                       help='Disable incremental mode')

    args = parser.parse_args()

    main(
        incremental=not args.no_incremental,
        force_full=args.full
    )
