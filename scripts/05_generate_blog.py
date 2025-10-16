"""Generate static blog from results"""

import sys
import os
import logging
import yaml
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.cache import DataCache
from src.blog.generator import BlogGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration"""
    with open('config/config.yaml', 'r') as f:
        return yaml.safe_load(f)


def load_results():
    """Load training/validation results"""
    logger.info("Loading results...")

    try:
        with open('results/validation_results.json', 'r') as f:
            results = json.load(f)
        logger.info(f"Loaded {len(results)} algorithm results")
        return results
    except FileNotFoundError:
        logger.warning("No validation results found. Run training first.")
        return []


def main():
    """Generate blog"""
    logger.info("Generating static blog...")

    # Load configuration
    config = load_config()

    # Load results
    results = load_results()

    if not results:
        logger.error("No results to generate blog from!")
        return

    # Transform results to match template expectations
    for result in results:
        # Map validation fields to expected fields
        result['total_return'] = result.get('val_return', 0)
        result['sharpe_ratio'] = result.get('val_sharpe', 0)
        result['max_drawdown'] = result.get('val_max_drawdown', 0)
        result['win_rate'] = result.get('val_win_rate', 0)
        result['num_trades'] = result.get('val_num_trades', 0)

    # Initialize blog generator
    generator = BlogGenerator(
        templates_dir='templates',
        output_dir='blog',
        assets_dir='assets'
    )

    # Determine generation number from results or generation files
    generation = 0
    try:
        # Try to get the latest generation from generation files
        gen_files = [f for f in os.listdir('results/generations') if f.endswith('.json')]
        if gen_files:
            latest_gen_file = max(gen_files)
            generation = int(latest_gen_file.split('_')[1].split('.')[0])
    except Exception:
        # If no generation files, use a default
        generation = 100  # Assuming training completed with default config

    # Load data from cache
    with DataCache('data/cache.db') as cache:
        # Generate all blog pages
        logger.info("Generating blog pages...")

        # Generate index page
        generator.generate_index(results, generation)

        # Generate individual algorithm pages (top 50)
        top_results = sorted(results, key=lambda x: x['val_fitness'], reverse=True)[:50]

        for i, result in enumerate(top_results):
            logger.info(f"Generating page for algorithm {i+1}/50...")

            algo_id = result['algorithm_id']

            # Get portfolio history
            portfolio_history = cache.get_portfolio_history(algo_id)

            # Get transactions
            transactions = cache.get_transactions(algo_id)

            # Add portfolio data to result for template
            result['portfolio_history'] = portfolio_history
            result['transactions'] = transactions

            # Generate page
            generator.generate_chromosome_page(
                chromosome_id=algo_id,
                backtest_results=result,
                rank=i+1
            )

        # Generate generation summary (if available)
        try:
            latest_gen_file = max([f for f in os.listdir('results/generations')
                                  if f.endswith('.json')])
            with open(os.path.join('results/generations', latest_gen_file), 'r') as f:
                generation_data = json.load(f)

            gen_number = int(latest_gen_file.split('_')[1].split('.')[0])
            generator.generate_generation_summary(
                generation=gen_number,
                population_results=results,
                evolution_stats=generation_data
            )
        except Exception as e:
            logger.warning(f"Could not generate generation summary: {e}")

        # Clean up results before saving to JSON (remove DataFrames)
        clean_results = []
        for result in results:
            clean_result = result.copy()
            # Remove non-serializable objects
            if 'portfolio_history' in clean_result:
                del clean_result['portfolio_history']
            if 'transactions' in clean_result:
                del clean_result['transactions']
            clean_results.append(clean_result)

        # Save results as JSON for easy access
        generator.save_results_json(clean_results, generation, 'results.json')

    logger.info("Blog generation complete!")
    logger.info("Open blog/index.html in your browser to view results")


if __name__ == '__main__':
    main()
