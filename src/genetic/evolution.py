"""Main evolution engine"""

import logging
from typing import Dict, Callable
from .population import Population
from .operators import GeneticOperators
from .fitness import FitnessEvaluator

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """Main engine for evolutionary process"""

    def __init__(self, config: Dict, stock_list: list):
        """
        Initialize evolution engine

        Args:
            config: Configuration dictionary
            stock_list: List of stock tickers
        """
        self.config = config
        self.stock_list = stock_list

        pop_size = config.get('population', {}).get('size', 1000)
        self.population = Population(pop_size, config, stock_list)
        self.operators = GeneticOperators(config)
        self.fitness_evaluator = FitnessEvaluator(config)

        self.history = []

    def initialize(self):
        """Initialize population"""
        logger.info("Initializing evolution engine")
        self.population.initialize()

    def run_evolution(self, n_generations: int,
                     fitness_function: Callable,
                     callback: Callable = None):
        """
        Run evolutionary process

        Args:
            n_generations: Number of generations to evolve
            fitness_function: Function to evaluate chromosome fitness
            callback: Optional callback after each generation
        """
        logger.info(f"Starting evolution for {n_generations} generations")

        for gen in range(n_generations):
            logger.info(f"--- Generation {gen + 1}/{n_generations} ---")

            # Evaluate fitness
            for i, individual in enumerate(self.population.individuals):
                fitness = fitness_function(individual)
                self.population.fitness_scores[i] = fitness

            # Get statistics
            stats = self.population.get_statistics()
            stats['diversity'] = self.population.get_diversity_score()
            self.history.append(stats)

            logger.info(f"Best: {stats['best_fitness']:.4f}, "
                       f"Mean: {stats['mean_fitness']:.4f}, "
                       f"Diversity: {stats['diversity']:.4f}")

            # Callback
            if callback:
                callback(self.population, stats)

            # Evolve (if not last generation)
            if gen < n_generations - 1:
                new_pop, new_fitness = self.operators.evolve_generation(
                    self.population.individuals,
                    self.population.fitness_scores
                )
                self.population.replace_generation(new_pop, new_fitness)

        logger.info("Evolution complete")

    def get_best_individual(self):
        """Get the best individual from population"""
        return self.population.get_best(n=1)[0]

    def get_top_individuals(self, n: int = 50):
        """Get top n individuals"""
        return self.population.get_best(n=n)
