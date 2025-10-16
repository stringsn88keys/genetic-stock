"""Portfolio management for trading simulation"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from dataclasses import dataclass
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a stock position"""
    ticker: str
    shares: float
    entry_price: float
    entry_date: pd.Timestamp
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    @property
    def cost_basis(self) -> float:
        """Total cost of position"""
        return self.shares * self.entry_price

    @property
    def current_value(self) -> float:
        """Current market value"""
        return self.shares * self.current_price

    @property
    def profit_loss(self) -> float:
        """Unrealized profit/loss"""
        return self.current_value - self.cost_basis

    @property
    def profit_loss_pct(self) -> float:
        """Unrealized profit/loss percentage"""
        if self.cost_basis == 0:
            return 0.0
        return (self.profit_loss / self.cost_basis) * 100

    def update_price(self, price: float):
        """Update current price"""
        self.current_price = price

    def should_stop_loss(self) -> bool:
        """Check if stop loss should trigger"""
        if self.stop_loss is None:
            return False
        return self.current_price <= self.stop_loss

    def should_take_profit(self) -> bool:
        """Check if take profit should trigger"""
        if self.take_profit is None:
            return False
        return self.current_price >= self.take_profit


@dataclass
class Trade:
    """Represents a completed trade"""
    ticker: str
    action: str  # 'buy' or 'sell'
    shares: float
    price: float
    date: pd.Timestamp
    commission: float = 0.0
    slippage: float = 0.0

    @property
    def total_cost(self) -> float:
        """Total cost including fees"""
        base_cost = self.shares * self.price
        return base_cost + self.commission + (base_cost * self.slippage)

    @property
    def total_proceeds(self) -> float:
        """Total proceeds after fees (for sells)"""
        base_proceeds = self.shares * self.price
        return base_proceeds - self.commission - (base_proceeds * self.slippage)


