"""Setup database for genetic trading system"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.cache import DataCache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Initialize database"""
    logger.info("Setting up database...")

    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)

    # Initialize database
    with DataCache('data/cache.db') as cache:
        cache.create_tables()

    logger.info("Database setup complete!")
    logger.info("Database location: data/cache.db")


if __name__ == '__main__':
    main()
