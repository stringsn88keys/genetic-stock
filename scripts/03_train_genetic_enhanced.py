"""Enhanced training script with checkpointing, parallel processing, and GPU support"""

import sys
import os
import logging
import yaml
import json
import pickle
from datetime import datetime
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import psutil

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.cache import DataCache
from src.data.normalizer import DataNormalizer
from src.genetic.evolution import EvolutionEngine
from src.genetic.chromosome import Chromosome
from src.trading.backtest import BacktestEngine
from src.genetic.fitness import FitnessEvaluator

# Create logs directory first
os.makedirs('C:\\projects\\logs', exist_ok=True)
os.makedirs('checkpoints', exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('C:\\projects\\logs\\training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Check for GPU support
try:
    import cupy as cp
    GPU_AVAILABLE = True

    # Test if CUDA actually works
    try:
        device_count = cp.cuda.runtime.getDeviceCount()
        props = cp.cuda.runtime.getDeviceProperties(0)
        gpu_name = props['name'].decode('utf-8')
        logger.info(f"GPU (CuPy) available: {gpu_name} ({device_count} device(s))")
    except Exception as e:
        if 'nvrtc' in str(e).lower():
            logger.warning(f"GPU available but NVRTC library missing - basic operations only")
            logger.warning(f"  To fix: Run 'python scripts/fix_cupy_cuda_version.py'")
        else:
            logger.warning(f"GPU detection warning: {e}")
        logger.info("GPU (CuPy) available - proceeding with available functionality")

except ImportError:
    GPU_AVAILABLE = False
    logger.info("GPU not available, using CPU only")


def get_optimal_workers():
    """Determine optimal number of worker processes"""
    cpu_count = psutil.cpu_count(logical=True)
    memory_gb = psutil.virtual_memory().total / (1024**3)

    # Use 75% of CPUs, but leave at least 2 cores free
    optimal = max(1, min(cpu_count - 2, int(cpu_count * 0.75)))

    # Adjust for memory (assume each worker needs ~2GB)
    memory_limited = max(1, int(memory_gb / 2))

    workers = min(optimal, memory_limited)
    logger.info(f"Using {workers} worker processes (CPU cores: {cpu_count}, RAM: {memory_gb:.1f}GB)")

    return workers


def save_checkpoint(checkpoint_path, evolution, generation, config, validation_results=None):
    """Save training checkpoint"""
    checkpoint = {
        'generation': generation,
        'population': evolution.population.to_dict_list(),
        'history': evolution.history,
        'config': config,
        'timestamp': datetime.now().isoformat()
    }

    if validation_results:
        checkpoint['validation_results'] = validation_results

    with open(checkpoint_path, 'wb') as f:
        pickle.dump(checkpoint, f)

    logger.info(f"Checkpoint saved: {checkpoint_path}")


def load_checkpoint(checkpoint_path):
    """Load training checkpoint"""
    if not os.path.exists(checkpoint_path):
        return None

    try:
        with open(checkpoint_path, 'rb') as f:
            checkpoint = pickle.load(f)

        logger.info(f"Loaded checkpoint from generation {checkpoint['generation']}")
        return checkpoint
    except Exception as e:
        logger.error(f"Error loading checkpoint: {e}")
        return None


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
    for ticker in tqdm(stock_list, desc="Loading stocks"):
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

    for ticker in tqdm(data_dict.keys(), desc="Processing stocks"):
        df = data_dict[ticker]

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

    # Log date ranges
    if train_data:
        sample_ticker = list(train_data.keys())[0]
        train_start = train_data[sample_ticker].index.min()
        train_end = train_data[sample_ticker].index.max()
        logger.info(f"Training period: {train_start.date()} to {train_end.date()}")

    return train_data, val_data, test_data


def evaluate_chromosome_worker(args):
    """Worker function for parallel fitness evaluation"""
    chromosome_dict, train_data, config, use_gpu = args

    try:
        # Reconstruct chromosome
        chromosome = Chromosome(config, list(train_data.keys()))
        chromosome.from_dict(chromosome_dict)

        # Run backtest with GPU acceleration
        backtest = BacktestEngine(
            chromosome=chromosome,
            initial_capital=config['population']['initial_capital'],
            commission=config['trading'].get('commission', 0.0),
            slippage=config['trading'].get('slippage', 0.001),
            max_positions=config['trading'].get('max_positions', 10),
            min_cash_reserve=config['trading'].get('min_cash_reserve', 0.05),
            use_gpu=use_gpu
        )

        results = backtest.run(stock_data=train_data)

        # Calculate fitness
        fitness_evaluator = FitnessEvaluator(config)
        performance_metrics = {
            'total_return': results.get('total_return', 0.0) / 100.0,
            'sharpe_ratio': results.get('sharpe_ratio', 0.0),
            'win_rate': results.get('win_rate', 0.0) / 100.0,
            'max_drawdown': abs(results.get('max_drawdown', 0.0)) / 100.0,
            'n_trades': results.get('num_trades', 0),
            'transaction_cost_ratio': (results.get('total_commission', 0) + results.get('total_slippage', 0)) /
                                     max(abs(results.get('total_profit', 0.01)), 0.01)
        }

        fitness = fitness_evaluator.calculate_fitness(performance_metrics)

        # Return date range info for progress tracking
        date_info = {
            'start': results.get('start_date'),
            'end': results.get('end_date'),
            'days': results.get('trading_days', 0)
        }

        return fitness, date_info

    except Exception as e:
        logger.error(f"Error evaluating chromosome: {e}")
        return -999.0, {}


def parallel_fitness_evaluation(population, train_data, config, n_workers, use_gpu=True):
    """Evaluate fitness for entire population in parallel"""
    logger.info(f"Evaluating {len(population.individuals)} chromosomes using {n_workers} workers...")

    if use_gpu:
        logger.info("GPU acceleration enabled for worker processes")
    else:
        logger.info("GPU acceleration disabled, using CPU only")

    # Prepare arguments for workers
    args_list = [
        (ind.to_dict(), train_data, config, use_gpu)
        for ind in population.individuals
    ]

    fitness_scores = [0.0] * len(population.individuals)

    # Use ProcessPoolExecutor for true parallelism
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(evaluate_chromosome_worker, args): i
                  for i, args in enumerate(args_list)}

        # Process results with progress bar
        with tqdm(total=len(futures), desc="Evaluating fitness") as pbar:
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    fitness, date_info = future.result()
                    fitness_scores[idx] = fitness

                    # Update progress bar with date info
                    if date_info.get('end'):
                        pbar.set_postfix({'latest_date': str(date_info['end'].date())})

                except Exception as e:
                    logger.error(f"Worker failed for chromosome {idx}: {e}")
                    fitness_scores[idx] = -999.0

                pbar.update(1)

    return fitness_scores


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
    """Main training loop with checkpointing and parallel processing"""
    logger.info("=" * 80)
    logger.info("Enhanced Genetic Algorithm Training")
    logger.info("Features: Checkpointing, Parallel Processing, Progress Tracking")
    logger.info("=" * 80)

    # Create directories
    os.makedirs('results/generations', exist_ok=True)
    os.makedirs('results/backtests', exist_ok=True)

    # Load configuration
    config, stocks_config = load_config()
    stock_list = stocks_config['all_stocks']
    n_generations = config['evolution']['generations']

    # Check for existing checkpoint
    checkpoint_path = 'checkpoints/training_checkpoint.pkl'
    checkpoint = load_checkpoint(checkpoint_path)

    if checkpoint:
        resume = input("Found existing checkpoint. Resume training? (y/n): ").lower() == 'y'
        if not resume:
            checkpoint = None
            logger.info("Starting fresh training")
    else:
        logger.info("No checkpoint found, starting fresh training")

    # Get optimal number of workers
    n_workers = get_optimal_workers()

    logger.info(f"Population size: {config['population']['size']}")
    logger.info(f"Generations: {n_generations}")
    logger.info(f"Stocks: {len(stock_list)}")
    logger.info(f"Parallel workers: {n_workers}")

    # Load data
    with DataCache('data/cache.db') as cache:
        train_data, val_data, test_data = load_training_data(cache, stock_list, config)

    # Initialize or restore evolution engine
    evolution = EvolutionEngine(config, stock_list)

    start_generation = 1

    if checkpoint:
        # Restore from checkpoint
        start_generation = checkpoint['generation'] + 1
        evolution.history = checkpoint['history']

        # Restore population
        population_data = checkpoint['population']
        evolution.population.individuals = []
        evolution.population.fitness_scores = []

        for item in population_data:
            chromosome = Chromosome(config, stock_list)
            chromosome.from_dict(item['chromosome'])
            evolution.population.individuals.append(chromosome)
            evolution.population.fitness_scores.append(item['fitness'])

        evolution.population.generation = checkpoint['generation']

        logger.info(f"Resumed from generation {checkpoint['generation']}")
    else:
        # Initialize new population
        logger.info("Initializing evolution engine...")
        evolution.initialize()

    # Run evolution with parallel processing
    logger.info(f"Starting evolution from generation {start_generation}...")
    start_time = datetime.now()

    for gen in range(start_generation, n_generations + 1):
        logger.info(f"=" * 80)
        logger.info(f"Generation {gen}/{n_generations}")
        logger.info(f"=" * 80)

        # Parallel fitness evaluation with GPU support
        fitness_scores = parallel_fitness_evaluation(
            evolution.population, train_data, config, n_workers, use_gpu=GPU_AVAILABLE
        )

        evolution.population.fitness_scores = fitness_scores

        # Get statistics
        stats = evolution.population.get_statistics()
        stats['diversity'] = evolution.population.get_diversity_score()
        evolution.history.append(stats)

        logger.info(f"Best: {stats['best_fitness']:.4f}, "
                   f"Mean: {stats['mean_fitness']:.4f}, "
                   f"Diversity: {stats['diversity']:.4f}")

        # Save checkpoint every 5 generations
        if gen % 5 == 0:
            save_checkpoint(checkpoint_path, evolution, gen, config)
            save_generation_results(evolution.population, gen)

        # Evolve (if not last generation)
        if gen < n_generations:
            from src.genetic.operators import GeneticOperators
            operators = GeneticOperators(config)

            new_pop, new_fitness = operators.evolve_generation(
                evolution.population.individuals,
                evolution.population.fitness_scores
            )
            evolution.population.replace_generation(new_pop, new_fitness)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60

    logger.info(f"Evolution complete! Duration: {duration:.1f} minutes")

    # Save final checkpoint
    save_checkpoint(checkpoint_path, evolution, n_generations, config)
    save_generation_results(evolution.population, n_generations)

    # Validation
    logger.info("Evaluating top performers on validation data...")
    top_performers = evolution.population.get_best(n=min(50, len(evolution.population.individuals)))

    validation_results = []
    fitness_evaluator = FitnessEvaluator(config)

    for i, (chromosome, train_fitness) in enumerate(tqdm(top_performers, desc="Validating")):
        try:
            backtest = BacktestEngine(
                chromosome=chromosome,
                initial_capital=config['population']['initial_capital'],
                commission=config['trading'].get('commission', 0.0),
                slippage=config['trading'].get('slippage', 0.001),
                max_positions=config['trading'].get('max_positions', 10),
                min_cash_reserve=config['trading'].get('min_cash_reserve', 0.05),
                use_gpu=GPU_AVAILABLE
            )

            val_results = backtest.run(stock_data=val_data)

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

    # Save final checkpoint with validation results
    save_checkpoint(checkpoint_path + '.final', evolution, n_generations, config, validation_results)

    # Summary
    logger.info("=" * 80)
    logger.info("Training Summary:")
    logger.info(f"  Total generations: {n_generations}")
    logger.info(f"  Training time: {duration:.1f} minutes")
    if evolution.population.fitness_scores:
        logger.info(f"  Best training fitness: {max(evolution.population.fitness_scores):.4f}")
    if validation_results:
        logger.info(f"  Top validation fitness: {max(r['val_fitness'] for r in validation_results):.4f}")
    logger.info("=" * 80)

    logger.info("Training complete! Results saved to results/")


if __name__ == '__main__':
    main()
