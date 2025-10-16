"""Test installation and verify all dependencies"""

import sys
import os

print("=" * 80)
print("Genetic Trading System - Installation Test")
print("=" * 80)

# Test Python version
print(f"\n1. Python Version: {sys.version}")
if sys.version_info < (3, 9):
    print("   ❌ ERROR: Python 3.9+ required!")
    sys.exit(1)
else:
    print("   ✓ Python version OK")

# Test imports
print("\n2. Testing module imports...")

modules_to_test = [
    ('yfinance', 'Yahoo Finance data'),
    ('pandas', 'Data manipulation'),
    ('numpy', 'Numerical computing'),
    ('yaml', 'Configuration files'),
    ('jinja2', 'Template engine'),
    ('matplotlib', 'Plotting'),
    ('plotly', 'Interactive plots'),
    ('dotenv', 'Environment variables'),
    ('tqdm', 'Progress bars'),
    ('joblib', 'Parallel processing'),
]

failed = []
for module, description in modules_to_test:
    try:
        __import__(module)
        print(f"   ✓ {module:15s} - {description}")
    except ImportError:
        print(f"   ❌ {module:15s} - MISSING!")
        failed.append(module)

if failed:
    print(f"\n   ❌ Missing modules: {', '.join(failed)}")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# Test project structure
print("\n3. Testing project structure...")

required_dirs = [
    'src/data',
    'src/genetic',
    'src/trading',
    'src/analysis',
    'src/blog',
    'config',
    'scripts',
]

for dir_path in required_dirs:
    if os.path.exists(dir_path):
        print(f"   ✓ {dir_path}")
    else:
        print(f"   ❌ {dir_path} - MISSING!")

# Test configuration files
print("\n4. Testing configuration files...")

config_files = [
    'config/config.yaml',
    'config/stocks.yaml',
    'requirements.txt',
]

for file_path in config_files:
    if os.path.exists(file_path):
        print(f"   ✓ {file_path}")
    else:
        print(f"   ❌ {file_path} - MISSING!")

# Test importing custom modules
print("\n5. Testing custom module imports...")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from src.data import DataFetcher, DataCache, DataNormalizer
    print("   ✓ src.data modules")
except ImportError as e:
    print(f"   ❌ src.data modules - {e}")

try:
    from src.genetic import Chromosome, Population, GeneticOperators
    print("   ✓ src.genetic modules")
except ImportError as e:
    print(f"   ❌ src.genetic modules - {e}")

try:
    from src.trading import SignalGenerator, Portfolio, TradeExecutor
    print("   ✓ src.trading modules")
except ImportError as e:
    print(f"   ❌ src.trading modules - {e}")

try:
    from src.analysis import PerformanceMetrics
    print("   ✓ src.analysis modules")
except ImportError as e:
    print(f"   ❌ src.analysis modules - {e}")

try:
    from src.blog import BlogGenerator
    print("   ✓ src.blog modules")
except ImportError as e:
    print(f"   ❌ src.blog modules - {e}")

# Test basic functionality
print("\n6. Testing basic functionality...")

try:
    from src.data import DataCache
    cache = DataCache(':memory:')
    cache.connect()
    cache.create_tables()
    cache.disconnect()
    print("   ✓ Database operations")
except Exception as e:
    print(f"   ❌ Database operations - {e}")

try:
    from src.genetic import Chromosome
    import yaml
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    with open('config/stocks.yaml', 'r') as f:
        stocks = yaml.safe_load(f)

    chromosome = Chromosome(config, stocks['all_stocks'])
    print("   ✓ Chromosome creation")
except Exception as e:
    print(f"   ❌ Chromosome creation - {e}")

# Summary
print("\n" + "=" * 80)
print("Installation Test Complete!")
print("=" * 80)
print("\nNext steps:")
print("  1. Run: python scripts/01_setup_database.py")
print("  2. Run: python scripts/02_download_data.py")
print("  3. Edit config/config.yaml to reduce population/generations for testing")
print("  4. Run: python scripts/03_train_genetic.py")
print("  5. Run: python scripts/05_generate_blog.py")
print("\nSee QUICKSTART.md for detailed instructions.")
print("=" * 80)
