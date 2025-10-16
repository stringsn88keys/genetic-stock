"""Backtesting engine for trading strategies"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
from .portfolio import Portfolio
from .executor import TradeExecutor
from .signals import SignalGenerator
from ..genetic.chromosome import Chromosome
from ..data.normalizer import DataNormalizer
from ..utils.gpu_utils import GPUAccelerator

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Engine for backtesting trading strategies"""

    def __init__(self,
                 chromosome: Chromosome,
                 initial_capital: float = 10000.0,
                 commission: float = 0.0,
                 slippage: float = 0.001,
                 max_positions: int = 10,
                 min_cash_reserve: float = 0.05,
                 use_gpu: bool = True):
        """
        Initialize backtest engine

        Args:
            chromosome: Chromosome to test
            initial_capital: Starting capital
            commission: Commission per trade
            slippage: Slippage percentage
            max_positions: Maximum simultaneous positions
            min_cash_reserve: Minimum cash reserve percentage
            use_gpu: Whether to use GPU acceleration if available
        """
        self.chromosome = chromosome
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.max_positions = max_positions
        self.min_cash_reserve = min_cash_reserve

        # Initialize GPU accelerator
        self.gpu = GPUAccelerator(use_gpu=use_gpu)

        # Initialize components
        self.portfolio = Portfolio(
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage
        )

        self.executor = TradeExecutor(
            portfolio=self.portfolio,
            chromosome=chromosome,
            max_positions=max_positions,
            min_cash_reserve=min_cash_reserve
        )

        self.signal_generator = SignalGenerator(chromosome)
        self.normalizer = DataNormalizer()

        # Results
        self.results = None

    def run(self, stock_data: Dict[str, pd.DataFrame],
            start_date: Optional[pd.Timestamp] = None,
            end_date: Optional[pd.Timestamp] = None) -> Dict:
        """
        Run backtest on historical data

        Args:
            stock_data: Dictionary mapping ticker to OHLCV DataFrame
            start_date: Start date for backtest (None = earliest available)
            end_date: End date for backtest (None = latest available)

        Returns:
            Dictionary with backtest results
        """
        logger.info(f"Starting backtest with {len(stock_data)} stocks")

        # Reset portfolio
        self.portfolio.reset()

        # Normalize and prepare data
        prepared_data = {}
        for ticker, df in stock_data.items():
            try:
                # Ensure date index
                if 'date' in df.columns:
                    df = df.set_index('date')

                # Normalize and calculate features
                normalized = self.normalizer.normalize_full(df)
                normalized = self.normalizer.calculate_technical_features(
                    normalized,
                    short_window=self.chromosome.genes['windows']['short'],
                    medium_window=self.chromosome.genes['windows']['medium'],
                    long_window=self.chromosome.genes['windows']['long']
                )

                prepared_data[ticker] = normalized
                logger.debug(f"Prepared data for {ticker}: {len(normalized)} rows")

            except Exception as e:
                logger.error(f"Error preparing data for {ticker}: {e}")
                continue

        if not prepared_data:
            logger.error("No data prepared for backtesting")
            return self._empty_results()

        # Generate signals for all stocks
        stock_signals = self.signal_generator.generate_multi_stock_signals(prepared_data)

        # Get date range
        all_dates = set()
        for df in prepared_data.values():
            all_dates.update(df.index)

        dates = sorted(list(all_dates))

        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]

        if not dates:
            logger.error("No dates in backtest range")
            return self._empty_results()

        logger.info(f"Backtesting from {dates[0].date()} to {dates[-1].date()} ({len(dates)} days)")

        # Run backtest day by day
        # To avoid look-ahead bias: signals generated on day[i] are executed at day[i+1] open
        pending_signals = {}

        for i, date in enumerate(dates):
            # First, execute any pending signals from previous day using today's open price
            if pending_signals and i > 0:
                execution_prices = {}
                for ticker in pending_signals.keys():
                    # Use open price of current day to execute yesterday's signals
                    if ticker in stock_data and 'open' in stock_data[ticker].columns:
                        price_df = stock_data[ticker]
                        if date in price_df.index:
                            execution_prices[ticker] = price_df.loc[date, 'open']

                if execution_prices:
                    self.executor.execute_signals(pending_signals, execution_prices, date)

                pending_signals = {}

            # Now generate signals for current day (to be executed tomorrow)
            current_signals = {}

            for ticker in prepared_data.keys():
                signal_df = stock_signals[ticker]

                # Get signal for this date
                if date in signal_df.index:
                    signal = signal_df.loc[date, 'signal']
                    if signal != 'hold':  # Only store non-hold signals
                        current_signals[ticker] = signal

            # Store signals for execution next day
            if current_signals:
                pending_signals = current_signals

            # Log progress periodically
            if (i + 1) % 100 == 0:
                logger.debug(f"Processed {i + 1}/{len(dates)} days")

        # Close all positions at end
        final_prices = {}
        for ticker, df in stock_data.items():
            if dates[-1] in df.index and 'close' in df.columns:
                final_prices[ticker] = df.loc[dates[-1], 'close']

        self.executor.close_all_positions(final_prices, dates[-1])

        # Calculate results
        self.results = self._calculate_results(dates[0], dates[-1])

        logger.info(f"Backtest complete: Return={self.results['total_return']:.2f}%, "
                   f"Trades={self.results['num_trades']}")

        return self.results

    def _calculate_results(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict:
        """
        Calculate backtest results and metrics

        Args:
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            Dictionary with all results
        """
        # Get portfolio value history
        value_df = self.portfolio.get_value_dataframe()
        trades_df = self.portfolio.get_trades_dataframe()

        # Basic metrics
        final_value = self.portfolio.get_total_value()
        total_return = ((final_value - self.initial_capital) / self.initial_capital) * 100

        # Calculate returns series
        if not value_df.empty:
            value_df['returns'] = value_df['total_value'].pct_change()
            value_df['cumulative_returns'] = (1 + value_df['returns']).cumprod() - 1
        else:
            value_df['returns'] = 0
            value_df['cumulative_returns'] = 0

        # Trade metrics
        num_trades = len(trades_df)
        num_buy_trades = len(trades_df[trades_df['action'] == 'buy']) if not trades_df.empty else 0
        num_sell_trades = len(trades_df[trades_df['action'] == 'sell']) if not trades_df.empty else 0

        # Win rate
        winning_trades = self.portfolio.get_num_winning_trades()
        win_rate = (winning_trades / num_sell_trades * 100) if num_sell_trades > 0 else 0

        # Sharpe ratio (annualized)
        sharpe_ratio = self._calculate_sharpe_ratio(value_df)

        # Maximum drawdown
        max_drawdown = self._calculate_max_drawdown(value_df)

        # Sortino ratio
        sortino_ratio = self._calculate_sortino_ratio(value_df)

        # Calculate days
        trading_days = len(value_df)
        calendar_days = (end_date - start_date).days

        # Average trade metrics
        avg_trade_return = 0
        if not trades_df.empty and num_sell_trades > 0:
            # Calculate average profit per closed trade
            buy_prices = {}
            trade_returns = []

            for _, trade in trades_df.iterrows():
                ticker = trade['ticker']
                if trade['action'] == 'buy':
                    if ticker not in buy_prices:
                        buy_prices[ticker] = []
                    buy_prices[ticker].append(trade['price'])
                elif trade['action'] == 'sell' and ticker in buy_prices and buy_prices[ticker]:
                    buy_price = buy_prices[ticker].pop(0)
                    trade_return = ((trade['price'] - buy_price) / buy_price) * 100
                    trade_returns.append(trade_return)

            if trade_returns:
                avg_trade_return = np.mean(trade_returns)

        # Execution summary
        execution_summary = self.executor.get_execution_summary()

        results = {
            # Date range
            'start_date': start_date,
            'end_date': end_date,
            'trading_days': trading_days,
            'calendar_days': calendar_days,

            # Capital metrics
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_profit': final_value - self.initial_capital,

            # Risk metrics
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,

            # Trade metrics
            'num_trades': num_trades,
            'num_buy_trades': num_buy_trades,
            'num_sell_trades': num_sell_trades,
            'win_rate': win_rate,
            'winning_trades': winning_trades,
            'losing_trades': num_sell_trades - winning_trades,
            'avg_trade_return': avg_trade_return,

            # Execution metrics
            'unique_tickers_traded': execution_summary['unique_tickers'],
            'total_commission': execution_summary['total_commission'],
            'total_slippage': execution_summary['total_slippage'],

            # DataFrames
            'value_history': value_df,
            'trades': trades_df,

            # Chromosome info
            'chromosome': self.chromosome.to_dict()
        }

        return results

    def _calculate_sharpe_ratio(self, value_df: pd.DataFrame,
                               risk_free_rate: float = 0.02) -> float:
        """
        Calculate annualized Sharpe ratio (GPU-accelerated)

        Args:
            value_df: DataFrame with returns
            risk_free_rate: Annual risk-free rate

        Returns:
            Sharpe ratio
        """
        if value_df.empty or 'returns' not in value_df.columns:
            return 0.0

        returns = value_df['returns'].dropna()

        if len(returns) < 2:
            return 0.0

        # Use GPU-accelerated calculation
        returns_array = returns.values
        sharpe = self.gpu.compute_sharpe_ratio(
            returns_array,
            risk_free_rate=risk_free_rate,
            periods_per_year=252
        )
        return float(sharpe)

    def _calculate_sortino_ratio(self, value_df: pd.DataFrame,
                                 risk_free_rate: float = 0.02) -> float:
        """
        Calculate annualized Sortino ratio (uses downside deviation)

        Args:
            value_df: DataFrame with returns
            risk_free_rate: Annual risk-free rate

        Returns:
            Sortino ratio
        """
        if value_df.empty or 'returns' not in value_df.columns:
            return 0.0

        returns = value_df['returns'].dropna()

        if len(returns) < 2:
            return 0.0

        # Annualize mean return
        mean_return = returns.mean() * 252

        # Calculate downside deviation (only negative returns)
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0:
            return float('inf')  # No downside

        downside_std = downside_returns.std() * np.sqrt(252)

        if downside_std == 0:
            return 0.0

        sortino = (mean_return - risk_free_rate) / downside_std
        return float(sortino)

    def _calculate_max_drawdown(self, value_df: pd.DataFrame) -> float:
        """
        Calculate maximum drawdown percentage (GPU-accelerated)

        Args:
            value_df: DataFrame with total_value column

        Returns:
            Maximum drawdown percentage (negative value)
        """
        if value_df.empty or 'total_value' not in value_df.columns:
            return 0.0

        values = value_df['total_value']

        if len(values) < 2:
            return 0.0

        # Use GPU-accelerated calculation
        values_array = values.values
        max_dd = self.gpu.compute_max_drawdown(values_array)

        # Convert to percentage
        return float(max_dd * 100)

    def _empty_results(self) -> Dict:
        """Return empty results dictionary"""
        return {
            'start_date': None,
            'end_date': None,
            'trading_days': 0,
            'calendar_days': 0,
            'initial_capital': self.initial_capital,
            'final_value': self.initial_capital,
            'total_return': 0.0,
            'total_profit': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'max_drawdown': 0.0,
            'num_trades': 0,
            'num_buy_trades': 0,
            'num_sell_trades': 0,
            'win_rate': 0.0,
            'winning_trades': 0,
            'losing_trades': 0,
            'avg_trade_return': 0.0,
            'unique_tickers_traded': 0,
            'total_commission': 0.0,
            'total_slippage': 0.0,
            'value_history': pd.DataFrame(),
            'trades': pd.DataFrame(),
            'chromosome': self.chromosome.to_dict()
        }

    def get_results_summary(self) -> str:
        """
        Get formatted results summary

        Returns:
            String with formatted results
        """
        if self.results is None:
            return "No backtest results available. Run backtest first."

        r = self.results

        summary = f"""
Backtest Results Summary
========================
Period: {r['start_date'].date()} to {r['end_date'].date()} ({r['trading_days']} trading days)

Performance:
  Initial Capital:    ${r['initial_capital']:,.2f}
  Final Value:        ${r['final_value']:,.2f}
  Total Return:       {r['total_return']:.2f}%
  Total Profit/Loss:  ${r['total_profit']:,.2f}

Risk Metrics:
  Sharpe Ratio:       {r['sharpe_ratio']:.2f}
  Sortino Ratio:      {r['sortino_ratio']:.2f}
  Max Drawdown:       {r['max_drawdown']:.2f}%

Trading Activity:
  Total Trades:       {r['num_trades']}
  Buy Trades:         {r['num_buy_trades']}
  Sell Trades:        {r['num_sell_trades']}
  Win Rate:           {r['win_rate']:.2f}%
  Winning Trades:     {r['winning_trades']}
  Losing Trades:      {r['losing_trades']}
  Avg Trade Return:   {r['avg_trade_return']:.2f}%

Execution:
  Unique Tickers:     {r['unique_tickers_traded']}
  Total Commission:   ${r['total_commission']:.2f}
  Total Slippage:     ${r['total_slippage']:.2f}
"""
        return summary

    def __repr__(self) -> str:
        return f"BacktestEngine(capital=${self.initial_capital:,.2f}, chromosome={self.chromosome})"
