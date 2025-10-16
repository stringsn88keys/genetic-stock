"""Trade execution logic"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
import logging
from .portfolio import Portfolio
from .signals import SignalGenerator
from ..genetic.chromosome import Chromosome

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Execute trades based on signals and risk management rules"""

    def __init__(self,
                 portfolio: Portfolio,
                 chromosome: Chromosome,
                 max_positions: int = 10,
                 min_cash_reserve: float = 0.05):
        """
        Initialize trade executor

        Args:
            portfolio: Portfolio instance to execute trades on
            chromosome: Chromosome with trading parameters
            max_positions: Maximum number of simultaneous positions
            min_cash_reserve: Minimum cash reserve as percentage of portfolio
        """
        self.portfolio = portfolio
        self.chromosome = chromosome
        self.max_positions = max_positions
        self.min_cash_reserve = min_cash_reserve

        self.risk_params = chromosome.genes['risk']
        self.signal_generator = SignalGenerator(chromosome)

    def execute_signals(self,
                       signals: Dict[str, str],
                       prices: Dict[str, float],
                       date: pd.Timestamp) -> Dict[str, str]:
        """
        Execute trades based on signals

        Args:
            signals: Dictionary mapping ticker to signal ('buy', 'sell', 'hold')
            prices: Dictionary mapping ticker to current price
            date: Current date

        Returns:
            Dictionary of executed actions per ticker
        """
        actions = {}

        # First, check for risk management triggers (stop loss, take profit)
        triggered_tickers = self.portfolio.check_risk_triggers(date, prices)
        for ticker in triggered_tickers:
            actions[ticker] = 'risk_exit'

        # Process sell signals first (to free up capital)
        for ticker, signal in signals.items():
            if signal == 'sell' and self.portfolio.has_position(ticker):
                if ticker in prices:
                    success = self.execute_sell(ticker, prices[ticker], date)
                    if success:
                        actions[ticker] = 'sold'

        # Process buy signals
        for ticker, signal in signals.items():
            if signal == 'buy' and ticker in prices:
                # Don't buy if we already have a position
                if not self.portfolio.has_position(ticker):
                    success = self.execute_buy(ticker, prices[ticker], date)
                    if success:
                        actions[ticker] = 'bought'

        # Record portfolio value
        self.portfolio.record_value(date)

        return actions

    def execute_buy(self, ticker: str, price: float, date: pd.Timestamp) -> bool:
        """
        Execute a buy order with risk management

        Args:
            ticker: Stock ticker
            price: Current price
            date: Trade date

        Returns:
            True if trade executed, False otherwise
        """
        # Check if we can add more positions
        if len(self.portfolio.positions) >= self.max_positions:
            logger.debug(f"Cannot buy {ticker}: max positions reached")
            return False

        # Calculate position size
        max_position_pct = self.risk_params['max_position_pct']
        available_capital = self.portfolio.get_available_capital(max_position_pct)

        # Check minimum cash reserve
        total_value = self.portfolio.get_total_value()
        min_cash = total_value * self.min_cash_reserve

        if self.portfolio.cash - available_capital < min_cash:
            available_capital = max(0, self.portfolio.cash - min_cash)

        if available_capital <= 0:
            logger.debug(f"Cannot buy {ticker}: insufficient capital")
            return False

        # Calculate shares to buy
        shares = np.floor(available_capital / price)

        if shares < 1:
            logger.debug(f"Cannot buy {ticker}: cannot afford 1 share")
            return False

        # Get stop loss and take profit from chromosome
        stop_loss_pct = self.risk_params.get('stop_loss_pct')
        take_profit_pct = self.risk_params.get('take_profit_pct')

        # Execute buy
        success = self.portfolio.buy(
            ticker=ticker,
            shares=shares,
            price=price,
            date=date,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct
        )

        return success

    def execute_sell(self, ticker: str, price: float, date: pd.Timestamp,
                    shares: Optional[float] = None) -> bool:
        """
        Execute a sell order

        Args:
            ticker: Stock ticker
            price: Current price
            date: Trade date
            shares: Number of shares to sell (None = all)

        Returns:
            True if trade executed, False otherwise
        """
        return self.portfolio.sell(
            ticker=ticker,
            shares=shares,
            price=price,
            date=date,
            reason='signal'
        )

    def rebalance_portfolio(self, prices: Dict[str, float], date: pd.Timestamp):
        """
        Rebalance portfolio if positions exceed maximum percentage

        Args:
            prices: Current prices
            date: Current date
        """
        total_value = self.portfolio.get_total_value()
        max_position_value = total_value * self.risk_params['max_position_pct']

        for ticker, position in list(self.portfolio.positions.items()):
            if ticker not in prices:
                continue

            price = prices[ticker]
            position.update_price(price)

            # If position exceeds max percentage, trim it
            if position.current_value > max_position_value * 1.2:  # 20% buffer
                excess_value = position.current_value - max_position_value
                shares_to_sell = np.floor(excess_value / price)

                if shares_to_sell >= 1:
                    logger.info(f"Rebalancing: selling {shares_to_sell} shares of {ticker}")
                    self.execute_sell(ticker, price, date, shares_to_sell)

    def get_portfolio_weights(self) -> Dict[str, float]:
        """
        Get current portfolio weights by position

        Returns:
            Dictionary mapping ticker to weight (percentage of total value)
        """
        total_value = self.portfolio.get_total_value()
        if total_value == 0:
            return {}

        weights = {}
        for ticker, position in self.portfolio.positions.items():
            weights[ticker] = (position.current_value / total_value) * 100

        return weights

    def get_risk_metrics(self) -> Dict[str, float]:
        """
        Calculate current risk metrics

        Returns:
            Dictionary of risk metrics
        """
        total_value = self.portfolio.get_total_value()
        positions_value = self.portfolio.get_positions_value()

        metrics = {
            'num_positions': len(self.portfolio.positions),
            'cash_percentage': (self.portfolio.cash / total_value * 100) if total_value > 0 else 0,
            'positions_percentage': (positions_value / total_value * 100) if total_value > 0 else 0,
            'largest_position_pct': 0,
            'avg_position_pct': 0
        }

        if self.portfolio.positions:
            position_values = [pos.current_value for pos in self.portfolio.positions.values()]
            metrics['largest_position_pct'] = (max(position_values) / total_value * 100) if total_value > 0 else 0
            metrics['avg_position_pct'] = (np.mean(position_values) / total_value * 100) if total_value > 0 else 0

        return metrics

    def close_all_positions(self, prices: Dict[str, float], date: pd.Timestamp):
        """
        Close all open positions (for end of backtest)

        Args:
            prices: Current prices
            date: Current date
        """
        for ticker in list(self.portfolio.positions.keys()):
            if ticker in prices:
                logger.info(f"Closing position in {ticker}")
                self.execute_sell(ticker, prices[ticker], date)

    def get_execution_summary(self) -> Dict:
        """
        Get summary of execution statistics

        Returns:
            Dictionary with execution metrics
        """
        trades_df = self.portfolio.get_trades_dataframe()

        if trades_df.empty:
            return {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'unique_tickers': 0,
                'avg_trade_size': 0,
                'total_commission': 0,
                'total_slippage': 0
            }

        buy_trades = trades_df[trades_df['action'] == 'buy']
        sell_trades = trades_df[trades_df['action'] == 'sell']

        return {
            'total_trades': len(trades_df),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'unique_tickers': trades_df['ticker'].nunique(),
            'avg_trade_size': trades_df['total'].mean(),
            'total_commission': trades_df['commission'].sum(),
            'total_slippage': (trades_df['price'] * trades_df['shares'] * trades_df['slippage']).sum()
        }

    def can_execute_buy(self, ticker: str, price: float) -> bool:
        """
        Check if buy order can be executed

        Args:
            ticker: Stock ticker
            price: Current price

        Returns:
            True if buy is possible, False otherwise
        """
        # Check max positions
        if len(self.portfolio.positions) >= self.max_positions:
            return False

        # Check if already have position
        if self.portfolio.has_position(ticker):
            return False

        # Check capital availability
        max_position_pct = self.risk_params['max_position_pct']
        available_capital = self.portfolio.get_available_capital(max_position_pct)

        total_value = self.portfolio.get_total_value()
        min_cash = total_value * self.min_cash_reserve

        if self.portfolio.cash - available_capital < min_cash:
            available_capital = max(0, self.portfolio.cash - min_cash)

        if available_capital <= 0:
            return False

        # Check if can afford at least 1 share
        shares = np.floor(available_capital / price)
        return shares >= 1

    def can_execute_sell(self, ticker: str) -> bool:
        """
        Check if sell order can be executed

        Args:
            ticker: Stock ticker

        Returns:
            True if sell is possible, False otherwise
        """
        return self.portfolio.has_position(ticker)

    def __repr__(self) -> str:
        return (f"TradeExecutor(max_positions={self.max_positions}, "
                f"current_positions={len(self.portfolio.positions)})")
