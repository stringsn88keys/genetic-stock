"""Static blog generation for genetic trading system"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime
import logging
from pathlib import Path
import pandas as pd
import numpy as np

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    logging.warning("Jinja2 not available. Install with: pip install jinja2")

logger = logging.getLogger(__name__)


class BlogGenerator:
    """Generate static HTML blog from genetic algorithm results"""

    def __init__(self, templates_dir: str, output_dir: str, assets_dir: Optional[str] = None):
        """
        Initialize blog generator

        Args:
            templates_dir: Directory containing Jinja2 templates
            output_dir: Directory to output generated HTML
            assets_dir: Directory containing CSS/JS assets
        """
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.assets_dir = Path(assets_dir) if assets_dir else None

        # Create output directory if needed
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        if JINJA2_AVAILABLE:
            self.env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=select_autoescape(['html', 'xml'])
            )
            self._register_filters()
        else:
            self.env = None
            logger.error("Jinja2 not available. Cannot generate blog.")

        logger.info(f"BlogGenerator initialized: {self.output_dir}")

    def _register_filters(self):
        """Register custom Jinja2 filters"""
        if not self.env:
            return

        # Number formatting filters
        self.env.filters['format_number'] = lambda x: f"{x:,.2f}"
        self.env.filters['format_percent'] = lambda x: f"{x:.2f}%"
        self.env.filters['format_currency'] = lambda x: f"${x:,.2f}"
        self.env.filters['format_date'] = lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)
        self.env.filters['format_datetime'] = lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if hasattr(x, 'strftime') else str(x)

    def generate_index(self, population_results: List[Dict],
                      generation: int,
                      metadata: Optional[Dict] = None) -> str:
        """
        Generate index page with top performers

        Args:
            population_results: List of backtest results for all chromosomes
            generation: Current generation number
            metadata: Optional metadata (run info, config, etc.)

        Returns:
            Path to generated HTML file
        """
        if not self.env:
            logger.error("Cannot generate index: Jinja2 not available")
            return ""

        # Sort by total return
        sorted_results = sorted(
            population_results,
            key=lambda x: x.get('total_return', 0),
            reverse=True
        )

        # Get top performers
        top_performers = sorted_results[:50]

        # Calculate statistics
        returns = [r.get('total_return', 0) for r in population_results]
        sharpes = [r.get('sharpe_ratio', 0) for r in population_results]

        stats = {
            'generation': generation,
            'population_size': len(population_results),
            'avg_return': np.mean(returns),
            'median_return': np.median(returns),
            'best_return': max(returns) if returns else 0,
            'worst_return': min(returns) if returns else 0,
            'avg_sharpe': np.mean(sharpes),
            'best_sharpe': max(sharpes) if sharpes else 0,
            'timestamp': datetime.now()
        }

        # Render template
        try:
            template = self.env.get_template('index.html')
        except Exception as e:
            logger.warning(f"Template 'index.html' not found: {e}. Using basic template.")
            template = self._create_basic_index_template()

        html = template.render(
            top_performers=top_performers,
            stats=stats,
            metadata=metadata or {},
            generation=generation
        )

        # Write to file
        output_file = self.output_dir / 'index.html'
        output_file.write_text(html, encoding='utf-8')

        logger.info(f"Generated index page: {output_file}")
        return str(output_file)

    def generate_chromosome_page(self, chromosome_id: int,
                                 backtest_results: Dict,
                                 rank: Optional[int] = None) -> str:
        """
        Generate detailed page for a specific chromosome

        Args:
            chromosome_id: Chromosome identifier
            backtest_results: Backtest results for this chromosome
            rank: Rank in population (optional)

        Returns:
            Path to generated HTML file
        """
        if not self.env:
            logger.error("Cannot generate chromosome page: Jinja2 not available")
            return ""

        # Get chromosome genes
        chromosome = backtest_results.get('chromosome', {})

        # Get trades
        trades_df = backtest_results.get('trades', pd.DataFrame())
        trades_list = []

        if not trades_df.empty:
            trades_list = trades_df.to_dict('records')

        # Get value history
        value_df = backtest_results.get('value_history', pd.DataFrame())
        value_history = []

        if not value_df.empty:
            value_history = value_df.reset_index().to_dict('records')

        # Render template
        try:
            template = self.env.get_template('chromosome.html')
        except Exception as e:
            logger.warning(f"Template 'chromosome.html' not found: {e}. Using basic template.")
            template = self._create_basic_chromosome_template()

        html = template.render(
            chromosome_id=chromosome_id,
            rank=rank,
            results=backtest_results,
            chromosome=chromosome,
            trades=trades_list,
            value_history=value_history,
            timestamp=datetime.now()
        )

        # Write to file
        output_file = self.output_dir / f'chromosome_{chromosome_id}.html'
        output_file.write_text(html, encoding='utf-8')

        logger.debug(f"Generated chromosome page: {output_file}")
        return str(output_file)

    def generate_generation_summary(self, generation: int,
                                   population_results: List[Dict],
                                   evolution_stats: Optional[Dict] = None) -> str:
        """
        Generate summary page for a generation

        Args:
            generation: Generation number
            population_results: Results for all chromosomes in generation
            evolution_stats: Evolution statistics (diversity, convergence, etc.)

        Returns:
            Path to generated HTML file
        """
        if not self.env:
            logger.error("Cannot generate generation summary: Jinja2 not available")
            return ""

        # Calculate generation statistics
        returns = [r.get('total_return', 0) for r in population_results]
        sharpes = [r.get('sharpe_ratio', 0) for r in population_results]
        max_dds = [r.get('max_drawdown', 0) for r in population_results]
        num_trades = [r.get('num_trades', 0) for r in population_results]

        stats = {
            'generation': generation,
            'population_size': len(population_results),
            'returns': {
                'mean': np.mean(returns),
                'median': np.median(returns),
                'std': np.std(returns),
                'min': min(returns),
                'max': max(returns),
                'q25': np.percentile(returns, 25),
                'q75': np.percentile(returns, 75)
            },
            'sharpe': {
                'mean': np.mean(sharpes),
                'median': np.median(sharpes),
                'std': np.std(sharpes),
                'min': min(sharpes),
                'max': max(sharpes)
            },
            'max_drawdown': {
                'mean': np.mean(max_dds),
                'median': np.median(max_dds),
                'worst': min(max_dds)
            },
            'trades': {
                'mean': np.mean(num_trades),
                'median': np.median(num_trades),
                'min': min(num_trades),
                'max': max(num_trades)
            }
        }

        # Top 10 performers
        sorted_results = sorted(
            population_results,
            key=lambda x: x.get('total_return', 0),
            reverse=True
        )
        top_10 = sorted_results[:10]

        # Render template
        try:
            template = self.env.get_template('generation.html')
        except Exception as e:
            logger.warning(f"Template 'generation.html' not found: {e}. Using basic template.")
            template = self._create_basic_generation_template()

        html = template.render(
            generation=generation,
            stats=stats,
            top_performers=top_10,
            evolution_stats=evolution_stats or {},
            timestamp=datetime.now()
        )

        # Write to file
        output_file = self.output_dir / f'generation_{generation}.html'
        output_file.write_text(html, encoding='utf-8')

        logger.info(f"Generated generation summary: {output_file}")
        return str(output_file)

    def generate_all_pages(self, population_results: List[Dict],
                          generation: int,
                          metadata: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate all blog pages

        Args:
            population_results: Results for all chromosomes
            generation: Current generation number
            metadata: Optional metadata

        Returns:
            Dictionary mapping page type to file path
        """
        generated_files = {}

        # Generate index
        generated_files['index'] = self.generate_index(
            population_results, generation, metadata
        )

        # Generate generation summary
        generated_files['generation'] = self.generate_generation_summary(
            generation, population_results
        )

        # Generate top 50 chromosome pages
        sorted_results = sorted(
            population_results,
            key=lambda x: x.get('total_return', 0),
            reverse=True
        )

        for rank, result in enumerate(sorted_results[:50], start=1):
            chromosome_id = rank  # Use rank as ID
            page_path = self.generate_chromosome_page(
                chromosome_id, result, rank
            )
            generated_files[f'chromosome_{chromosome_id}'] = page_path

        logger.info(f"Generated {len(generated_files)} pages")
        return generated_files

    def save_results_json(self, population_results: List[Dict],
                         generation: int,
                         filename: str = 'results.json') -> str:
        """
        Save results as JSON file

        Args:
            population_results: Results to save
            generation: Generation number
            filename: Output filename

        Returns:
            Path to saved file
        """
        output_file = self.output_dir / filename

        # Prepare data (remove non-serializable objects)
        serializable_results = []

        for result in population_results:
            clean_result = result.copy()

            # Remove DataFrames
            if 'value_history' in clean_result:
                del clean_result['value_history']
            if 'trades' in clean_result:
                del clean_result['trades']

            # Convert timestamps
            for key in ['start_date', 'end_date']:
                if key in clean_result and hasattr(clean_result[key], 'isoformat'):
                    clean_result[key] = clean_result[key].isoformat()

            serializable_results.append(clean_result)

        data = {
            'generation': generation,
            'timestamp': datetime.now().isoformat(),
            'results': serializable_results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved results JSON: {output_file}")
        return str(output_file)

    def _create_basic_index_template(self):
        """Create basic index template if none exists"""
        template_str = """<!DOCTYPE html>
<html>
<head>
    <title>Genetic Trading System - Generation {{ generation }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .stats { background-color: #f9f9f9; padding: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>Genetic Trading System - Generation {{ generation }}</h1>

    <div class="stats">
        <h2>Population Statistics</h2>
        <p><strong>Population Size:</strong> {{ stats.population_size }}</p>
        <p><strong>Best Return:</strong> {{ stats.best_return|format_percent }}</p>
        <p><strong>Average Return:</strong> {{ stats.avg_return|format_percent }}</p>
        <p><strong>Average Sharpe:</strong> {{ stats.avg_sharpe|format_number }}</p>
        <p><strong>Generated:</strong> {{ stats.timestamp|format_datetime }}</p>
    </div>

    <h2>Top 50 Performers</h2>
    <table>
        <tr>
            <th>Rank</th>
            <th>Total Return</th>
            <th>Sharpe Ratio</th>
            <th>Max Drawdown</th>
            <th>Win Rate</th>
            <th>Trades</th>
        </tr>
        {% for result in top_performers %}
        <tr>
            <td>{{ loop.index }}</td>
            <td>{{ result.total_return|format_percent }}</td>
            <td>{{ result.sharpe_ratio|format_number }}</td>
            <td>{{ result.max_drawdown|format_percent }}</td>
            <td>{{ result.win_rate|format_percent }}</td>
            <td>{{ result.num_trades }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>"""

        return self.env.from_string(template_str)

    def _create_basic_chromosome_template(self):
        """Create basic chromosome template if none exists"""
        template_str = """<!DOCTYPE html>
<html>
<head>
    <title>Chromosome {{ chromosome_id }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .metric { margin: 10px 0; }
        .metric strong { display: inline-block; width: 200px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
    </style>
</head>
<body>
    <h1>Chromosome {{ chromosome_id }} {% if rank %}(Rank #{{ rank }}){% endif %}</h1>

    <h2>Performance Metrics</h2>
    <div class="metric"><strong>Total Return:</strong> {{ results.total_return|format_percent }}</div>
    <div class="metric"><strong>Sharpe Ratio:</strong> {{ results.sharpe_ratio|format_number }}</div>
    <div class="metric"><strong>Max Drawdown:</strong> {{ results.max_drawdown|format_percent }}</div>
    <div class="metric"><strong>Win Rate:</strong> {{ results.win_rate|format_percent }}</div>
    <div class="metric"><strong>Total Trades:</strong> {{ results.num_trades }}</div>

    <h2>Recent Trades</h2>
    <table>
        <tr>
            <th>Date</th>
            <th>Ticker</th>
            <th>Action</th>
            <th>Shares</th>
            <th>Price</th>
            <th>Total</th>
        </tr>
        {% for trade in trades[-20:] %}
        <tr>
            <td>{{ trade.date|format_date }}</td>
            <td>{{ trade.ticker }}</td>
            <td>{{ trade.action }}</td>
            <td>{{ trade.shares|format_number }}</td>
            <td>{{ trade.price|format_currency }}</td>
            <td>{{ trade.total|format_currency }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>"""

        return self.env.from_string(template_str)

    def _create_basic_generation_template(self):
        """Create basic generation template if none exists"""
        template_str = """<!DOCTYPE html>
<html>
<head>
    <title>Generation {{ generation }} Summary</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .stats { background-color: #f9f9f9; padding: 15px; margin: 20px 0; }
        .metric { margin: 10px 0; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
    </style>
</head>
<body>
    <h1>Generation {{ generation }} Summary</h1>

    <div class="stats">
        <h2>Returns Statistics</h2>
        <div class="metric"><strong>Mean:</strong> {{ stats.returns.mean|format_percent }}</div>
        <div class="metric"><strong>Median:</strong> {{ stats.returns.median|format_percent }}</div>
        <div class="metric"><strong>Best:</strong> {{ stats.returns.max|format_percent }}</div>
        <div class="metric"><strong>Worst:</strong> {{ stats.returns.min|format_percent }}</div>
        <div class="metric"><strong>Std Dev:</strong> {{ stats.returns.std|format_percent }}</div>
    </div>

    <h2>Top 10 Chromosomes</h2>
    <table>
        <tr>
            <th>Rank</th>
            <th>Total Return</th>
            <th>Sharpe Ratio</th>
            <th>Max Drawdown</th>
            <th>Trades</th>
        </tr>
        {% for result in top_performers %}
        <tr>
            <td>{{ loop.index }}</td>
            <td>{{ result.total_return|format_percent }}</td>
            <td>{{ result.sharpe_ratio|format_number }}</td>
            <td>{{ result.max_drawdown|format_percent }}</td>
            <td>{{ result.num_trades }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>"""

        return self.env.from_string(template_str)

    def __repr__(self) -> str:
        return f"BlogGenerator(output_dir='{self.output_dir}')"
