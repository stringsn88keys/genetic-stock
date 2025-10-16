"""Distributed training leader script - runs server and participates in training"""

import sys
import os
import logging
import yaml
import json
import threading
import time
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.cache import DataCache
from src.data.normalizer import DataNormalizer
from src.genetic.chromosome import Chromosome
from src.genetic.population import Population
from src.genetic.operators import GeneticOperators
from src.distributed.evolution_distributed import DistributedEvolutionEngine
from src.distributed.client import DistributedClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/distributed_training_leader.log'),
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


def start_local_client(server_host, server_port, config, train_data):
    """Start a local client worker"""
    logger.info("Starting local client worker...")

    client = DistributedClient(
        server_host=server_host if server_host != '0.0.0.0' else 'localhost',
        server_port=server_port,
        use_gpu=True
    )

    # Set training data for local execution
    client.set_training_data(config, train_data)

    # Give server time to start
    time.sleep(2)

    # Connect and start
    if client.connect():
        logger.info("Local client connected successfully")
        client.start()
    else:
        logger.error("Failed to connect local client")


def main():
    parser = argparse.ArgumentParser(description='Distributed Genetic Training Leader')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host address to bind server (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=9999,
                       help='Port for server (default: 9999)')
    parser.add_argument('--generations', type=int, default=None,
                       help='Number of generations (default: from config)')
    parser.add_argument('--no-local-worker', action='store_true',
                       help='Do not start local worker (server only)')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("DISTRIBUTED GENETIC TRAINING - LEADER NODE")
    logger.info("=" * 80)

    # Load configuration
    config, stocks = load_config()
    # Use all_stocks by default, or fall back to sp500 if not available
    stock_list = stocks.get('all_stocks', stocks.get('sp500', []))[:10]

    n_generations = args.generations or config['population'].get('generations', 50)
    pop_size = config['population']['size']

    logger.info(f"Configuration:")
    logger.info(f"  - Stocks: {len(stock_list)}")
    logger.info(f"  - Population: {pop_size}")
    logger.info(f"  - Generations: {n_generations}")
    logger.info(f"  - Server: {args.host}:{args.port}")

    # Load training data
    cache = DataCache()
    cache.connect()
    train_data, val_data, test_data = load_training_data(cache, stock_list, config)

    # Create distributed evolution engine
    logger.info("Initializing distributed evolution engine...")
    dist_engine = DistributedEvolutionEngine(
        config=config,
        stock_list=stock_list,
        server_host=args.host,
        server_port=args.port
    )

    # Start server
    dist_engine.start_server()
    dist_engine.set_training_data_info(train_data)

    # Start local client in separate thread (unless disabled)
    local_client_thread = None
    if not args.no_local_worker:
        local_client_thread = threading.Thread(
            target=start_local_client,
            args=(args.host, args.port, config, train_data),
            daemon=True
        )
        local_client_thread.start()
        logger.info("Local client worker started in background")
    else:
        logger.info("Local client worker disabled - waiting for remote workers only")

    # Give workers time to connect
    logger.info("Waiting for workers to connect...")
    time.sleep(5)

    # Initialize population
    logger.info("Initializing population...")
    population = Population(pop_size, config, stock_list)
    population.initialize()

    operators = GeneticOperators(config)

    # Training loop
    logger.info(f"\nStarting training for {n_generations} generations\n")
    history = []

    try:
        for gen in range(n_generations):
            logger.info(f"\n{'='*80}")
            logger.info(f"GENERATION {gen + 1}/{n_generations}")
            logger.info(f"{'='*80}\n")

            gen_start_time = time.time()

            # Evaluate fitness using distributed workers
            fitness_scores = dist_engine.evaluate_population_distributed(
                population.individuals,
                generation=gen
            )

            # Update population fitness
            population.fitness_scores = fitness_scores

            # Get statistics
            stats = population.get_statistics()
            stats['diversity'] = population.get_diversity_score()
            stats['server_stats'] = dist_engine.get_server_statistics()

            gen_time = time.time() - gen_start_time
            stats['generation_time'] = gen_time

            history.append(stats)

            # Log results
            logger.info(f"\nGeneration {gen + 1} Results:")
            logger.info(f"  Best Fitness:    {stats['best_fitness']:.6f}")
            logger.info(f"  Mean Fitness:    {stats['mean_fitness']:.6f}")
            logger.info(f"  Median Fitness:  {stats['median_fitness']:.6f}")
            logger.info(f"  Std Dev:         {stats['std_fitness']:.6f}")
            logger.info(f"  Diversity:       {stats['diversity']:.6f}")
            logger.info(f"  Generation Time: {gen_time:.1f}s")
            logger.info(f"\nServer Statistics:")
            logger.info(f"  Active Workers:  {stats['server_stats']['active_workers']}")
            logger.info(f"  Total Workers:   {stats['server_stats']['total_workers']}")
            logger.info(f"  Completed Work:  {stats['server_stats']['work_units_completed']}")
            logger.info(f"  Failed Work:     {stats['server_stats']['work_units_failed']}")

            # Save checkpoint
            if (gen + 1) % 10 == 0:
                checkpoint_file = f"checkpoints/distributed_gen_{gen + 1}.pkl"
                os.makedirs('checkpoints', exist_ok=True)

                import pickle
                checkpoint_data = {
                    'generation': gen + 1,
                    'population': [ind.to_dict() for ind in population.individuals],
                    'fitness_scores': population.fitness_scores,
                    'history': history,
                    'config': config
                }
                with open(checkpoint_file, 'wb') as f:
                    pickle.dump(checkpoint_data, f)
                logger.info(f"Checkpoint saved: {checkpoint_file}")

            # Evolve (if not last generation)
            if gen < n_generations - 1:
                logger.info("\nEvolving population...")
                new_pop, new_fitness = operators.evolve_generation(
                    population.individuals,
                    population.fitness_scores
                )
                population.replace_generation(new_pop, new_fitness)

        # Training complete
        logger.info(f"\n{'='*80}")
        logger.info("TRAINING COMPLETE")
        logger.info(f"{'='*80}\n")

        # Get best individual
        best_individual, best_fitness = population.get_best(n=1)[0]

        logger.info(f"Best Individual Fitness: {best_fitness:.6f}")
        logger.info(f"\nBest Individual Parameters:")
        logger.info(json.dumps(best_individual.to_dict(), indent=2))

        # Save results
        results_dir = 'results/distributed'
        os.makedirs(results_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save best individual
        with open(f'{results_dir}/best_individual_{timestamp}.json', 'w') as f:
            json.dump(best_individual.to_dict(), f, indent=2)

        # Save history
        with open(f'{results_dir}/training_history_{timestamp}.json', 'w') as f:
            json.dump(history, f, indent=2)

        # Save final population
        import pickle
        with open(f'{results_dir}/final_population_{timestamp}.pkl', 'wb') as f:
            pickle.dump({
                'individuals': [ind.to_dict() for ind in population.individuals],
                'fitness_scores': population.fitness_scores
            }, f)

        logger.info(f"\nResults saved to {results_dir}/")

    except KeyboardInterrupt:
        logger.info("\nTraining interrupted by user")

    except Exception as e:
        logger.error(f"\nError during training: {e}", exc_info=True)

    finally:
        # Stop server
        logger.info("\nShutting down distributed server...")
        dist_engine.stop_server()
        logger.info("Server stopped")

        # Disconnect cache
        cache.disconnect()
        logger.info("Cache disconnected")


if __name__ == '__main__':
    # Create logs directory
    os.makedirs('logs', exist_ok=True)

    main()
