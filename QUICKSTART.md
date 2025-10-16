# Quick Start Guide

Get up and running in 5 steps!

## 1. Install Dependencies

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install packages
pip install -r requirements.txt
```

## 2. Setup Database

```bash
python scripts/01_setup_database.py
```

Expected output:
```
INFO - Setting up database...
INFO - Database tables created successfully
INFO - Database setup complete!
```

## 3. Download Data

```bash
python scripts/02_download_data.py
```

This will download 10 years of historical data for 24 stocks. Takes 10-20 minutes.

Expected output:
```
INFO - Downloading 24 stocks...
INFO - Fetching AAPL from Yahoo Finance
INFO - Successfully fetched 2517 records for AAPL
...
INFO - Download complete: 24/24 stocks cached
```

## 4. Train Algorithms (Optional - Takes Time!)

```bash
python scripts/03_train_genetic.py
```

**Warning**: This trains 1000 algorithms for 100 generations. Estimated time: 12-48 hours!

For testing, edit `config/config.yaml` first:
```yaml
population:
  size: 10          # Reduce from 1000 to 10
evolution:
  generations: 5    # Reduce from 100 to 5
```

Then run training. With reduced settings, it should complete in 30-60 minutes.

## 5. Generate Blog

```bash
python scripts/05_generate_blog.py
```

Then open `blog/index.html` in your browser!

## Configuration Tips

### Start Small
For your first run, use a small configuration:

**config/config.yaml:**
```yaml
population:
  size: 10
evolution:
  generations: 5
```

**config/stocks.yaml:**
```yaml
all_stocks:
  - AAPL
  - MSFT
  - GOOGL
  # Just 3-5 stocks for testing
```

### Scale Up
Once you verify everything works, scale up:

```yaml
population:
  size: 100          # Then 500, then 1000
evolution:
  generations: 20    # Then 50, then 100
```

## Expected Timeline

| Configuration | Stocks | Population | Generations | Est. Time |
|--------------|--------|------------|-------------|-----------|
| Testing | 5 | 10 | 5 | 30 min |
| Small | 10 | 50 | 20 | 4 hours |
| Medium | 20 | 200 | 50 | 18 hours |
| Full | 24 | 1000 | 100 | 48 hours |

## Common Issues

### "No module named 'src'"
- Make sure you're running scripts from the project root directory
- The scripts add the parent directory to Python path automatically

### "No data downloaded"
- Check your internet connection
- Yahoo Finance is the default and requires no API key
- Check logs in `C:\\projects\\logs\\` directory

### "Out of memory"
- Reduce population size
- Reduce number of stocks
- Close other applications

## Next Steps

1. **Analyze Results**: Look at `results/validation_results.json`
2. **View Blog**: Open `blog/index.html` to see performance dashboards
3. **Tune Parameters**: Edit `config/config.yaml` to optimize
4. **Add Stocks**: Edit `config/stocks.yaml` to expand universe
5. **Daily Trading**: Run `scripts/04_run_daily.py` for live simulation

## Quick Commands Reference

```bash
# Full workflow
python scripts/01_setup_database.py
python scripts/02_download_data.py
python scripts/03_train_genetic.py
python scripts/05_generate_blog.py

# Daily operations (after training)
python scripts/04_run_daily.py
python scripts/05_generate_blog.py
```

## Help

- Read `README.md` for detailed documentation
- Check `C:\\projects\\logs\\` directory for error messages
- Review `config/config.yaml` for all available options

Happy trading (for educational purposes only)!
