"""Performance metrics calculation for trading strategies"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Calculate comprehensive performance metrics for trading strategies"""

    @staticmethod
    def calculate_total_return(initial_capital: float, final_value: float) -> float:
        """
        Calculate total return percentage

        Args:
            initial_capital: Starting capital
            final_value: Final portfolio value

        Returns:
            Total return percentage
        """
        if initial_capital == 0:
            return 0.0
        return ((final_value - initial_capital) / initial_capital) * 100

    @staticmethod
    def calculate_annualized_return(total_return_pct: float, days: int) -> float:
        """
        Calculate annualized return

        Args:
            total_return_pct: Total return percentage
            days: Number of days in period

        Returns:
            Annualized return percentage
        """
        if days == 0:
            return 0.0

        years = days / 365.25
        if years == 0:
            return 0.0

        annualized = ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100
        return float(annualized)

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calculate annualized Sharpe ratio

        Args:
            returns: Series of daily returns
            risk_free_rate: Annual risk-free rate (default 2%)

        Returns:
            Sharpe ratio
        """
        if returns.empty or len(returns) < 2:
            return 0.0

        returns = returns.dropna()

        if len(returns) < 2:
            return 0.0

        # Annualize (252 trading days)
        mean_return = returns.mean() * 252
        std_return = returns.std() * np.sqrt(252)

        if std_return == 0:
            return 0.0

        sharpe = (mean_return - risk_free_rate) / std_return
        return float(sharpe)

    @staticmethod
    def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calculate annualized Sortino ratio (downside deviation)

        Args:
            returns: Series of daily returns
            risk_free_rate: Annual risk-free rate (default 2%)

        Returns:
            Sortino ratio
        """
        if returns.empty or len(returns) < 2:
            return 0.0

        returns = returns.dropna()

        if len(returns) < 2:
            return 0.0

        # Annualize mean
        mean_return = returns.mean() * 252

        # Downside deviation (only negative returns)
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0:
            return float('inf')  # No downside volatility

        downside_std = downside_returns.std() * np.sqrt(252)

        if downside_std == 0:
            return 0.0

        sortino = (mean_return - risk_free_rate) / downside_std
        return float(sortino)

    @staticmethod
    def calculate_max_drawdown(values: pd.Series) -> Tuple[float, Optional[pd.Timestamp], Optional[pd.Timestamp]]:
        """
        Calculate maximum drawdown and its dates

        Args:
            values: Series of portfolio values over time

        Returns:
            Tuple of (max_drawdown_pct, peak_date, trough_date)
        """
        if values.empty or len(values) < 2:
            return 0.0, None, None

        # Calculate running maximum
        running_max = values.expanding().max()

        # Calculate drawdown
        drawdown = (values - running_max) / running_max

        # Find maximum drawdown
        max_dd_idx = drawdown.idxmin()
        max_dd = drawdown[max_dd_idx] * 100

        # Find peak before the drawdown
        peak_idx = values[:max_dd_idx].idxmax()

        return float(max_dd), peak_idx, max_dd_idx

    @staticmethod
    def calculate_calmar_ratio(annualized_return: float, max_drawdown: float) -> float:
        """
        Calculate Calmar ratio (return / max drawdown)

        Args:
            annualized_return: Annualized return percentage
            max_drawdown: Maximum drawdown percentage (negative)

        Returns:
            Calmar ratio
        """
        if max_drawdown >= 0:
            return 0.0

        return annualized_return / abs(max_drawdown)

    @staticmethod
    def calculate_win_rate(trades_df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate win rate from trades

        Args:
            trades_df: DataFrame with trade history

        Returns:
            Dictionary with win rate metrics
        """
        if trades_df.empty:
            return {
                'win_rate': 0.0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_trades': 0
            }

        # Match buy and sell trades
        buy_trades = {}
        winning_trades = 0
        losing_trades = 0
        total_closed_trades = 0

        for _, trade in trades_df.iterrows():
            ticker = trade['ticker']

            if trade['action'] == 'buy':
                if ticker not in buy_trades:
                    buy_trades[ticker] = []
                buy_trades[ticker].append(trade['price'])

            elif trade['action'] == 'sell':
                if ticker in buy_trades and buy_trades[ticker]:
                    buy_price = buy_trades[ticker].pop(0)
                    total_closed_trades += 1

                    if trade['price'] > buy_price:
                        winning_trades += 1
                    else:
                        losing_trades += 1

        win_rate = (winning_trades / total_closed_trades * 100) if total_closed_trades > 0 else 0.0

        return {
            'win_rate': win_rate,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'total_trades': total_closed_trades
        }

    @staticmethod
    def calculate_profit_factor(trades_df: pd.DataFrame) -> float:
        """
        Calculate profit factor (gross profit / gross loss)

        Args:
            trades_df: DataFrame with trade history

        Returns:
            Profit factor
        """
        if trades_df.empty:
            return 0.0

        buy_trades = {}
        gross_profit = 0.0
        gross_loss = 0.0

        for _, trade in trades_df.iterrows():
            ticker = trade['ticker']

            if trade['action'] == 'buy':
                if ticker not in buy_trades:
                    buy_trades[ticker] = []
                buy_trades[ticker].append({
                    'price': trade['price'],
                    'shares': trade['shares']
                })

            elif trade['action'] == 'sell':
                if ticker in buy_trades and buy_trades[ticker]:
                    buy_info = buy_trades[ticker].pop(0)
                    profit = (trade['price'] - buy_info['price']) * buy_info['shares']

                    if profit > 0:
                        gross_profit += profit
                    else:
                        gross_loss += abs(profit)

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    @staticmethod
    def calculate_average_trade_metrics(trades_df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate average trade metrics

        Args:
            trades_df: DataFrame with trade history

        Returns:
            Dictionary with average trade metrics
        """
        if trades_df.empty:
            return {
                'avg_profit': 0.0,
                'avg_profit_pct': 0.0,
                'avg_winner': 0.0,
                'avg_loser': 0.0,
                'avg_winner_pct': 0.0,
                'avg_loser_pct': 0.0,
                'avg_hold_time': 0.0
            }

        buy_trades = {}
        profits = []
        profit_pcts = []
        winners = []
        losers = []
        winner_pcts = []
        loser_pcts = []
        hold_times = []

        for _, trade in trades_df.iterrows():
            ticker = trade['ticker']

            if trade['action'] == 'buy':
                if ticker not in buy_trades:
                    buy_trades[ticker] = []
                buy_trades[ticker].append({
                    'price': trade['price'],
                    'shares': trade['shares'],
                    'date': trade['date']
                })

            elif trade['action'] == 'sell':
                if ticker in buy_trades and buy_trades[ticker]:
                    buy_info = buy_trades[ticker].pop(0)

                    profit = (trade['price'] - buy_info['price']) * buy_info['shares']
                    profit_pct = ((trade['price'] - buy_info['price']) / buy_info['price']) * 100

                    profits.append(profit)
                    profit_pcts.append(profit_pct)

                    if profit > 0:
                        winners.append(profit)
                        winner_pcts.append(profit_pct)
                    else:
                        losers.append(profit)
                        loser_pcts.append(profit_pct)

                    # Calculate hold time
                    hold_time = (trade['date'] - buy_info['date']).days
                    hold_times.append(hold_time)

        return {
            'avg_profit': np.mean(profits) if profits else 0.0,
            'avg_profit_pct': np.mean(profit_pcts) if profit_pcts else 0.0,
            'avg_winner': np.mean(winners) if winners else 0.0,
            'avg_loser': np.mean(losers) if losers else 0.0,
            'avg_winner_pct': np.mean(winner_pcts) if winner_pcts else 0.0,
            'avg_loser_pct': np.mean(loser_pcts) if loser_pcts else 0.0,
            'avg_hold_time': np.mean(hold_times) if hold_times else 0.0
        }

    @staticmethod
    def calculate_volatility(returns: pd.Series) -> Dict[str, float]:
        """
        Calculate volatility metrics

        Args:
            returns: Series of daily returns

        Returns:
            Dictionary with volatility metrics
        """
        if returns.empty or len(returns) < 2:
            return {
                'daily_volatility': 0.0,
                'annual_volatility': 0.0,
                'downside_volatility': 0.0
            }

        returns = returns.dropna()

        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)

        # Downside volatility
        downside_returns = returns[returns < 0]
        downside_vol = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0.0

        return {
            'daily_volatility': float(daily_vol),
            'annual_volatility': float(annual_vol),
            'downside_volatility': float(downside_vol)
        }

    @staticmethod
    def calculate_information_ratio(returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """
        Calculate information ratio (excess return / tracking error)

        Args:
            returns: Strategy returns series
            benchmark_returns: Benchmark returns series

        Returns:
            Information ratio
        """
        if returns.empty or benchmark_returns.empty:
            return 0.0

        # Align series
        returns, benchmark_returns = returns.align(benchmark_returns, join='inner')

        if len(returns) < 2:
            return 0.0

        # Calculate excess returns
        excess_returns = returns - benchmark_returns

        # Tracking error (std of excess returns)
        tracking_error = excess_returns.std() * np.sqrt(252)

        if tracking_error == 0:
            return 0.0

        # Annualize excess return
        mean_excess = excess_returns.mean() * 252

        return float(mean_excess / tracking_error)

    @staticmethod
    def calculate_comprehensive_metrics(backtest_results: Dict) -> Dict:
        """
        Calculate comprehensive set of metrics from backtest results

        Args:
            backtest_results: Results dictionary from BacktestEngine

        Returns:
            Dictionary with all calculated metrics
        """
        metrics = {}

        # Basic returns
        metrics['total_return'] = backtest_results.get('total_return', 0.0)
        metrics['total_profit'] = backtest_results.get('total_profit', 0.0)

        # Annualized return
        days = backtest_results.get('calendar_days', 0)
        if days > 0:
            metrics['annualized_return'] = PerformanceMetrics.calculate_annualized_return(
                metrics['total_return'], days
            )
        else:
            metrics['annualized_return'] = 0.0

        # Risk metrics
        metrics['sharpe_ratio'] = backtest_results.get('sharpe_ratio', 0.0)
        metrics['sortino_ratio'] = backtest_results.get('sortino_ratio', 0.0)
        metrics['max_drawdown'] = backtest_results.get('max_drawdown', 0.0)

        # Calmar ratio
        if metrics['max_drawdown'] < 0:
            metrics['calmar_ratio'] = PerformanceMetrics.calculate_calmar_ratio(
                metrics['annualized_return'],
                metrics['max_drawdown']
            )
        else:
            metrics['calmar_ratio'] = 0.0

        # Trade metrics
        trades_df = backtest_results.get('trades', pd.DataFrame())

        if not trades_df.empty:
            win_rate_metrics = PerformanceMetrics.calculate_win_rate(trades_df)
            metrics.update(win_rate_metrics)

            metrics['profit_factor'] = PerformanceMetrics.calculate_profit_factor(trades_df)

            avg_trade_metrics = PerformanceMetrics.calculate_average_trade_metrics(trades_df)
            metrics.update(avg_trade_metrics)
        else:
            metrics['win_rate'] = 0.0
            metrics['winning_trades'] = 0
            metrics['losing_trades'] = 0
            metrics['profit_factor'] = 0.0

        # Volatility metrics
        value_df = backtest_results.get('value_history', pd.DataFrame())

        if not value_df.empty and 'returns' in value_df.columns:
            vol_metrics = PerformanceMetrics.calculate_volatility(value_df['returns'])
            metrics.update(vol_metrics)
        else:
            metrics['daily_volatility'] = 0.0
            metrics['annual_volatility'] = 0.0
            metrics['downside_volatility'] = 0.0

        # Trading activity
        metrics['num_trades'] = backtest_results.get('num_trades', 0)
        metrics['unique_tickers'] = backtest_results.get('unique_tickers_traded', 0)

        return metrics

    @staticmethod
    def calculate_rolling_metrics(value_df: pd.DataFrame, window: int = 30) -> pd.DataFrame:
        """
        Calculate rolling performance metrics

        Args:
            value_df: DataFrame with value history
            window: Rolling window size in days

        Returns:
            DataFrame with rolling metrics
        """
        if value_df.empty or 'returns' not in value_df.columns:
            return pd.DataFrame()

        df = value_df.copy()

        # Rolling return
        df['rolling_return'] = df['returns'].rolling(window).sum() * 100

        # Rolling volatility
        df['rolling_volatility'] = df['returns'].rolling(window).std() * np.sqrt(252)

        # Rolling Sharpe (simplified)
        df['rolling_sharpe'] = (df['returns'].rolling(window).mean() * 252) / \
                               (df['returns'].rolling(window).std() * np.sqrt(252))

        # Rolling max drawdown
        rolling_max = df['total_value'].rolling(window, min_periods=1).max()
        df['rolling_drawdown'] = (df['total_value'] - rolling_max) / rolling_max * 100

        return df

    @staticmethod
    def compare_strategies(results_list: List[Dict], strategy_names: List[str]) -> pd.DataFrame:
        """
        Compare multiple strategies

        Args:
            results_list: List of backtest results dictionaries
            strategy_names: List of strategy names

        Returns:
            DataFrame comparing strategies
        """
        if not results_list or not strategy_names:
            return pd.DataFrame()

        comparison_data = []

        for results, name in zip(results_list, strategy_names):
            metrics = PerformanceMetrics.calculate_comprehensive_metrics(results)
            metrics['strategy'] = name
            comparison_data.append(metrics)

        df = pd.DataFrame(comparison_data)
        df.set_index('strategy', inplace=True)

        return df

    @staticmethod
    def format_metrics_report(metrics: Dict) -> str:
        """
        Format metrics as readable report

        Args:
            metrics: Dictionary of metrics

        Returns:
            Formatted string report
        """
        report = """
Performance Metrics Report
==========================

Returns:
  Total Return:           {total_return:.2f}%
  Annualized Return:      {annualized_return:.2f}%
  Total Profit/Loss:      ${total_profit:,.2f}

Risk Metrics:
  Sharpe Ratio:           {sharpe_ratio:.2f}
  Sortino Ratio:          {sortino_ratio:.2f}
  Calmar Ratio:           {calmar_ratio:.2f}
  Max Drawdown:           {max_drawdown:.2f}%

Volatility:
  Daily Volatility:       {daily_volatility:.2%}
  Annual Volatility:      {annual_volatility:.2%}
  Downside Volatility:    {downside_volatility:.2%}

Trading Activity:
  Total Trades:           {num_trades}
  Win Rate:               {win_rate:.2f}%
  Winning Trades:         {winning_trades}
  Losing Trades:          {losing_trades}
  Profit Factor:          {profit_factor:.2f}

Average Trade:
  Avg Profit:             ${avg_profit:.2f}
  Avg Profit %:           {avg_profit_pct:.2f}%
  Avg Winner:             ${avg_winner:.2f}
  Avg Loser:              ${avg_loser:.2f}
  Avg Hold Time:          {avg_hold_time:.1f} days
""".format(**metrics)

        return report
