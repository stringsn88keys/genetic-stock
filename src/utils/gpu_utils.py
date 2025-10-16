"""GPU acceleration utilities for numerical computations"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

# Try to import CuPy for GPU support
try:
    import cupy as cp
    GPU_AVAILABLE = True
    logger.info("GPU (CUDA) support enabled via CuPy")
except ImportError:
    cp = None
    GPU_AVAILABLE = False
    logger.info("GPU support not available - using CPU (NumPy)")


class GPUAccelerator:
    """Utility class for GPU-accelerated computations"""

    def __init__(self, use_gpu=True):
        """
        Initialize GPU accelerator

        Args:
            use_gpu: Whether to use GPU if available
        """
        self.use_gpu = use_gpu and GPU_AVAILABLE
        self.xp = cp if self.use_gpu else np

        if self.use_gpu:
            try:
                # Test GPU is actually working
                test = cp.array([1, 2, 3])
                _ = cp.asnumpy(test)
                logger.info(f"GPU initialized: {cp.cuda.Device()}")
            except Exception as e:
                logger.warning(f"GPU test failed, falling back to CPU: {e}")
                self.use_gpu = False
                self.xp = np

    def to_device(self, array):
        """
        Move array to GPU if available

        Args:
            array: NumPy array

        Returns:
            CuPy array if GPU enabled, otherwise NumPy array
        """
        if self.use_gpu and isinstance(array, np.ndarray):
            return cp.asarray(array)
        return array

    def to_cpu(self, array):
        """
        Move array to CPU

        Args:
            array: NumPy or CuPy array

        Returns:
            NumPy array
        """
        if self.use_gpu and isinstance(array, cp.ndarray):
            return cp.asnumpy(array)
        return array

    def compute_returns(self, prices):
        """
        Compute returns array (GPU-accelerated if available)

        Args:
            prices: Array of prices

        Returns:
            Array of returns
        """
        prices_gpu = self.to_device(prices)

        # Compute percentage returns
        returns = self.xp.diff(prices_gpu) / prices_gpu[:-1]

        return self.to_cpu(returns)

    def compute_sharpe_ratio(self, returns, risk_free_rate=0.02, periods_per_year=252):
        """
        Compute Sharpe ratio (GPU-accelerated)

        Args:
            returns: Array of returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year

        Returns:
            Sharpe ratio
        """
        returns_gpu = self.to_device(returns)

        mean_return = self.xp.mean(returns_gpu)
        std_return = self.xp.std(returns_gpu)

        if std_return == 0:
            return 0.0

        sharpe = (mean_return - risk_free_rate / periods_per_year) / std_return
        sharpe_annual = sharpe * self.xp.sqrt(periods_per_year)

        return float(self.to_cpu(sharpe_annual))

    def compute_max_drawdown(self, values):
        """
        Compute maximum drawdown (GPU-accelerated)

        Args:
            values: Array of portfolio values

        Returns:
            Maximum drawdown (negative value)
        """
        values_gpu = self.to_device(values)

        # Compute running maximum using cummax (compatible with CuPy)
        # For CuPy, we need to use a loop-based approach
        if self.use_gpu:
            # Use a custom kernel for running max
            n = len(values_gpu)
            running_max = self.xp.empty_like(values_gpu)
            running_max[0] = values_gpu[0]

            for i in range(1, n):
                running_max[i] = self.xp.maximum(running_max[i-1], values_gpu[i])
        else:
            # NumPy has accumulate
            running_max = self.xp.maximum.accumulate(values_gpu)

        # Compute drawdown
        drawdown = (values_gpu - running_max) / running_max

        max_dd = float(self.xp.min(drawdown))

        return max_dd

    def compute_moving_average(self, values, window):
        """
        Compute moving average (GPU-accelerated)

        Args:
            values: Array of values
            window: Window size

        Returns:
            Moving average array
        """
        values_gpu = self.to_device(values)

        # Use convolution for efficient MA calculation
        kernel = self.xp.ones(window) / window
        ma = self.xp.convolve(values_gpu, kernel, mode='valid')

        return self.to_cpu(ma)

    def batch_normalize(self, arrays):
        """
        Normalize multiple arrays in batch (GPU-accelerated)

        Args:
            arrays: List of arrays to normalize

        Returns:
            List of normalized arrays
        """
        if not arrays:
            return []

        # Stack arrays for batch processing
        stacked = self.xp.stack([self.to_device(arr) for arr in arrays])

        # Normalize each array
        means = self.xp.mean(stacked, axis=1, keepdims=True)
        stds = self.xp.std(stacked, axis=1, keepdims=True)

        # Avoid division by zero
        stds = self.xp.where(stds == 0, 1, stds)

        normalized = (stacked - means) / stds

        # Convert back to list
        return [self.to_cpu(arr) for arr in normalized]

    def compute_correlation_matrix(self, returns_dict):
        """
        Compute correlation matrix for multiple assets (GPU-accelerated)

        Args:
            returns_dict: Dictionary mapping ticker to returns array

        Returns:
            Correlation matrix as NumPy array
        """
        if not returns_dict:
            return np.array([[]])

        # Stack returns into matrix
        tickers = list(returns_dict.keys())
        returns_matrix = self.xp.array([returns_dict[t] for t in tickers])

        # Compute correlation matrix
        corr_matrix = self.xp.corrcoef(returns_matrix)

        return self.to_cpu(corr_matrix)

    def __repr__(self):
        device = "GPU (CUDA)" if self.use_gpu else "CPU"
        return f"GPUAccelerator(device={device})"


def use_gpu_if_available():
    """
    Helper function to get GPU accelerator

    Returns:
        GPUAccelerator instance
    """
    return GPUAccelerator(use_gpu=True)


# Convenience functions that auto-detect GPU
def compute_sharpe_gpu(returns, risk_free_rate=0.02, periods_per_year=252):
    """Compute Sharpe ratio with automatic GPU detection"""
    accelerator = use_gpu_if_available()
    return accelerator.compute_sharpe_ratio(returns, risk_free_rate, periods_per_year)


def compute_max_drawdown_gpu(values):
    """Compute max drawdown with automatic GPU detection"""
    accelerator = use_gpu_if_available()
    return accelerator.compute_max_drawdown(values)


def compute_returns_gpu(prices):
    """Compute returns with automatic GPU detection"""
    accelerator = use_gpu_if_available()
    return accelerator.compute_returns(prices)
