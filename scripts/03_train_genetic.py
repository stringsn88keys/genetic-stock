"""Train genetic algorithms on historical data"""

import sys
import os
import logging
import yaml
import json
from datetime import datetime
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.cache import DataCache
from src.data.normalizer import DataNormalizer
from src.genetic.evolution import EvolutionEngine
from src.genetic.chromosome import Chromosome
from src.trading.backtest import BacktestEngine

# Create logs directory first
os.makedirs('C:\\\\projects\\\\logs', exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('C:\\\\projects\\\\logs\\\\training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration files"""
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    with open('config/stocks.yaml', 'r') as f:
        stocks = yaml.safe_load(f)
    return config, stocks


def load_training_data(cache, stock_list, config):
    """Load and split training data"""
    logger.info("Loading training data from cache...")

    data_dict = {}
    for ticker in stock_list:
        df = cache.get_price_data(ticker)
        if not df.empty:
            data_dict[ticker] = df
        else:
            logger.warning(f"No data for {ticker}")

    if not data_dict:
        raise ValueError("No training data loaded!")

    # Split data
    train_ratio = config['data']['train_split']
    val_ratio = config['data']['validation_split']

    train_data = {}
    val_data = {}
    test_data = {}

    normalizer = DataNormalizer()

    for ticker, df in data_dict.items():
        # Add technical features
        df = normalizer.calculate_technical_features(df)

        # Split
        train_df, val_df, test_df = normalizer.split_train_val_test(
            df, train_ratio, val_ratio, config['data']['test_split']
        )

        train_data[ticker] = train_df
        val_data[ticker] = val_df
        test_data[ticker] = test_df

    logger.info(f"Loaded data for {len(data_dict)} stocks")
    return train_data, val_data, test_data


def create_fitness_function(train_data, config):
    """Create fitness function for evaluation"""

    def fitness_function(chromosome: Chromosome) -> float:
        """Evaluate chromosome fitness on training data"""
        try:
            # Run backtest
            backtest = BacktestEngine(
                chromosome=chromosome,
                initial_capital=config['population']['initial_capital'],
                commission=config['trading'].get('commission', 0.0),
                slippage=config['trading'].get('slippage', 0.001),
                max_positions=config['trading'].get('max_positions', 10),
                min_cash_reserve=config['trading'].get('min_cash_reserve', 0.05)
            )

            results = backtest.run(stock_data=train_data)

            # Calculate fitness using fitness evaluator
            from src.genetic.fitness import FitnessEvaluator
            fitness_evaluator = FitnessEvaluator(config)

            # Build performance metrics dict for fitness calculation
            performance_metrics = {
                'total_return': results.get('total_return', 0.0) / 100.0,  # Convert % to decimal
                'sharpe_ratio': results.get('sharpe_ratio', 0.0),
                'win_rate': results.get('win_rate', 0.0) / 100.0,  # Convert % to decimal
                'max_drawdown': abs(results.get('max_drawdown', 0.0)) / 100.0,  # Convert % to decimal, abs
                'n_trades': results.get('num_trades', 0),
                'transaction_cost_ratio': (results.get('total_commission', 0) + results.get('total_slippage', 0)) /
                                         max(abs(results.get('total_profit', 0.01)), 0.01)
            }

            fitness = fitness_evaluator.calculate_fitness(performance_metrics)
            return fitness

        except Exception as e:
            logger.error(f"Error evaluating chromosome: {e}")
            return -999.0

    return fitness_function


def save_generation_results(population, generation, output_dir='results/generations'):
    """Save generation results"""
    os.makedirs(output_dir, exist_ok=True)

    # Save population
    results = population.to_dict_list()

    filename = os.path.join(output_dir, f'generation_{generation:03d}.json')
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Saved generation {generation} to {filename}")


def main():
    """Main training loop"""
    logger.info("=" * 80)
    logger.info("Genetic Algorithm Trading System - Training")
    logger.info("=" * 80)

    # Create directories
    os.makedirs('C:\\\\projects\\\\logs', exist_ok=True)
    os.makedirs('results/generations', exist_ok=True)
    os.makedirs('results/backtests', exist_ok=True)

    # Load configuration
    config, stocks_config = load_config()
    stock_list = stocks_config['all_stocks']
    n_generations = config['evolution']['generations']

    logger.info(f"Population size: {config['population']['size']}")
    logger.info(f"Generations: {n_generations}")
    logger.info(f"Stocks: {len(stock_list)}")

    # Load data
    with DataCache('data/cache.db') as cache:
        train_data, val_data, test_data = load_training_data(cache, stock_list, config)

    # Initialize evolution engine
    logger.info("Initializing evolution engine...")
    evolution = EvolutionEngine(config, stock_list)
    evolution.initialize()

    # Create fitness function
    fitness_fn = create_fitness_function(train_data, config)

    # Callback to save results
    def generation_callback(population, stats):
        """Called after each generation"""
        logger.info(f"Generation {stats['generation']}: "
                   f"Best={stats['best_fitness']:.4f}, "
                   f"Mean={stats['mean_fitness']:.4f}, "
                   f"Diversity={stats['diversity']:.4f}")

        # Save every 10 generations
        if stats['generation'] % 10 == 0:
            save_generation_results(population, stats['generation'])

    # Run evolution
    logger.info("Starting evolution...")
    start_time = datetime.now()

    evolution.run_evolution(
        n_generations=n_generations,
        fitness_function=fitness_fn,
        callback=generation_callback
    )

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60

    logger.info(f"Evolution complete! Duration: {duration:.1f} minutes")

    # Save final population
    save_generation_results(evolution.population, n_generations)

    # Get best individuals
    logger.info("Evaluating top performers on validation data...")
    top_performers = evolution.get_top_individuals(n=100)

    validation_results = []
    from src.genetic.fitness import FitnessEvaluator
    fitness_evaluator = FitnessEvaluator(config)

    for i, (chromosome, train_fitness) in enumerate(top_performers[:50]):
        logger.info(f"Validating #{i+1}/50...")

        try:
            # Validate on validation set
            backtest = BacktestEngine(
                chromosome=chromosome,
                initial_capital=config['population']['initial_capital'],
                commission=config['trading'].get('commission', 0.0),
                slippage=config['trading'].get('slippage', 0.001),
                max_positions=config['trading'].get('max_positions', 10),
                min_cash_reserve=config['trading'].get('min_cash_reserve', 0.05)
            )

            val_results = backtest.run(stock_data=val_data)

            # Calculate fitness
            performance_metrics = {
                'total_return': val_results.get('total_return', 0.0) / 100.0,
                'sharpe_ratio': val_results.get('sharpe_ratio', 0.0),
                'win_rate': val_results.get('win_rate', 0.0) / 100.0,
                'max_drawdown': abs(val_results.get('max_drawdown', 0.0)) / 100.0,
                'n_trades': val_results.get('num_trades', 0),
                'transaction_cost_ratio': (val_results.get('total_commission', 0) + val_results.get('total_slippage', 0)) /
                                         max(abs(val_results.get('total_profit', 0.01)), 0.01)
            }

            val_fitness = fitness_evaluator.calculate_fitness(performance_metrics)

            validation_results.append({
                'algorithm_id': i,
                'train_fitness': train_fitness,
                'val_fitness': val_fitness,
                'val_return': val_results.get('total_return', 0.0),
                'val_sharpe': val_results.get('sharpe_ratio', 0.0),
                'chromosome': chromosome.to_dict()
            })
        except Exception as e:
            logger.error(f"Error validating algorithm {i}: {e}")
            continue

    # Save validation results
    with open('results/validation_results.json', 'w') as f:
        json.dump(validation_results, f, indent=2)

    # Summary
    logger.info("=" * 80)
    logger.info("Training Summary:")
    logger.info(f"  Total generations: {n_generations}")
    logger.info(f"  Training time: {duration:.1f} minutes")
    logger.info(f"  Best training fitness: {top_performers[0][1]:.4f}")
    logger.info(f"  Top validation fitness: {max(r['val_fitness'] for r in validation_results):.4f}")
    logger.info("=" * 80)

    logger.info("Training complete! Results saved to results/")


if __name__ == '__main__':
    main()
