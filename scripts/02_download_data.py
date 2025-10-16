"""Download historical stock data"""

import sys
import os
import logging
from datetime import datetime, timedelta
import yaml
from dotenv import load_dotenv

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


def main():
    """Download and cache stock data"""
    logger.info("Starting data download...")

    # Load configuration
    config, stocks_config = load_config()
    stock_list = stocks_config['all_stocks']

    # Calculate date range
    years = config['data']['historical_years']

    # Use yesterday as end date (market data not available for today)
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=years * 365)

    # If it's weekend, go back to Friday
    while end_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
        end_date -= timedelta(days=1)

    logger.info(f"Downloading {len(stock_list)} stocks from {start_date.date()} to {end_date.date()}")

    # Initialize components
    fetcher = DataFetcher(
        primary_source=config['data_sources']['primary'],
        fallback_enabled=config['data_sources']['fallback_enabled']
    )
    normalizer = DataNormalizer(volume_ma_window=config['data']['volume_ma_window'])

    # Download data
    data_dict = fetcher.fetch_multiple_tickers(
        stock_list,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )

    # Validate data
    logger.info("Validating downloaded data...")
    validation_results = DataValidator.validate_multiple_tickers(data_dict)

    # Process and cache data
    logger.info("Normalizing and caching data...")
    with DataCache('data/cache.db') as cache:
        for ticker, df in data_dict.items():
            if df is not None and not df.empty:
                # Normalize
                df_normalized = normalizer.normalize_full(df)

                # Save to cache
                cache.save_price_data(ticker, df_normalized, source='yahoo')
                logger.info(f"Cached {ticker}: {len(df_normalized)} records")
            else:
                logger.warning(f"Skipping {ticker}: no data available")

    # Summary
    successful = sum(1 for v in data_dict.values() if v is not None and not v.empty)
    logger.info(f"Download complete: {successful}/{len(stock_list)} stocks cached")

    # Validation summary
    valid_count = sum(1 for r in validation_results.values() if r.get('is_valid', False))
    logger.info(f"Validation: {valid_count}/{len(validation_results)} stocks valid")

    # Save validation results to file
    import json
    os.makedirs('results', exist_ok=True)
    with open('results/data_validation.json', 'w') as f:
        json.dump(validation_results, f, indent=2, default=str)
    logger.info("Validation results saved to results/data_validation.json")


if __name__ == '__main__':
    main()
