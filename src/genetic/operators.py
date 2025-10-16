"""Genetic operators: selection, crossover, mutation"""

import numpy as np
from typing import List, Tuple, Dict
import random
from .chromosome import Chromosome
import logging

logger = logging.getLogger(__name__)


class GeneticOperators:
    """Genetic algorithm operators"""

    def __init__(self, config: Dict):
        """
        Initialize operators

        Args:
            config: Configuration dictionary
        """
        self.config = config
        evolution_config = config.get('evolution', {})
        self.tournament_size = evolution_config.get('tournament_size', 5)
        self.crossover_prob = evolution_config.get('crossover_probability', 0.8)
        self.mutation_prob = evolution_config.get('mutation_probability', 0.15)
        self.mutation_sigma = evolution_config.get('mutation_sigma', 0.1)
        self.discrete_mutation_rate = evolution_config.get('discrete_mutation_rate', 0.05)

    def tournament_selection(self, population: List[Chromosome],
                            fitness_scores: List[float],
                            n_winners: int = 1) -> List[Chromosome]:
        """
        Tournament selection

        Args:
            population: List of chromosomes
            fitness_scores: List of fitness scores
            n_winners: Number of winners to select

        Returns:
            List of selected chromosomes
        """
        winners = []

        for _ in range(n_winners):
            # Randomly select tournament participants
            tournament_indices = random.sample(range(len(population)), self.tournament_size)
            tournament_fitness = [fitness_scores[i] for i in tournament_indices]

            # Select best from tournament
            winner_idx = tournament_indices[np.argmax(tournament_fitness)]
            winners.append(population[winner_idx].clone())

        return winners

    def two_point_crossover(self, parent1: Chromosome, parent2: Chromosome) -> Tuple[Chromosome, Chromosome]:
        """
        Two-point crossover for weight arrays

        Args:
            parent1: First parent
            parent2: Second parent

        Returns:
            Tuple of two offspring
        """
        if random.random() > self.crossover_prob:
            return parent1.clone(), parent2.clone()

        child1 = parent1.clone()
        child2 = parent2.clone()

        # Crossover for weights
        weights1 = list(parent1.genes['weights'].values())
        weights2 = list(parent2.genes['weights'].values())

        if len(weights1) >= 2:
            # Two-point crossover
            point1 = random.randint(0, len(weights1) - 1)
            point2 = random.randint(point1, len(weights1) - 1)

            # Swap middle section
            new_weights1 = (weights1[:point1] +
                           weights2[point1:point2 + 1] +
                           weights1[point2 + 1:])
            new_weights2 = (weights2[:point1] +
                           weights1[point1:point2 + 1] +
                           weights2[point2 + 1:])

            # Update children
            weight_keys = list(parent1.genes['weights'].keys())
            for i, key in enumerate(weight_keys):
                child1.genes['weights'][key] = new_weights1[i]
                child2.genes['weights'][key] = new_weights2[i]

        # Uniform crossover for discrete parameters
        if random.random() < 0.5:
            child1.genes['aggregation']['mode'] = parent2.genes['aggregation']['mode']
            child2.genes['aggregation']['mode'] = parent1.genes['aggregation']['mode']

        # Crossover for thresholds
        for key in ['buy', 'sell', 'hold_min', 'hold_max']:
            if random.random() < 0.5:
                child1.genes['thresholds'][key], child2.genes['thresholds'][key] = \
                    child2.genes['thresholds'][key], child1.genes['thresholds'][key]

        # Crossover for risk parameters
        for key in ['max_position_pct', 'stop_loss_pct', 'take_profit_pct']:
            if random.random() < 0.5:
                child1.genes['risk'][key], child2.genes['risk'][key] = \
                    child2.genes['risk'][key], child1.genes['risk'][key]

        return child1, child2

    def gaussian_mutation(self, chromosome: Chromosome) -> Chromosome:
        """
        Apply Gaussian mutation

        Args:
            chromosome: Chromosome to mutate

        Returns:
            Mutated chromosome
        """
        if random.random() > self.mutation_prob:
            return chromosome

        mutated = chromosome.clone()

        # Mutate weights
        for key in mutated.genes['weights'].keys():
            if random.random() < 0.3:  # 30% chance per weight
                mutated.mutate_weight('weights', key, self.mutation_sigma)

        # Mutate thresholds
        for key in mutated.genes['thresholds'].keys():
            if random.random() < 0.2:
                mutated.mutate_weight('thresholds', key, self.mutation_sigma)

        # Mutate risk parameters
        for key in mutated.genes['risk'].keys():
            if random.random() < 0.2:
                mutated.mutate_weight('risk', key, self.mutation_sigma)

        # Mutate discrete parameters (random reset)
        if random.random() < self.discrete_mutation_rate:
            mutated.genes['aggregation']['mode'] = random.choice([
                'independent', 'weighted_average', 'correlation_aware', 'sector_based'
            ])

        # Mutate windows
        if random.random() < 0.1:
            mutated.genes['windows']['short'] = int(np.random.randint(2, 11))
        if random.random() < 0.1:
            mutated.genes['windows']['medium'] = int(np.random.randint(10, 51))
        if random.random() < 0.1:
            mutated.genes['windows']['long'] = int(np.random.randint(50, 201))

        # Ensure window ordering
        windows = mutated.genes['windows']
        if windows['short'] >= windows['medium']:
            windows['short'] = max(2, windows['medium'] - 1)
        if windows['medium'] >= windows['long']:
            windows['medium'] = max(windows['short'] + 1, windows['long'] - 1)

        return mutated

    def elitism_selection(self, population: List[Chromosome],
                         fitness_scores: List[float],
                         elite_count: int) -> List[Chromosome]:
        """
        Select top individuals for elitism

        Args:
            population: List of chromosomes
            fitness_scores: List of fitness scores
            elite_count: Number of elite individuals

        Returns:
            List of elite chromosomes
        """
        sorted_indices = np.argsort(fitness_scores)[::-1]
        elite_indices = sorted_indices[:elite_count]

        return [population[i].clone() for i in elite_indices]

    def create_offspring(self, population: List[Chromosome],
                        fitness_scores: List[float],
                        n_offspring: int) -> List[Chromosome]:
        """
        Create offspring through selection, crossover, and mutation

        Args:
            population: Parent population
            fitness_scores: Fitness scores
            n_offspring: Number of offspring to create

        Returns:
            List of offspring chromosomes
        """
        offspring = []

        while len(offspring) < n_offspring:
            # Select parents
            parents = self.tournament_selection(population, fitness_scores, n_winners=2)

            # Crossover
            child1, child2 = self.two_point_crossover(parents[0], parents[1])

            # Mutation
            child1 = self.gaussian_mutation(child1)
            child2 = self.gaussian_mutation(child2)

            # Validate and add
            if child1.validate():
                offspring.append(child1)
            if len(offspring) < n_offspring and child2.validate():
                offspring.append(child2)

        return offspring[:n_offspring]

    def evolve_generation(self, population: List[Chromosome],
                         fitness_scores: List[float]) -> Tuple[List[Chromosome], List[float]]:
        """
        Evolve one generation

        Args:
            population: Current population
            fitness_scores: Current fitness scores

        Returns:
            Tuple of (new_population, placeholder_fitness_scores)
        """
        pop_size = len(population)
        elite_count = int(pop_size * self.config.get('evolution', {}).get('elitism_rate', 0.1))

        # Elitism: keep best individuals
        elite = self.elitism_selection(population, fitness_scores, elite_count)

        # Create offspring for remaining slots
        n_offspring = pop_size - elite_count
        offspring = self.create_offspring(population, fitness_scores, n_offspring)

        # Combine elite and offspring
        new_population = elite + offspring

        # Return new population with placeholder fitness scores (will be evaluated later)
        new_fitness = [0.0] * len(new_population)

        logger.info(f"Evolution complete: {elite_count} elite, {n_offspring} offspring")

        return new_population, new_fitness
