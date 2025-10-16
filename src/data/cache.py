"""Database cache for stock data"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class DataCache:
    """Manages SQLite cache for stock price data"""

    def __init__(self, db_path: str = "data/cache.db"):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path)
        logger.info(f"Connected to database: {self.db_path}")

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()

        # Historical prices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_prices (
                stock_ticker TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                normalized_open REAL DEFAULT 1.0,
                normalized_high REAL,
                normalized_low REAL,
                normalized_close REAL,
                normalized_volume REAL,
                volume_ma30 REAL,
                source TEXT,
                PRIMARY KEY (stock_ticker, date)
            )
        """)

        # Algorithm chromosomes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS algorithm_chromosomes (
                algorithm_id INTEGER NOT NULL,
                generation INTEGER NOT NULL,
                chromosome_json TEXT,
                fitness_score REAL,
                PRIMARY KEY (algorithm_id, generation)
            )
        """)

        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                algorithm_id INTEGER NOT NULL,
                date DATE NOT NULL,
                stock_ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                portfolio_value_after REAL
            )
        """)

        # Daily portfolio values table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_portfolio_values (
                algorithm_id INTEGER NOT NULL,
                date DATE NOT NULL,
                cash REAL,
                positions_value REAL,
                total_value REAL,
                PRIMARY KEY (algorithm_id, date)
            )
        """)

        # Create indices for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prices_ticker_date
            ON historical_prices(stock_ticker, date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_algo_date
            ON transactions(algorithm_id, date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolio_algo_date
            ON daily_portfolio_values(algorithm_id, date)
        """)

        self.conn.commit()
        logger.info("Database tables created successfully")

    def save_price_data(self, ticker: str, df: pd.DataFrame, source: str = "yahoo"):
        """
        Save price data to database

        Args:
            ticker: Stock ticker symbol
            df: DataFrame with columns: date, open, high, low, close, volume
            source: Data source name
        """
        df = df.copy()
        df['stock_ticker'] = ticker
        df['source'] = source

        # Ensure date is in correct format
        if 'date' not in df.columns:
            df['date'] = df.index

        df['date'] = pd.to_datetime(df['date']).dt.date

        # Select columns to save
        columns = ['stock_ticker', 'date', 'open', 'high', 'low', 'close', 'volume',
                   'normalized_open', 'normalized_high', 'normalized_low',
                   'normalized_close', 'normalized_volume', 'volume_ma30', 'source']

        # Add missing columns with defaults
        for col in columns:
            if col not in df.columns:
                if col == 'normalized_open':
                    df[col] = 1.0
                elif col.startswith('normalized_') or col == 'volume_ma30':
                    df[col] = None
                elif col == 'source':
                    df[col] = source

        # Save to database using INSERT OR REPLACE to handle duplicates
        cursor = self.conn.cursor()

        for _, row in df[columns].iterrows():
            placeholders = ', '.join(['?'] * len(columns))
            cursor.execute(f"""
                INSERT OR REPLACE INTO historical_prices
                ({', '.join(columns)})
                VALUES ({placeholders})
            """, tuple(row[col] for col in columns))

        self.conn.commit()
        logger.info(f"Saved {len(df)} records for {ticker} from {source}")

    def get_price_data(self, ticker: str, start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieve price data from database

        Args:
            ticker: Stock ticker symbol
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            DataFrame with price data
        """
        query = "SELECT * FROM historical_prices WHERE stock_ticker = ?"
        params = [ticker]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date"

        df = pd.read_sql_query(query, self.conn, params=params)

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

        return df

    def get_all_tickers(self) -> List[str]:
        """Get list of all tickers in database"""
        query = "SELECT DISTINCT stock_ticker FROM historical_prices ORDER BY stock_ticker"
        cursor = self.conn.cursor()
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def get_date_range(self, ticker: str) -> tuple:
        """
        Get min and max dates for a ticker

        Returns:
            Tuple of (min_date, max_date)
        """
        query = """
            SELECT MIN(date), MAX(date)
            FROM historical_prices
            WHERE stock_ticker = ?
        """
        cursor = self.conn.cursor()
        cursor.execute(query, (ticker,))
        result = cursor.fetchone()
        return result if result else (None, None)

    def save_transaction(self, algorithm_id: int, date: str, ticker: str,
                        action: str, quantity: int, price: float,
                        portfolio_value: float):
        """Save a trading transaction"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO transactions
            (algorithm_id, date, stock_ticker, action, quantity, price, portfolio_value_after)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (algorithm_id, date, ticker, action, quantity, price, portfolio_value))
        self.conn.commit()

    def save_portfolio_value(self, algorithm_id: int, date: str,
                            cash: float, positions_value: float, total_value: float):
        """Save daily portfolio value"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO daily_portfolio_values
            (algorithm_id, date, cash, positions_value, total_value)
            VALUES (?, ?, ?, ?, ?)
        """, (algorithm_id, date, cash, positions_value, total_value))
        self.conn.commit()

    def save_chromosome(self, algorithm_id: int, generation: int,
                       chromosome_json: str, fitness_score: float):
        """Save algorithm chromosome data"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO algorithm_chromosomes
            (algorithm_id, generation, chromosome_json, fitness_score)
            VALUES (?, ?, ?, ?)
        """, (algorithm_id, generation, chromosome_json, fitness_score))
        self.conn.commit()

    def get_portfolio_history(self, algorithm_id: int) -> pd.DataFrame:
        """Get portfolio value history for an algorithm"""
        query = """
            SELECT * FROM daily_portfolio_values
            WHERE algorithm_id = ?
            ORDER BY date
        """
        df = pd.read_sql_query(query, self.conn, params=(algorithm_id,))
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df

    def get_transactions(self, algorithm_id: int,
                        start_date: Optional[str] = None) -> pd.DataFrame:
        """Get transaction history for an algorithm"""
        query = "SELECT * FROM transactions WHERE algorithm_id = ?"
        params = [algorithm_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        query += " ORDER BY date, transaction_id"

        df = pd.read_sql_query(query, self.conn, params=params)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df
