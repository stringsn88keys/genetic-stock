# Genetic Algorithm Stock Trading System

A distributed genetic algorithm system that evolves 1000 independent trading strategies, each managing a $1000 portfolio and making daily buy/sell decisions based on normalized historical stock data.

## Features

- **1000 Independent Algorithms**: Population of trading strategies evolved through genetic algorithms
- **Multi-Source Data**: Fetches from Yahoo Finance, Alpha Vantage, and other free sources
- **Normalized Data**: Price and volume normalization for algorithm independence
- **Complete Backtesting**: Full historical simulation with realistic transaction costs
- **Risk Management**: Stop loss, take profit, position sizing
- **Performance Tracking**: Sharpe ratio, Sortino ratio, max drawdown, and more
- **Automated Blog**: Static HTML blog with performance dashboards

## Project Structure

```
genetic-stock/
├── src/                          # Source code
│   ├── data/                    # Data acquisition and processing
│   │   ├── fetchers.py         # Multi-source data retrieval
│   │   ├── cache.py            # SQLite database management
│   │   ├── normalizer.py       # Data normalization
│   │   └── validators.py       # Data quality checks
│   ├── genetic/                 # Genetic algorithm framework
│   │   ├── chromosome.py       # Trading algorithm genes
│   │   ├── population.py       # Population management
│   │   ├── operators.py        # Selection, crossover, mutation
│   │   ├── fitness.py          # Fitness evaluation
│   │   └── evolution.py        # Evolution engine
│   ├── trading/                 # Trading engine
│   │   ├── signals.py          # Signal generation
│   │   ├── portfolio.py        # Portfolio management
│   │   ├── executor.py         # Trade execution
│   │   └── backtest.py         # Backtesting engine
│   ├── analysis/                # Performance analysis
│   │   └── metrics.py          # Metrics calculation
│   └── blog/                    # Blog generation
│       └── generator.py        # Static HTML generator
├── scripts/                      # Executable scripts
│   ├── 01_setup_database.py    # Initialize database
│   ├── 02_download_data.py     # Download historical data
│   ├── 03_train_genetic.py     # Train algorithms
│   ├── 04_run_daily.py         # Daily trading execution
│   └── 05_generate_blog.py     # Generate blog
├── config/                       # Configuration files
│   ├── config.yaml             # System configuration
│   └── stocks.yaml             # Stock universe
├── data/                         # Data storage
│   └── cache.db                # SQLite database
├── results/                      # Training results
├── blog/                         # Generated blog
└── logs/                         # Log files
```

## Installation

### Prerequisites

- Python 3.9+
- pip
- Virtual environment (recommended)

### Setup

```bash
# Clone or navigate to project directory
cd genetic-stock

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (optional - for additional data sources)
cp .env.example .env
# Edit .env to add API keys if you have them
```

### Configuration

Edit `config/stocks.yaml` to customize your stock universe:

```yaml
all_stocks:
  - AAPL
  - MSFT
  - GOOGL
  # Add more stocks...
```

Edit `config/config.yaml` to adjust parameters:

```yaml
population:
  size: 1000              # Number of algorithms
  initial_capital: 1000   # Starting capital per algorithm

evolution:
  generations: 100        # Number of generations to evolve

data:
  historical_years: 10    # Years of historical data
```

## Usage

### Step 1: Setup Database

```bash
python scripts/01_setup_database.py
```

Creates the SQLite database with required tables.

### Step 2: Download Historical Data

```bash
python scripts/02_download_data.py
```

Downloads and normalizes historical stock data. This may take 10-30 minutes depending on the number of stocks.

### Step 3: Train Genetic Algorithms

```bash
python scripts/03_train_genetic.py
```

Trains 1000 trading algorithms through evolution. This is the most time-intensive step:
- 1000 algorithms × 100 generations × backtesting
- Estimated time: 12-48 hours on a 16-core machine
- Progress is logged and saved every 10 generations

**Training Output:**
- `results/generations/` - Population snapshots
- `results/validation_results.json` - Top performers with validation scores
- `C:\\projects\\logs\\training.log` - Detailed training log

### Step 4: Generate Blog

```bash
python scripts/05_generate_blog.py
```

Generates static HTML blog with:
- Index page with top 50 performers
- Individual algorithm pages with charts
- Complete performance metrics

Open `blog/index.html` in your browser to view results.

### Step 5: Daily Operations (Optional)

```bash
python scripts/04_run_daily.py
```

For live trading simulation:
- Fetches latest market data
- Executes trades for all algorithms
- Updates database with transactions

Run this daily after market close (or set up as a cron job).

## Algorithm Chromosome Structure

Each trading algorithm is defined by a chromosome containing:

### Weights
- Feature weights (close, high, low, volume)
- Momentum indicators (5-day, 20-day)
- Volume trends

