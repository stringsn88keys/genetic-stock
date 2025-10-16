"""Population management for genetic algorithms"""

import numpy as np
from typing import List, Dict
import logging
from .chromosome import Chromosome

logger = logging.getLogger(__name__)


class Population:
    """Manages a population of trading algorithm chromosomes"""

    def __init__(self, size: int, config: Dict, stock_list: List[str]):
        """
        Initialize population

        Args:
            size: Population size
            config: Configuration dictionary
            stock_list: List of stock tickers
        """
        self.size = size
        self.config = config
        self.stock_list = stock_list
        self.individuals = []
        self.fitness_scores = []
        self.generation = 0

    def initialize(self):
        """Create initial random population"""
        logger.info(f"Initializing population of {self.size} individuals")

        self.individuals = [
            Chromosome(self.config, self.stock_list)
            for _ in range(self.size)
        ]

        self.fitness_scores = [0.0] * self.size
        logger.info("Population initialized")

    def evaluate_fitness(self, fitness_function):
        """
        Evaluate fitness for all individuals

        Args:
            fitness_function: Function that takes a chromosome and returns fitness score
        """
        logger.info(f"Evaluating fitness for generation {self.generation}")

        for i, individual in enumerate(self.individuals):
            self.fitness_scores[i] = fitness_function(individual)

        logger.info(f"Fitness evaluation complete. Best: {max(self.fitness_scores):.4f}, "
                   f"Mean: {np.mean(self.fitness_scores):.4f}")

    def get_best(self, n: int = 1) -> List[tuple]:
        """
        Get top n individuals

        Args:
            n: Number of individuals to return

        Returns:
            List of (chromosome, fitness) tuples
        """
        sorted_indices = np.argsort(self.fitness_scores)[::-1]
        return [(self.individuals[i], self.fitness_scores[i])
                for i in sorted_indices[:n]]

    def get_worst(self, n: int = 1) -> List[tuple]:
        """Get bottom n individuals"""
        sorted_indices = np.argsort(self.fitness_scores)
        return [(self.individuals[i], self.fitness_scores[i])
                for i in sorted_indices[:n]]

    def get_statistics(self) -> Dict:
        """Get population statistics"""
        scores = np.array(self.fitness_scores)

        return {
            'generation': self.generation,
            'size': self.size,
            'best_fitness': float(np.max(scores)),
            'worst_fitness': float(np.min(scores)),
            'mean_fitness': float(np.mean(scores)),
            'median_fitness': float(np.median(scores)),
            'std_fitness': float(np.std(scores)),
        }

    def replace_generation(self, new_individuals: List[Chromosome],
                          new_fitness_scores: List[float]):
        """Replace current population with new generation"""
        assert len(new_individuals) == self.size, "New generation size mismatch"

        self.individuals = new_individuals
        self.fitness_scores = new_fitness_scores
        self.generation += 1

        logger.info(f"Generation {self.generation} created")

    def get_diversity_score(self) -> float:
        """
        Calculate population diversity
        Higher score = more diversity

        Returns:
            Diversity score
        """
        try:
            # Compare all weights across population
            all_weights = []
            for ind in self.individuals:
                weights = ind.get_all_weights()
                all_weights.append(weights)

            # Check if we have valid weights
            if not all_weights or len(all_weights) < 2:
                return 0.0

            # Convert to numpy array (all arrays must have same shape)
            all_weights = np.array(all_weights)

            # Calculate average pairwise distance
            n = len(all_weights)
            total_distance = 0.0
            count = 0

            for i in range(n):
                for j in range(i + 1, n):
                    try:
                        distance = np.linalg.norm(all_weights[i] - all_weights[j])
                        total_distance += distance
                        count += 1
                    except Exception:
                        # Skip if arrays incompatible
                        continue

            avg_distance = total_distance / count if count > 0 else 0.0
            return float(avg_distance)

        except Exception as e:
            logger.warning(f"Error calculating diversity: {e}")
            return 0.0

    def to_dict_list(self) -> List[Dict]:
        """Export population as list of dictionaries"""
        return [
            {
                'chromosome': ind.to_dict(),
                'fitness': self.fitness_scores[i]
            }
            for i, ind in enumerate(self.individuals)
        ]

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        return self.individuals[index]

    def __repr__(self):
        return f"Population(size={self.size}, generation={self.generation})"
