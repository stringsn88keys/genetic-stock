"""Fitness evaluation for trading algorithms"""

import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class FitnessEvaluator:
    """Evaluates fitness of trading algorithms"""

    def __init__(self, config: Dict):
        """
        Initialize fitness evaluator

        Args:
            config: Configuration dictionary with fitness weights
        """
        self.config = config
        fitness_config = config.get('fitness', {})

        # Fitness function weights
        self.alpha = fitness_config.get('alpha', 0.4)    # Total return
        self.beta = fitness_config.get('beta', 0.25)     # Sharpe ratio
        self.gamma = fitness_config.get('gamma', 0.15)   # Win rate
        self.delta = fitness_config.get('delta', 0.1)    # Max drawdown penalty
        self.epsilon = fitness_config.get('epsilon', 0.05)  # Transaction cost penalty
        self.zeta = fitness_config.get('zeta', 0.05)     # Inactivity penalty

        self.min_trades = fitness_config.get('min_trades', 10)
        self.risk_free_rate = 0.02  # 2% annual risk-free rate

    def calculate_fitness(self, performance_metrics: Dict) -> float:
        """
        Calculate fitness score from performance metrics

        Args:
            performance_metrics: Dictionary with performance data

        Returns:
            Fitness score
        """
        try:
            # Extract metrics
            total_return = performance_metrics.get('total_return', 0.0)
            sharpe_ratio = performance_metrics.get('sharpe_ratio', 0.0)
            win_rate = performance_metrics.get('win_rate', 0.0)
            max_drawdown = performance_metrics.get('max_drawdown', 0.0)
            n_trades = performance_metrics.get('n_trades', 0)
            transaction_cost_ratio = performance_metrics.get('transaction_cost_ratio', 0.0)

            # Normalize Sharpe ratio (cap at reasonable range)
            sharpe_normalized = np.clip(sharpe_ratio / 3.0, -1, 1)

            # Calculate fitness components
            return_component = self.alpha * total_return
            sharpe_component = self.beta * sharpe_normalized
            winrate_component = self.gamma * win_rate

            # Penalties
            drawdown_penalty = self.delta * abs(max_drawdown)
            transaction_penalty = self.epsilon * transaction_cost_ratio

            # Inactivity penalty
            inactivity_penalty = 0.0
            if n_trades < self.min_trades:
                inactivity_penalty = self.zeta * (1.0 - n_trades / self.min_trades)

            # Total fitness
            fitness = (return_component +
                      sharpe_component +
                      winrate_component -
                      drawdown_penalty -
                      transaction_penalty -
                      inactivity_penalty)

            logger.debug(f"Fitness: {fitness:.4f} (return={return_component:.4f}, "
                        f"sharpe={sharpe_component:.4f}, winrate={winrate_component:.4f}, "
                        f"drawdown_penalty={drawdown_penalty:.4f})")

            return float(fitness)

        except Exception as e:
            logger.error(f"Error calculating fitness: {e}")
            return -999.0  # Very poor fitness for invalid individuals

    def calculate_sharpe_ratio(self, returns: np.ndarray, periods_per_year: int = 252) -> float:
        """
        Calculate Sharpe ratio

        Args:
            returns: Array of returns
            periods_per_year: Trading periods per year (252 for daily)

        Returns:
            Sharpe ratio
        """
        if len(returns) == 0:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualized Sharpe ratio
        sharpe = (mean_return - self.risk_free_rate / periods_per_year) / std_return
        sharpe_annualized = sharpe * np.sqrt(periods_per_year)

        return float(sharpe_annualized)

    def calculate_sortino_ratio(self, returns: np.ndarray, periods_per_year: int = 252) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        if len(returns) == 0:
            return 0.0

        mean_return = np.mean(returns)
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0:
            return 0.0

        downside_std = np.std(downside_returns)

        if downside_std == 0:
            return 0.0

        sortino = (mean_return - self.risk_free_rate / periods_per_year) / downside_std
        sortino_annualized = sortino * np.sqrt(periods_per_year)

        return float(sortino_annualized)

    def calculate_max_drawdown(self, portfolio_values: np.ndarray) -> float:
        """
        Calculate maximum drawdown

        Args:
            portfolio_values: Array of portfolio values over time

        Returns:
            Maximum drawdown (negative value)
        """
        if len(portfolio_values) == 0:
            return 0.0

        peak = np.maximum.accumulate(portfolio_values)
        drawdown = (portfolio_values - peak) / peak
        max_dd = np.min(drawdown)

        return float(max_dd)

    def calculate_calmar_ratio(self, total_return: float, max_drawdown: float,
                               years: float) -> float:
        """Calculate Calmar ratio (annual return / max drawdown)"""
        if max_drawdown == 0:
            return 0.0

        annual_return = total_return / years
        calmar = annual_return / abs(max_drawdown)

        return float(calmar)

    def calculate_win_rate(self, trades: list) -> float:
        """
        Calculate win rate from trades

        Args:
            trades: List of trade dictionaries with 'profit' or 'return' key

        Returns:
            Win rate (0.0 to 1.0)
        """
        if not trades:
            return 0.0

        winning_trades = sum(1 for trade in trades
                           if trade.get('profit', 0) > 0 or trade.get('return', 0) > 0)

        win_rate = winning_trades / len(trades)

        return float(win_rate)

    def calculate_profit_factor(self, trades: list) -> float:
        """Calculate profit factor (gross profits / gross losses)"""
        if not trades:
            return 0.0

        gross_profit = sum(trade.get('profit', 0) for trade in trades
                          if trade.get('profit', 0) > 0)
        gross_loss = abs(sum(trade.get('profit', 0) for trade in trades
                            if trade.get('profit', 0) < 0))

        if gross_loss == 0:
            return gross_profit if gross_profit > 0 else 0.0

        return float(gross_profit / gross_loss)

    def evaluate_backtest_results(self, backtest_results: Dict) -> Dict:
        """
        Evaluate complete backtest results

        Args:
            backtest_results: Dictionary with backtest data

        Returns:
            Dictionary with all performance metrics
        """
        portfolio_values = np.array(backtest_results.get('portfolio_values', []))
        trades = backtest_results.get('trades', [])

        if len(portfolio_values) == 0:
            return self._default_metrics()

        # Calculate returns
        returns = np.diff(portfolio_values) / portfolio_values[:-1]

        # Total return
        initial_value = portfolio_values[0]
        final_value = portfolio_values[-1]
        total_return = (final_value - initial_value) / initial_value

        # Time-based metrics
        n_days = len(portfolio_values)
        years = n_days / 252.0

        # Calculate all metrics
        metrics = {
            'total_return': float(total_return),
            'annualized_return': float((1 + total_return) ** (1 / years) - 1) if years > 0 else 0.0,
            'sharpe_ratio': self.calculate_sharpe_ratio(returns),
            'sortino_ratio': self.calculate_sortino_ratio(returns),
            'max_drawdown': self.calculate_max_drawdown(portfolio_values),
            'win_rate': self.calculate_win_rate(trades),
            'profit_factor': self.calculate_profit_factor(trades),
            'n_trades': len(trades),
            'transaction_cost_ratio': len(trades) * 0.001 / max(total_return, 0.01),  # Simplified
            'final_value': float(final_value),
            'initial_value': float(initial_value),
        }

        # Calculate fitness
        metrics['fitness'] = self.calculate_fitness(metrics)

        return metrics

    def _default_metrics(self) -> Dict:
        """Return default metrics for failed evaluations"""
        return {
            'total_return': 0.0,
            'annualized_return': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'n_trades': 0,
            'transaction_cost_ratio': 0.0,
            'final_value': 1000.0,
            'initial_value': 1000.0,
            'fitness': -999.0
        }
