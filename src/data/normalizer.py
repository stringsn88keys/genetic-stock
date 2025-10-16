"""Data normalization for stock prices"""

import pandas as pd
import numpy as np
from typing import Optional
import logging
from ..utils.gpu_utils import GPUAccelerator

logger = logging.getLogger(__name__)


class DataNormalizer:
    """Normalize stock price data for genetic algorithm input"""

    def __init__(self, volume_ma_window: int = 30, use_gpu: bool = True):
        """
        Initialize normalizer

        Args:
            volume_ma_window: Window for volume moving average
            use_gpu: Whether to use GPU acceleration if available
        """
        self.volume_ma_window = volume_ma_window
        self.gpu = GPUAccelerator(use_gpu=use_gpu)

    def normalize_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize OHLC prices relative to opening price

        Args:
            df: DataFrame with columns: open, high, low, close

        Returns:
            DataFrame with additional normalized columns
        """
        df = df.copy()

        # Normalize to open price = 1.0
        df['normalized_open'] = 1.0
        df['normalized_high'] = df['high'] / df['open']
        df['normalized_low'] = df['low'] / df['open']
        df['normalized_close'] = df['close'] / df['open']

        logger.debug(f"Normalized prices for {len(df)} rows")
        return df

    def normalize_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize volume relative to moving average

        Args:
            df: DataFrame with volume column

        Returns:
            DataFrame with normalized volume column
        """
        df = df.copy()

        # Calculate volume moving average
        df['volume_ma30'] = df['volume'].rolling(
            window=self.volume_ma_window,
            min_periods=1
        ).mean()

        # Normalize volume
        df['normalized_volume'] = df['volume'] / df['volume_ma30']

        # Handle edge cases
        df['normalized_volume'] = df['normalized_volume'].replace([np.inf, -np.inf], np.nan)
        df['normalized_volume'] = df['normalized_volume'].fillna(1.0)

        logger.debug(f"Normalized volume for {len(df)} rows")
        return df

    def normalize_full(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply full normalization (prices and volume)

        Args:
            df: DataFrame with columns: date, open, high, low, close, volume

        Returns:
            DataFrame with all normalized columns added
        """
        df = df.copy()

        # Normalize prices
        df = self.normalize_prices(df)

        # Normalize volume
        df = self.normalize_volume(df)

        logger.info(f"Full normalization complete for {len(df)} rows")
        return df

    def calculate_technical_features(self, df: pd.DataFrame,
                                     short_window: int = 5,
                                     medium_window: int = 20,
                                     long_window: int = 50) -> pd.DataFrame:
        """
        Calculate technical indicators from normalized data (GPU-accelerated)

        Args:
            df: DataFrame with normalized price columns
            short_window: Short-term lookback period
            medium_window: Medium-term lookback period
            long_window: Long-term lookback period

        Returns:
            DataFrame with additional technical feature columns
        """
        df = df.copy()

        # Momentum indicators (rate of change)
        for window in [short_window, medium_window, long_window]:
            df[f'momentum_{window}d'] = df['normalized_close'].pct_change(window)

        # Volume trend
        for window in [short_window, medium_window]:
            df[f'volume_trend_{window}d'] = df['normalized_volume'].pct_change(window)

        # Moving averages of normalized close (GPU-accelerated for speed)
        close_values = df['normalized_close'].values

        # Calculate moving averages using GPU if series is large enough
        if len(close_values) > 100 and self.gpu.use_gpu:
            try:
                sma_short = self.gpu.compute_moving_average(close_values, short_window)
                sma_medium = self.gpu.compute_moving_average(close_values, medium_window)
                sma_long = self.gpu.compute_moving_average(close_values, long_window)

                # Pad with NaN to match original length
                df[f'sma_{short_window}'] = np.concatenate([
                    np.full(short_window - 1, np.nan), sma_short
                ])
                df[f'sma_{medium_window}'] = np.concatenate([
                    np.full(medium_window - 1, np.nan), sma_medium
                ])
                df[f'sma_{long_window}'] = np.concatenate([
                    np.full(long_window - 1, np.nan), sma_long
                ])
            except Exception as e:
                logger.debug(f"GPU MA calculation failed, falling back to CPU: {e}")
                # Fallback to pandas rolling
                df[f'sma_{short_window}'] = df['normalized_close'].rolling(short_window).mean()
                df[f'sma_{medium_window}'] = df['normalized_close'].rolling(medium_window).mean()
                df[f'sma_{long_window}'] = df['normalized_close'].rolling(long_window).mean()
        else:
            # Use pandas rolling for small datasets or when GPU unavailable
            df[f'sma_{short_window}'] = df['normalized_close'].rolling(short_window).mean()
            df[f'sma_{medium_window}'] = df['normalized_close'].rolling(medium_window).mean()
            df[f'sma_{long_window}'] = df['normalized_close'].rolling(long_window).mean()

        # Price relative to moving averages
        df[f'price_to_sma_{short_window}'] = df['normalized_close'] / df[f'sma_{short_window}']
        df[f'price_to_sma_{medium_window}'] = df['normalized_close'] / df[f'sma_{medium_window}']

        # Volatility (standard deviation of returns)
        df[f'volatility_{short_window}'] = df['normalized_close'].pct_change().rolling(short_window).std()

        # High-Low range
        df['hl_range'] = df['normalized_high'] - df['normalized_low']

        # Fill NaN values with 0
        df = df.fillna(0)

        logger.debug(f"Calculated technical features for {len(df)} rows")
        return df

    def get_features_for_date(self, df: pd.DataFrame, date: pd.Timestamp,
                             lookback_window: int = 50) -> pd.Series:
        """
        Get feature vector for a specific date

        Args:
            df: DataFrame with all features
            date: Target date
            lookback_window: Number of days to look back

        Returns:
            Series with features for the date
        """
        # Get data up to and including the target date
        df_filtered = df[df.index <= date].tail(lookback_window)

        if df_filtered.empty:
            logger.warning(f"No data available for date {date}")
            return pd.Series()

        # Return the most recent row
        return df_filtered.iloc[-1]

    def prepare_training_data(self, df: pd.DataFrame,
                             feature_columns: Optional[list] = None) -> pd.DataFrame:
        """
        Prepare normalized data for training

        Args:
            df: Raw price DataFrame
            feature_columns: List of feature columns to include (None = all)

        Returns:
            DataFrame ready for algorithm training
        """
        # Apply full normalization
        df = self.normalize_full(df)

        # Calculate technical features
        df = self.calculate_technical_features(df)

        # Select feature columns
        if feature_columns:
            available_cols = [col for col in feature_columns if col in df.columns]
            df = df[available_cols]

        # Remove rows with NaN (from rolling calculations)
        initial_rows = len(df)
        df = df.dropna()
        removed_rows = initial_rows - len(df)

        if removed_rows > 0:
            logger.info(f"Removed {removed_rows} rows with NaN values")

        logger.info(f"Prepared training data: {len(df)} rows, {len(df.columns)} features")
        return df

    @staticmethod
    def split_train_val_test(df: pd.DataFrame,
                             train_ratio: float = 0.7,
                             val_ratio: float = 0.2,
                             test_ratio: float = 0.1) -> tuple:
        """
        Split data into train/validation/test sets chronologically

        Args:
            df: DataFrame to split
            train_ratio: Fraction for training
            val_ratio: Fraction for validation
            test_ratio: Fraction for testing

        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 0.001, \
            "Ratios must sum to 1.0"

        n = len(df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_df = df.iloc[:train_end].copy()
        val_df = df.iloc[train_end:val_end].copy()
        test_df = df.iloc[val_end:].copy()

        logger.info(f"Split data: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")

        return train_df, val_df, test_df
