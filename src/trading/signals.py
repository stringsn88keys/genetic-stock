"""Signal generation from normalized data"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from ..genetic.chromosome import Chromosome

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generate trading signals from normalized stock data using chromosome weights"""

    def __init__(self, chromosome: Chromosome):
        """
        Initialize signal generator with a chromosome

        Args:
            chromosome: Chromosome containing weights and thresholds
        """
        self.chromosome = chromosome
        self.weights = chromosome.genes['weights']
        self.thresholds = chromosome.genes['thresholds']
        self.windows = chromosome.genes['windows']

    def calculate_signal_score(self, features: pd.Series) -> float:
        """
        Calculate signal score from feature vector using chromosome weights

        Args:
            features: Series containing normalized features for a single data point

        Returns:
            Signal score (typically between -1 and 1)
        """
        score = 0.0

        # Weight basic normalized prices
        if 'normalized_close' in features:
            score += self.weights.get('close', 0.0) * (features['normalized_close'] - 1.0)

        if 'normalized_high' in features:
            score += self.weights.get('high', 0.0) * (features['normalized_high'] - 1.0)

        if 'normalized_low' in features:
            score += self.weights.get('low', 0.0) * (features['normalized_low'] - 1.0)

        # Weight volume
        if 'normalized_volume' in features:
            score += self.weights.get('volume', 0.0) * (features['normalized_volume'] - 1.0)

        # Weight momentum indicators
        if 'momentum_5d' in features:
            score += self.weights.get('momentum_5d', 0.0) * features['momentum_5d']

        if 'momentum_20d' in features:
            score += self.weights.get('momentum_20d', 0.0) * features['momentum_20d']

        # Weight volume trend
        if 'volume_trend_5d' in features:
            score += self.weights.get('volume_trend_5d', 0.0) * features['volume_trend_5d']

        # Clip score to reasonable range
        score = np.clip(score, -2.0, 2.0)

        return float(score)

    def generate_signal(self, features: pd.Series) -> str:
        """
        Generate trading signal (buy/sell/hold) from features

        Args:
            features: Series containing normalized features

        Returns:
            Signal string: 'buy', 'sell', or 'hold'
        """
        score = self.calculate_signal_score(features)

        # Apply thresholds
        if score >= self.thresholds['buy']:
            return 'buy'
        elif score <= self.thresholds['sell']:
            return 'sell'
        elif self.thresholds['hold_min'] <= score <= self.thresholds['hold_max']:
            return 'hold'
        else:
            # Between thresholds but not in hold zone
            return 'hold'

    def generate_signals_for_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals for entire DataFrame

        Args:
            df: DataFrame with normalized features

        Returns:
            DataFrame with added 'signal' and 'signal_score' columns
        """
        df = df.copy()

        # Calculate signal scores
        df['signal_score'] = df.apply(
            lambda row: self.calculate_signal_score(row),
            axis=1
        )

        # Generate signals
        df['signal'] = df['signal_score'].apply(
            lambda score: (
                'buy' if score >= self.thresholds['buy']
                else 'sell' if score <= self.thresholds['sell']
                else 'hold'
            )
        )

        logger.debug(f"Generated signals for {len(df)} data points")
        return df

    def generate_multi_stock_signals(self,
                                    stock_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Generate signals for multiple stocks

        Args:
            stock_data: Dictionary mapping ticker to DataFrame with normalized features

        Returns:
            Dictionary mapping ticker to DataFrame with signals
        """
        results = {}

        for ticker, df in stock_data.items():
            try:
                results[ticker] = self.generate_signals_for_dataframe(df)
                logger.debug(f"Generated signals for {ticker}")
            except Exception as e:
                logger.error(f"Error generating signals for {ticker}: {e}")
                results[ticker] = df.copy()
                results[ticker]['signal'] = 'hold'
                results[ticker]['signal_score'] = 0.0

        return results

    def aggregate_signals(self,
                         stock_signals: Dict[str, pd.DataFrame],
                         date: pd.Timestamp) -> Dict[str, str]:
        """
        Aggregate signals for multiple stocks at a specific date

        Args:
            stock_signals: Dictionary mapping ticker to DataFrame with signals
            date: Date to get signals for

        Returns:
            Dictionary mapping ticker to signal ('buy', 'sell', 'hold')
        """
        aggregation_mode = self.chromosome.genes['aggregation']['mode']
        stock_weights = self.chromosome.genes['aggregation']['stock_weights']

        signals = {}

        for ticker, df in stock_signals.items():
            # Get signal for this date
            date_mask = df.index == date
            if date_mask.any():
                signals[ticker] = df.loc[date_mask, 'signal'].iloc[0]
            else:
                signals[ticker] = 'hold'

        # Apply aggregation strategy
        if aggregation_mode == 'independent':
            # Each stock trades independently
            return signals

        elif aggregation_mode == 'weighted_average':
            # Weight signals by stock weights
            # For now, just return independent signals
            # In future, could implement weighted voting
            return signals

        elif aggregation_mode == 'correlation_aware':
            # Consider correlations between stocks
            # For now, return independent signals
            return signals

        elif aggregation_mode == 'sector_based':
            # Group by sector (requires sector data)
            # For now, return independent signals
            return signals

        else:
            return signals

    def get_signal_for_date(self, df: pd.DataFrame, date: pd.Timestamp) -> Optional[str]:
        """
        Get signal for a specific date

        Args:
            df: DataFrame with signals
            date: Target date

        Returns:
            Signal string or None if date not found
        """
        date_mask = df.index == date
        if date_mask.any():
            return df.loc[date_mask, 'signal'].iloc[0]
        return None

    def get_signal_score_for_date(self, df: pd.DataFrame, date: pd.Timestamp) -> Optional[float]:
        """
        Get signal score for a specific date

        Args:
            df: DataFrame with signal scores
            date: Target date

        Returns:
            Signal score or None if date not found
        """
        date_mask = df.index == date
        if date_mask.any():
            return df.loc[date_mask, 'signal_score'].iloc[0]
        return None

    def validate_features(self, features: pd.Series) -> bool:
        """
        Validate that required features are present

        Args:
            features: Feature series to validate

        Returns:
            True if valid, False otherwise
        """
        required_features = [
            'normalized_close',
            'normalized_high',
            'normalized_low',
            'normalized_volume'
        ]

        for feature in required_features:
            if feature not in features or pd.isna(features[feature]):
                return False

        return True

    def __repr__(self) -> str:
        return f"SignalGenerator(weights={len(self.weights)}, thresholds={self.thresholds})"
