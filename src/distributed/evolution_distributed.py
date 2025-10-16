"""Distributed evolution engine wrapper"""

import logging
import uuid
from typing import Dict, List, Callable
import time

from ..genetic.chromosome import Chromosome
from .server import DistributedServer
from .protocol import WorkUnit, WorkResult

logger = logging.getLogger(__name__)


class DistributedEvolutionEngine:
    """Wrapper for evolution engine with distributed fitness evaluation"""

    def __init__(self, config: Dict, stock_list: list,
                 server_host: str = '0.0.0.0', server_port: int = 9999):
        """
        Initialize distributed evolution engine

        Args:
            config: Configuration dictionary
            stock_list: List of stock tickers
            server_host: Host to bind server to
            server_port: Port for server
        """
        self.config = config
        self.stock_list = stock_list

        # Create server
        self.server = DistributedServer(server_host, server_port)

        # Training data info (to be set)
        self.train_data_info = None

        # Results tracking
        self.fitness_results = {}
        self.current_generation = 0

    def start_server(self):
        """Start the distribution server"""
        self.server.start()
        logger.info("Distributed server started")

    def stop_server(self):
        """Stop the distribution server"""
        self.server.stop()
        logger.info("Distributed server stopped")

    def set_training_data_info(self, train_data: Dict):
        """
        Set training data information for workers

        Args:
            train_data: Dictionary of training dataframes
        """
        # Extract date ranges from the training data
        start_date = None
        end_date = None

        for ticker, df in train_data.items():
            if not df.empty:
                ticker_start = df.index.min()
                ticker_end = df.index.max()

                if start_date is None or ticker_start < start_date:
                    start_date = ticker_start
                if end_date is None or ticker_end > end_date:
                    end_date = ticker_end

        # Send metadata about the data, workers will load from cache or fetch
        self.train_data_info = {
            'tickers': list(train_data.keys()),
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
        }

    def evaluate_population_distributed(self, population: List[Chromosome],
                                       generation: int) -> List[float]:
        """
        Evaluate fitness for entire population using distributed workers

        Args:
            population: List of chromosomes to evaluate
            generation: Current generation number

        Returns:
            List of fitness scores in same order as population
        """
        logger.info(f"Distributing {len(population)} fitness evaluations "
                   f"for generation {generation}")

        self.current_generation = generation
        self.fitness_results = {}

        # Create work units
        work_units = []
        chromosome_map = {}  # work_id -> index in population

        for idx, chromosome in enumerate(population):
            work_id = str(uuid.uuid4())
            chromosome_map[work_id] = idx

            work_unit = WorkUnit(
                work_id=work_id,
                work_type='fitness_eval',
                chromosome_data=chromosome.to_dict(),
                train_data_info=self.train_data_info,
                config=self.config,
                generation=generation
            )
            work_units.append(work_unit)

        # Submit all work
        self.server.submit_work_batch(work_units)

        # Wait for all results with progress logging
        start_time = time.time()
        last_log_time = start_time
        completed_count = 0

        while completed_count < len(population):
            results = self.server.get_results()

            for result in results:
                if result.work_id in chromosome_map:
                    idx = chromosome_map[result.work_id]
                    if result.success:
                        self.fitness_results[idx] = result.fitness_score
                    else:
                        logger.warning(f"Work {result.work_id} failed: {result.error}")
                        self.fitness_results[idx] = 0.0  # Failed evaluation gets 0

                    completed_count += 1

            # Log progress every 5 seconds
            current_time = time.time()
            if current_time - last_log_time >= 5.0:
                elapsed = current_time - start_time
                rate = completed_count / elapsed if elapsed > 0 else 0
                remaining = len(population) - completed_count
                eta = remaining / rate if rate > 0 else 0

                logger.info(f"Progress: {completed_count}/{len(population)} "
                           f"({100*completed_count/len(population):.1f}%) "
                           f"- Rate: {rate:.1f}/s - ETA: {eta:.0f}s")
                last_log_time = current_time

            # Small sleep to avoid busy waiting
            time.sleep(0.1)

        total_time = time.time() - start_time
        logger.info(f"Completed {len(population)} evaluations in {total_time:.1f}s "
                   f"({len(population)/total_time:.1f} evals/s)")

        # Return fitness scores in original order
        fitness_scores = [self.fitness_results.get(i, 0.0) for i in range(len(population))]

        return fitness_scores

    def get_server_statistics(self) -> Dict:
        """Get server statistics"""
        return self.server.get_statistics()


# Helper function to create work units from chromosomes
def create_fitness_work_units(chromosomes: List[Chromosome],
                             train_data_info: Dict,
                             config: Dict,
                             generation: int) -> List[WorkUnit]:
    """
    Create fitness evaluation work units from chromosomes

    Args:
        chromosomes: List of chromosomes to evaluate
        train_data_info: Training data information
        config: Configuration dictionary
        generation: Current generation number

    Returns:
        List of work units
    """
    work_units = []

    for chromosome in chromosomes:
        work_id = str(uuid.uuid4())

        work_unit = WorkUnit(
            work_id=work_id,
            work_type='fitness_eval',
            chromosome_data=chromosome.to_dict(),
            train_data_info=train_data_info,
            config=config,
            generation=generation
        )
        work_units.append(work_unit)

    return work_units
