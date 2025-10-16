"""Data quality validation"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """Validate stock data quality"""

    @staticmethod
    def check_completeness(df: pd.DataFrame, ticker: str) -> Dict[str, any]:
        """Check data completeness"""
        results = {
            'ticker': ticker,
            'total_rows': len(df),
            'missing_values': {},
            'date_gaps': [],
            'is_complete': True
        }

        # Check for missing values
        for col in df.columns:
            missing = df[col].isnull().sum()
            if missing > 0:
                results['missing_values'][col] = missing
                results['is_complete'] = False

        # Check for date gaps (weekdays only)
        if 'date' in df.columns or df.index.name == 'date':
            dates = pd.to_datetime(df['date'] if 'date' in df.columns else df.index)
            date_range = pd.date_range(start=dates.min(), end=dates.max(), freq='B')
            missing_dates = set(date_range) - set(dates)

            if len(missing_dates) > 10:  # Allow some missing days for holidays
                results['date_gaps'] = sorted(list(missing_dates))[:10]  # Show first 10
                results['total_date_gaps'] = len(missing_dates)

        return results

    @staticmethod
    def check_consistency(df: pd.DataFrame, ticker: str) -> Dict[str, any]:
        """Check data consistency (e.g., high >= low)"""
        results = {
            'ticker': ticker,
            'inconsistencies': [],
            'is_consistent': True
        }

        # High should be >= Low
        invalid_hl = df[df['high'] < df['low']]
        if len(invalid_hl) > 0:
            results['inconsistencies'].append({
                'type': 'high < low',
                'count': len(invalid_hl),
                'dates': invalid_hl['date'].tolist()[:5] if 'date' in invalid_hl else []
            })
            results['is_consistent'] = False

        # Close should be between high and low
        invalid_close = df[(df['close'] > df['high']) | (df['close'] < df['low'])]
        if len(invalid_close) > 0:
            results['inconsistencies'].append({
                'type': 'close outside high/low',
                'count': len(invalid_close),
                'dates': invalid_close['date'].tolist()[:5] if 'date' in invalid_close else []
            })
            results['is_consistent'] = False

        # Open should be between high and low
        invalid_open = df[(df['open'] > df['high']) | (df['open'] < df['low'])]
        if len(invalid_open) > 0:
            results['inconsistencies'].append({
                'type': 'open outside high/low',
                'count': len(invalid_open),
                'dates': invalid_open['date'].tolist()[:5] if 'date' in invalid_open else []
            })
            results['is_consistent'] = False

        # Check for negative prices
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                negative = df[df[col] < 0]
                if len(negative) > 0:
                    results['inconsistencies'].append({
                        'type': f'negative {col}',
                        'count': len(negative)
                    })
                    results['is_consistent'] = False

        # Check for zero or negative volume
        if 'volume' in df.columns:
            invalid_volume = df[df['volume'] <= 0]
            if len(invalid_volume) > 0:
                results['inconsistencies'].append({
                    'type': 'zero/negative volume',
                    'count': len(invalid_volume)
                })

        return results

    @staticmethod
    def check_outliers(df: pd.DataFrame, ticker: str,
                      std_threshold: float = 5.0) -> Dict[str, any]:
        """Check for statistical outliers"""
        results = {
            'ticker': ticker,
            'outliers': [],
            'has_outliers': False
        }

        # Calculate daily returns
        df_copy = df.copy()
        df_copy['return'] = df_copy['close'].pct_change()

        # Find outliers (returns beyond N standard deviations)
        mean_return = df_copy['return'].mean()
        std_return = df_copy['return'].std()
        threshold = std_threshold * std_return

        outliers = df_copy[np.abs(df_copy['return'] - mean_return) > threshold]

        if len(outliers) > 0:
            results['has_outliers'] = True
            results['outliers'] = {
                'count': len(outliers),
                'max_positive_return': float(df_copy['return'].max()),
                'max_negative_return': float(df_copy['return'].min()),
                'dates': outliers['date'].tolist()[:5] if 'date' in outliers else []
            }

        return results

    @staticmethod
    def validate_ticker_data(df: pd.DataFrame, ticker: str,
                            check_outliers: bool = False) -> Dict[str, any]:
        """Run all validation checks"""
        logger.info(f"Validating data for {ticker}")

        validation_results = {
            'ticker': ticker,
            'completeness': DataValidator.check_completeness(df, ticker),
            'consistency': DataValidator.check_consistency(df, ticker),
            'is_valid': True
        }

        if check_outliers:
            validation_results['outliers'] = DataValidator.check_outliers(df, ticker)

        # Overall validation status
        if not validation_results['completeness']['is_complete']:
            validation_results['is_valid'] = False
            logger.warning(f"{ticker}: Data completeness issues")

        if not validation_results['consistency']['is_consistent']:
            validation_results['is_valid'] = False
            logger.warning(f"{ticker}: Data consistency issues")

        if validation_results['is_valid']:
            logger.info(f"{ticker}: Data validation passed")
        else:
            logger.warning(f"{ticker}: Data validation failed")

        return validation_results

    @staticmethod
    def validate_multiple_tickers(data_dict: Dict[str, pd.DataFrame],
                                  check_outliers: bool = False) -> Dict[str, Dict]:
        """Validate data for multiple tickers"""
        results = {}

        for ticker, df in data_dict.items():
            if df is not None and not df.empty:
                results[ticker] = DataValidator.validate_ticker_data(
                    df, ticker, check_outliers
                )
            else:
                results[ticker] = {
                    'ticker': ticker,
                    'is_valid': False,
                    'error': 'No data available'
                }

        # Summary
        valid_count = sum(1 for r in results.values() if r.get('is_valid', False))
        logger.info(f"Validation complete: {valid_count}/{len(results)} tickers valid")

        return results
