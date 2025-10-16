"""Check trades from top algorithms"""
import sqlite3
import pandas as pd
import json

# Connect to database
conn = sqlite3.connect('data/cache.db')

# Get top algorithm IDs from validation results
with open('results/validation_results.json', 'r') as f:
    results = json.load(f)

# Sort by validation fitness and get top 5
top_algos = sorted(results, key=lambda x: x['val_fitness'], reverse=True)[:5]
top_ids = [algo['algorithm_id'] for algo in top_algos]

print('Top 5 Algorithms by Validation Fitness:')
print('=' * 80)
for i, algo in enumerate(top_algos[:5], 1):
    val_fitness = algo['val_fitness']
    val_return = algo['val_return']
    val_sharpe = algo['val_sharpe']
    print(f'{i}. Algorithm {algo["algorithm_id"]} - Fitness: {val_fitness:.4f}, Return: {val_return:.2f}%, Sharpe: {val_sharpe:.4f}')

print('\n' + '=' * 80)
print('Trades from Top 5 Algorithms:')
print('=' * 80)

# Get trades for top algorithms
for algo_id in top_ids[:5]:
    query = '''
    SELECT date, stock_ticker, action, quantity, price, portfolio_value_after
    FROM transactions
    WHERE algorithm_id = ?
    ORDER BY date DESC
    LIMIT 10
    '''

    df = pd.read_sql_query(query, conn, params=(algo_id,))

    if not df.empty:
        print(f'\nAlgorithm {algo_id} - Most Recent Trades:')
        print(df.to_string(index=False))
        print(f'Total trades: {len(pd.read_sql_query("SELECT * FROM transactions WHERE algorithm_id = ?", conn, params=(algo_id,)))}')
    else:
        print(f'\nAlgorithm {algo_id} - No trades recorded yet')

conn.close()