### Thresholds
- Buy threshold
- Sell threshold
- Hold range

### Risk Parameters
- Maximum position size (% of portfolio)
- Stop loss percentage
- Take profit percentage

### Lookback Windows
- Short-term (2-10 days)
- Medium-term (10-50 days)
- Long-term (50-200 days)

## Performance Metrics

The system tracks comprehensive performance metrics:

- **Total Return**: (Final - Initial) / Initial
- **Annualized Return**: Geometric mean return per year
- **Sharpe Ratio**: Risk-adjusted return
- **Sortino Ratio**: Downside risk-adjusted return
- **Maximum Drawdown**: Worst peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profits / Gross losses
- **Calmar Ratio**: Annual return / Max drawdown

## Fitness Function

Algorithms are evaluated using a weighted fitness function:

```
Fitness = 0.40 × Total Return
        + 0.25 × Sharpe Ratio
        + 0.15 × Win Rate
        - 0.10 × Max Drawdown
        - 0.05 × Transaction Costs
        - 0.05 × Inactivity Penalty
```

## Data Normalization

### Price Normalization
All prices are normalized relative to opening price:
```
Normalized_Open = 1.0
Normalized_High = High / Open
Normalized_Low = Low / Open
Normalized_Close = Close / Open
```

### Volume Normalization
Volume is normalized relative to 30-day moving average:
```
Normalized_Volume = Current_Volume / 30-day_MA
```

## Genetic Operators

### Selection
- Tournament selection (tournament size: 5)
- Elitism: Top 10% survive unchanged

### Crossover
- Two-point crossover for weight arrays
- Uniform crossover for discrete parameters
- Probability: 80%

### Mutation
- Gaussian mutation for continuous weights (σ = 0.1)
- Random reset for discrete parameters
- Probability: 15%

## Transaction Costs

- **Commission**: $0 (assuming commission-free trading)
- **Slippage**: 0.1% per trade
- **Market Impact**: Negligible for $1000 positions

## Risk Considerations

### Overfitting
- Strict train/validate/test splits (70%/20%/10%)
- Diversity maintenance in population
- Regularization in fitness function

### Look-Ahead Bias
- Ensured data at day T doesn't include day T+1
- Realistic data availability delays

### Market Regime Changes
- Test across multiple market cycles
- Past performance doesn't guarantee future results

## Disclaimer

**This is an educational project for research purposes only.**

- Past performance does not guarantee future results
- This is not financial advice
- Do not trade real money based on these results
- Market conditions change and historical patterns may not persist
- Always consult with a qualified financial advisor

## Example Results

After training, you can expect:

```
Generation 100/100:
  Best Fitness: 1.234
  Mean Fitness: 0.456
  Diversity: 2.34

Top Performer:
  Total Return: 45.2%
  Sharpe Ratio: 1.82
  Max Drawdown: -12.3%
  Win Rate: 58.4%
  Number of Trades: 127
```

## Troubleshooting

### Out of Memory
- Reduce population size in `config/config.yaml`
- Reduce number of stocks in `config/stocks.yaml`
- Run on a machine with more RAM

### Slow Training
- Enable parallel processing in config
- Reduce number of generations
- Use fewer stocks for faster iteration
- Consider using a more powerful machine

### No Data Downloaded
- Check internet connection
- Verify stock tickers are correct
- Check API rate limits\n- Review logs in `C:\\projects\\logs\\` directory

### Import Errors
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`
- Check Python version (3.9+ required)

## Advanced Usage

### Custom Stock Universe

Edit `config/stocks.yaml` to add more stocks or create sector-specific lists.

### Hyperparameter Tuning

Edit `config/config.yaml` to adjust:
- Population size
- Mutation rates
- Fitness function weights
- Risk parameters

### Custom Features

Add technical indicators in `src/data/normalizer.py`:
- RSI, MACD, Bollinger Bands
- Custom momentum indicators
- Fundamental data

## Contributing

Contributions welcome! Areas for improvement:
- Additional data sources
- More technical indicators
- Enhanced visualization
- Portfolio-level optimization
- Multi-timeframe analysis

## License

MIT License - See LICENSE file for details

## Citation

If you use this project in your research, please cite:

```
Genetic Algorithm Stock Trading System
https://github.com/yourusername/genetic-stock
```

## Support

For issues or questions:
- Check documentation
- Review logs in `C:\\projects\\logs\\` directory
- Open an issue on GitHub

## Acknowledgments

- Data: Yahoo Finance, Alpha Vantage
- Libraries: pandas, numpy, yfinance, DEAP
- Inspired by genetic algorithm research in algorithmic trading

---

**Remember**: This is for educational purposes. Never risk money you can't afford to lose, and always do your own research before making investment decisions.
