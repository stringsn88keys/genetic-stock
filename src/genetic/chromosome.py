"""Chromosome representation for trading algorithms"""

import numpy as np
import json
from typing import Dict, List
import copy


class Chromosome:
    """Represents a trading algorithm's parameters"""

    def __init__(self, config: Dict = None, stock_list: List[str] = None):
        """
        Initialize chromosome

        Args:
            config: Configuration dictionary with parameter ranges
            stock_list: List of stock tickers
        """
        self.config = config or {}
        self.stock_list = stock_list or []
        self.genes = self._initialize_genes()

    def _initialize_genes(self) -> Dict:
        """Initialize random genes within configured ranges"""

        # Get configuration ranges
        ranges = self.config.get('chromosome_ranges', {})
        weight_min = ranges.get('weights', {}).get('min', -1.0)
        weight_max = ranges.get('weights', {}).get('max', 1.0)

        genes = {
            'weights': {
                'close': np.random.uniform(weight_min, weight_max),
                'high': np.random.uniform(weight_min, weight_max),
                'low': np.random.uniform(weight_min, weight_max),
                'volume': np.random.uniform(weight_min, weight_max),
                'momentum_5d': np.random.uniform(weight_min, weight_max),
                'momentum_20d': np.random.uniform(weight_min, weight_max),
                'volume_trend_5d': np.random.uniform(weight_min, weight_max),
            },
            'aggregation': {
                'mode': np.random.choice(['independent', 'weighted_average',
                                        'correlation_aware', 'sector_based']),
                'stock_weights': {ticker: np.random.uniform(0, 1)
                                 for ticker in self.stock_list}
            },
            'thresholds': {
                'buy': np.random.uniform(0.3, 0.9),
                'sell': np.random.uniform(-0.9, -0.3),
                'hold_min': np.random.uniform(-0.3, 0),
                'hold_max': np.random.uniform(0, 0.5),
            },
            'risk': {
                'max_position_pct': np.random.uniform(0.1, 0.35),
                'stop_loss_pct': np.random.uniform(-0.15, -0.05),
                'take_profit_pct': np.random.uniform(0.10, 0.25),
            },
            'windows': {
                'short': int(np.random.randint(2, 11)),
                'medium': int(np.random.randint(10, 51)),
                'long': int(np.random.randint(50, 201)),
            }
        }

        # Normalize stock weights to sum to 1
        if genes['aggregation']['stock_weights']:
            total = sum(genes['aggregation']['stock_weights'].values())
            if total > 0:
                genes['aggregation']['stock_weights'] = {
                    k: v/total for k, v in genes['aggregation']['stock_weights'].items()
                }

        return genes

    def get_gene(self, category: str, key: str):
        """Get a specific gene value"""
        return self.genes.get(category, {}).get(key)

    def set_gene(self, category: str, key: str, value):
        """Set a specific gene value"""
        if category not in self.genes:
            self.genes[category] = {}
        self.genes[category][key] = value

    def to_dict(self) -> Dict:
        """Convert chromosome to dictionary"""
        return copy.deepcopy(self.genes)

    def to_json(self) -> str:
        """Convert chromosome to JSON string"""
        return json.dumps(self.genes, indent=2)

    def from_dict(self, genes: Dict):
        """Load chromosome from dictionary"""
        self.genes = copy.deepcopy(genes)

    def from_json(self, json_str: str):
        """Load chromosome from JSON string"""
        self.genes = json.loads(json_str)

    def clone(self) -> 'Chromosome':
        """Create a deep copy of this chromosome"""
        new_chromosome = Chromosome(self.config, self.stock_list)
        new_chromosome.genes = copy.deepcopy(self.genes)
        return new_chromosome

    def get_all_weights(self) -> np.ndarray:
        """Get all weight values as a numpy array"""
        weights = list(self.genes['weights'].values())
        return np.array(weights)

    def set_all_weights(self, weight_array: np.ndarray):
        """Set all weights from a numpy array"""
        weight_keys = list(self.genes['weights'].keys())
        for i, key in enumerate(weight_keys):
            if i < len(weight_array):
                self.genes['weights'][key] = float(weight_array[i])

    def mutate_weight(self, category: str, key: str, sigma: float = 0.1):
        """Apply Gaussian mutation to a specific weight"""
        current_value = self.genes[category][key]

        if isinstance(current_value, (int, float)):
            mutation = np.random.normal(0, sigma)
            new_value = current_value + mutation

            # Clip to valid range based on category
            if category == 'weights':
                new_value = np.clip(new_value, -1.0, 1.0)
            elif category == 'thresholds':
                if key == 'buy':
                    new_value = np.clip(new_value, 0.3, 0.9)
                elif key == 'sell':
                    new_value = np.clip(new_value, -0.9, -0.3)
            elif category == 'risk':
                if key == 'max_position_pct':
                    new_value = np.clip(new_value, 0.05, 0.5)
                elif key == 'stop_loss_pct':
                    new_value = np.clip(new_value, -0.2, -0.02)
                elif key == 'take_profit_pct':
                    new_value = np.clip(new_value, 0.05, 0.5)

            self.genes[category][key] = float(new_value)

    def validate(self) -> bool:
        """Validate chromosome structure and values"""
        try:
            # Check required categories
            required = ['weights', 'aggregation', 'thresholds', 'risk', 'windows']
            for cat in required:
                if cat not in self.genes:
                    return False

            # Check threshold logic
            if self.genes['thresholds']['buy'] <= self.genes['thresholds']['hold_max']:
                return False
            if self.genes['thresholds']['sell'] >= self.genes['thresholds']['hold_min']:
                return False

            # Check window ordering
            windows = self.genes['windows']
            if not (windows['short'] < windows['medium'] < windows['long']):
                return False

            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"Chromosome(weights={len(self.genes['weights'])}, stocks={len(self.stock_list)})"

    def __str__(self) -> str:
        return self.to_json()