class Portfolio:
    """Portfolio management class for backtesting"""

    def __init__(self, initial_capital: float = 10000.0,
                 commission: float = 0.0,
                 slippage: float = 0.001):
        """
        Initialize portfolio

        Args:
            initial_capital: Starting cash amount
            commission: Commission per trade (flat fee)
            slippage: Slippage as percentage (e.g., 0.001 = 0.1%)
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission = commission
        self.slippage = slippage

        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self.value_history: List[Dict] = []

        logger.debug(f"Initialized portfolio with ${initial_capital:,.2f}")

    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position for a ticker"""
        return self.positions.get(ticker)

    def has_position(self, ticker: str) -> bool:
        """Check if portfolio has position in ticker"""
        return ticker in self.positions

    def get_total_value(self) -> float:
        """Calculate total portfolio value (cash + positions)"""
        positions_value = sum(pos.current_value for pos in self.positions.values())
        return self.cash + positions_value

    def get_positions_value(self) -> float:
        """Get total value of all positions"""
        return sum(pos.current_value for pos in self.positions.values())

    def get_available_capital(self, max_position_pct: float = 1.0) -> float:
        """
        Get available capital for new positions

        Args:
            max_position_pct: Maximum percentage of portfolio for single position

        Returns:
            Amount available to invest
        """
        total_value = self.get_total_value()
        max_position_value = total_value * max_position_pct
        return min(self.cash, max_position_value)

    def buy(self, ticker: str, shares: float, price: float,
            date: pd.Timestamp, stop_loss_pct: Optional[float] = None,
            take_profit_pct: Optional[float] = None) -> bool:
        """
        Buy shares of a stock

        Args:
            ticker: Stock ticker
            shares: Number of shares to buy
            price: Price per share
            date: Trade date
            stop_loss_pct: Stop loss percentage (e.g., -0.08 for -8%)
            take_profit_pct: Take profit percentage (e.g., 0.15 for +15%)

        Returns:
            True if trade executed, False otherwise
        """
        # Calculate total cost with slippage
        base_cost = shares * price
        adjusted_price = price * (1 + self.slippage)
        total_cost = shares * adjusted_price + self.commission

        # Check if we have enough cash
        if total_cost > self.cash:
            logger.warning(f"Insufficient cash to buy {shares} shares of {ticker}")
            return False

        # Execute trade
        self.cash -= total_cost

        # Calculate stop loss and take profit prices
        stop_loss_price = None
        take_profit_price = None

        if stop_loss_pct is not None:
            stop_loss_price = price * (1 + stop_loss_pct)

        if take_profit_pct is not None:
            take_profit_price = price * (1 + take_profit_pct)

        # Add or update position
        if ticker in self.positions:
            # Average down/up
            old_pos = self.positions[ticker]
            total_shares = old_pos.shares + shares
            avg_price = ((old_pos.shares * old_pos.entry_price) +
                        (shares * adjusted_price)) / total_shares

            self.positions[ticker] = Position(
                ticker=ticker,
                shares=total_shares,
                entry_price=avg_price,
                entry_date=old_pos.entry_date,
                current_price=price,
                stop_loss=stop_loss_price,
                take_profit=take_profit_price
            )
        else:
            self.positions[ticker] = Position(
                ticker=ticker,
                shares=shares,
                entry_price=adjusted_price,
                entry_date=date,
                current_price=price,
                stop_loss=stop_loss_price,
                take_profit=take_profit_price
            )

        # Record trade
        trade = Trade(
            ticker=ticker,
            action='buy',
            shares=shares,
            price=price,
            date=date,
            commission=self.commission,
            slippage=self.slippage
        )
        self.trade_history.append(trade)

        logger.debug(f"BUY {shares:.2f} shares of {ticker} @ ${price:.2f} on {date.date()}")
        return True

    def sell(self, ticker: str, shares: Optional[float], price: float,
             date: pd.Timestamp, reason: str = 'signal') -> bool:
        """
        Sell shares of a stock

        Args:
            ticker: Stock ticker
            shares: Number of shares to sell (None = sell all)
            price: Price per share
            date: Trade date
            reason: Reason for sale ('signal', 'stop_loss', 'take_profit')

        Returns:
            True if trade executed, False otherwise
        """
        # Check if we have position
        if ticker not in self.positions:
            logger.warning(f"No position in {ticker} to sell")
            return False

        position = self.positions[ticker]

        # Determine shares to sell
        if shares is None:
            shares = position.shares
        else:
            shares = min(shares, position.shares)

        # Calculate proceeds with slippage
        adjusted_price = price * (1 - self.slippage)
        total_proceeds = shares * adjusted_price - self.commission

        # Execute trade
        self.cash += total_proceeds

        # Update or remove position
        if shares >= position.shares:
            # Selling entire position
            del self.positions[ticker]
            logger.debug(f"SELL ALL {shares:.2f} shares of {ticker} @ ${price:.2f} "
                        f"({reason}) on {date.date()}")
        else:
            # Partial sell
            position.shares -= shares
            logger.debug(f"SELL {shares:.2f} shares of {ticker} @ ${price:.2f} "
                        f"({reason}) on {date.date()}")

        # Record trade
        trade = Trade(
            ticker=ticker,
            action='sell',
            shares=shares,
            price=price,
            date=date,
            commission=self.commission,
            slippage=self.slippage
        )
        self.trade_history.append(trade)

        return True

    def update_prices(self, prices: Dict[str, float]):
        """
        Update current prices for all positions

        Args:
            prices: Dictionary mapping ticker to current price
        """
        for ticker, position in self.positions.items():
            if ticker in prices:
                position.update_price(prices[ticker])

    def check_risk_triggers(self, date: pd.Timestamp, prices: Dict[str, float]) -> List[str]:
        """
        Check for stop loss and take profit triggers

        Args:
            date: Current date
            prices: Current prices for all tickers

        Returns:
            List of tickers that triggered stops
        """
        triggered = []

        for ticker, position in list(self.positions.items()):
            if ticker not in prices:
                continue

            price = prices[ticker]
            position.update_price(price)

            # Check stop loss
            if position.should_stop_loss():
                logger.info(f"Stop loss triggered for {ticker} at ${price:.2f}")
                if self.sell(ticker, None, price, date, reason='stop_loss'):
                    triggered.append(ticker)

            # Check take profit
            elif position.should_take_profit():
                logger.info(f"Take profit triggered for {ticker} at ${price:.2f}")
                if self.sell(ticker, None, price, date, reason='take_profit'):
                    triggered.append(ticker)

        return triggered

    def record_value(self, date: pd.Timestamp):
        """
        Record portfolio value for this date

        Args:
            date: Date to record
        """
        total_value = self.get_total_value()
        positions_value = self.get_positions_value()

        self.value_history.append({
            'date': date,
            'total_value': total_value,
            'cash': self.cash,
            'positions_value': positions_value,
            'num_positions': len(self.positions)
        })

    def get_value_dataframe(self) -> pd.DataFrame:
        """
        Get portfolio value history as DataFrame

        Returns:
            DataFrame with value history
        """
        if not self.value_history:
            return pd.DataFrame()

        df = pd.DataFrame(self.value_history)
        df.set_index('date', inplace=True)
        return df

    def get_trades_dataframe(self) -> pd.DataFrame:
        """
        Get trade history as DataFrame

        Returns:
            DataFrame with all trades
        """
        if not self.trade_history:
            return pd.DataFrame()

        trades_data = []
        for trade in self.trade_history:
            trades_data.append({
                'date': trade.date,
                'ticker': trade.ticker,
                'action': trade.action,
                'shares': trade.shares,
                'price': trade.price,
                'commission': trade.commission,
                'slippage': trade.slippage,
                'total': trade.total_cost if trade.action == 'buy' else trade.total_proceeds
            })

        df = pd.DataFrame(trades_data)
        return df

    def get_return(self) -> float:
        """Calculate total return percentage"""
        if self.initial_capital == 0:
            return 0.0
        return ((self.get_total_value() - self.initial_capital) /
                self.initial_capital) * 100

    def get_num_trades(self) -> int:
        """Get total number of trades"""
        return len(self.trade_history)

    def get_num_winning_trades(self) -> int:
        """Get number of profitable trades"""
        winning = 0
        buy_trades = {}

        for trade in self.trade_history:
            if trade.action == 'buy':
                if trade.ticker not in buy_trades:
                    buy_trades[trade.ticker] = []
                buy_trades[trade.ticker].append(trade)
            elif trade.action == 'sell':
                if trade.ticker in buy_trades and buy_trades[trade.ticker]:
                    buy_trade = buy_trades[trade.ticker].pop(0)
                    if trade.price > buy_trade.price:
                        winning += 1

        return winning

    def reset(self):
        """Reset portfolio to initial state"""
        self.cash = self.initial_capital
        self.positions.clear()
        self.trade_history.clear()
        self.value_history.clear()
        logger.debug("Portfolio reset")

    def __repr__(self) -> str:
        return (f"Portfolio(value=${self.get_total_value():,.2f}, "
                f"cash=${self.cash:,.2f}, positions={len(self.positions)})")
