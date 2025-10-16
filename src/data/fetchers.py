"""Data fetchers for various stock data sources"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import time
import os

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetch stock data from multiple sources with fallback support"""

    def __init__(self, primary_source: str = "yahoo", fallback_enabled: bool = True):
        """
        Initialize data fetcher

        Args:
            primary_source: Primary data source ('yahoo', 'alpha_vantage', etc.)
            fallback_enabled: Whether to use fallback sources on failure
        """
        self.primary_source = primary_source
        self.fallback_enabled = fallback_enabled
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.twelve_data_key = os.getenv('TWELVE_DATA_API_KEY')

    def fetch_historical_data(self, ticker: str, start_date: str,
                              end_date: Optional[str] = None,
                              period: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch historical data for a ticker

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to today
            period: Alternative to dates: '1y', '5y', '10y', 'max'

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Try primary source
        try:
            if self.primary_source == "yahoo":
                return self._fetch_yahoo(ticker, start_date, end_date, period)
            elif self.primary_source == "alpha_vantage":
                return self._fetch_alpha_vantage(ticker, start_date, end_date)
            else:
                logger.warning(f"Unknown primary source: {self.primary_source}, using Yahoo")
                return self._fetch_yahoo(ticker, start_date, end_date, period)

        except Exception as e:
            logger.error(f"Error fetching {ticker} from {self.primary_source}: {e}")

            if self.fallback_enabled:
                logger.info(f"Trying fallback sources for {ticker}")
                return self._fetch_with_fallback(ticker, start_date, end_date, period)
            else:
                raise

    def _fetch_yahoo(self, ticker: str, start_date: str, end_date: str,
                     period: Optional[str] = None) -> pd.DataFrame:
        """Fetch data from Yahoo Finance"""
        logger.info(f"Fetching {ticker} from Yahoo Finance")

        try:
            stock = yf.Ticker(ticker)

            if period:
                df = stock.history(period=period)
            else:
                df = stock.history(start=start_date, end=end_date)

            if df.empty:
                raise ValueError(f"No data returned for {ticker}")

            # Standardize column names
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # Keep only required columns
            df = df[['open', 'high', 'low', 'close', 'volume']].copy()

            # Remove timezone info and reset index
            df.index = df.index.tz_localize(None)
            df.reset_index(inplace=True)
            df.rename(columns={'Date': 'date'}, inplace=True)

            logger.info(f"Successfully fetched {len(df)} records for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Yahoo Finance error for {ticker}: {e}")
            raise

    def _fetch_alpha_vantage(self, ticker: str, start_date: str,
                            end_date: str) -> pd.DataFrame:
        """Fetch data from Alpha Vantage"""
        if not self.alpha_vantage_key:
            raise ValueError("Alpha Vantage API key not found")

        logger.info(f"Fetching {ticker} from Alpha Vantage")

        try:
            import requests

            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'TIME_SERIES_DAILY_ADJUSTED',
                'symbol': ticker,
                'outputsize': 'full',
                'apikey': self.alpha_vantage_key
            }

            response = requests.get(url, params=params)
            data = response.json()

            if 'Time Series (Daily)' not in data:
                raise ValueError(f"No data in Alpha Vantage response: {data}")

            # Convert to DataFrame
            time_series = data['Time Series (Daily)']
            df = pd.DataFrame.from_dict(time_series, orient='index')

            df.index = pd.to_datetime(df.index)
            df = df.sort_index()

            # Rename columns
            df = df.rename(columns={
                '1. open': 'open',
                '2. high': 'high',
                '3. low': 'low',
                '4. close': 'close',
                '6. volume': 'volume'
            })

            # Filter date range
            df = df.loc[start_date:end_date]

            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])

            df.reset_index(inplace=True)
            df.rename(columns={'index': 'date'}, inplace=True)

            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

            logger.info(f"Successfully fetched {len(df)} records for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Alpha Vantage error for {ticker}: {e}")
            raise

    def _fetch_with_fallback(self, ticker: str, start_date: str,
                            end_date: str, period: Optional[str] = None) -> pd.DataFrame:
        """Try multiple sources as fallback"""

        sources = ['yahoo']

        if self.alpha_vantage_key:
            sources.append('alpha_vantage')

        for source in sources:
            try:
                logger.info(f"Trying {source} for {ticker}")

                if source == 'yahoo':
                    return self._fetch_yahoo(ticker, start_date, end_date, period)
                elif source == 'alpha_vantage':
                    return self._fetch_alpha_vantage(ticker, start_date, end_date)

            except Exception as e:
                logger.warning(f"Failed to fetch {ticker} from {source}: {e}")
                continue

        raise ValueError(f"All data sources failed for {ticker}")

    def fetch_multiple_tickers(self, tickers: List[str], start_date: str,
                              end_date: Optional[str] = None,
                              period: Optional[str] = None) -> dict:
        """
        Fetch data for multiple tickers

        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            period: Alternative period specification

        Returns:
            Dictionary mapping ticker to DataFrame
        """
        results = {}

        for ticker in tickers:
            try:
                logger.info(f"Fetching data for {ticker}")
                df = self.fetch_historical_data(ticker, start_date, end_date, period)
                results[ticker] = df

                # Be respectful to API rate limits
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to fetch {ticker}: {e}")
                results[ticker] = None

        successful = sum(1 for v in results.values() if v is not None)
        logger.info(f"Successfully fetched {successful}/{len(tickers)} tickers")

        return results

    def validate_data(self, df: pd.DataFrame, ticker: str) -> bool:
        """
        Validate fetched data for quality issues

        Args:
            df: DataFrame with price data
            ticker: Ticker symbol for logging

        Returns:
            True if data is valid
        """
        if df is None or df.empty:
            logger.warning(f"{ticker}: No data")
            return False

        # Check for required columns
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.warning(f"{ticker}: Missing columns: {missing_cols}")
            return False

        # Check for null values
        null_counts = df[required_cols].isnull().sum()
        if null_counts.sum() > 0:
            logger.warning(f"{ticker}: Null values found: {null_counts[null_counts > 0].to_dict()}")

        # Check for data consistency
        # High should be >= Low
        invalid_hl = df[df['high'] < df['low']]
        if len(invalid_hl) > 0:
            logger.warning(f"{ticker}: {len(invalid_hl)} days with high < low")

        # Close should be between high and low
        invalid_close = df[(df['close'] > df['high']) | (df['close'] < df['low'])]
        if len(invalid_close) > 0:
            logger.warning(f"{ticker}: {len(invalid_close)} days with close outside high/low range")

        # Check for duplicate dates
        duplicates = df[df['date'].duplicated()]
        if len(duplicates) > 0:
            logger.warning(f"{ticker}: {len(duplicates)} duplicate dates")
            return False

        logger.info(f"{ticker}: Data validation passed")
        return True
