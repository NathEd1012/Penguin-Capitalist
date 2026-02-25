"""Performance evaluation and reporting for backtests."""
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path
from backtest.portfolio import Portfolio
from scripts.plotting import plot_capital_curves, create_final_report_pdf


class Evaluator:
    """Calculate performance metrics and generate reports."""
    
    @staticmethod
    def calculate_metrics(portfolio: Portfolio, initial_capital: float) -> Dict:
        """
        Calculate performance metrics for a portfolio.
        
        Args:
            portfolio: Portfolio object with value history
            initial_capital: Initial capital amount
        
        Returns:
            Dictionary with metrics
        """
        if not portfolio.value_history:
            return {
                'total_return': 0,
                'return_pct': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
            }
        
        values = np.array(portfolio.value_history, dtype=float)
        
        # Total return
        final_value = values[-1]
        total_return = final_value - initial_capital
        return_pct = (total_return / initial_capital) * 100
        
        # Maximum drawdown
        running_max = np.maximum.accumulate(values)
        drawdown = (values - running_max) / running_max
        max_drawdown = np.min(drawdown) * 100
        
        # Daily returns (simplified using value snapshots)
        if len(values) > 1:
            returns = np.diff(values) / values[:-1]
            returns = returns[~np.isnan(returns)]
            returns = returns[~np.isinf(returns)]
            
            if len(returns) > 0:
                sharpe_ratio = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252)
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        # Trade counts
        buy_trades = sum(1 for trade in portfolio.trades if trade.action == "BUY")
        sell_trades = sum(1 for trade in portfolio.trades if trade.action == "SELL")
        total_trades = len(portfolio.trades)
        
        return {
            'total_return': round(total_return, 2),
            'return_pct': round(return_pct, 2),
            'max_drawdown': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'final_value': round(final_value, 2),
        }
    
    @staticmethod
    def plot_capital_curves(
        results: Dict[str, Tuple[Portfolio, Dict]],
        output_file: Path,
        num_bars: int = None,
        binning: str = "1m",
        start_date: str = None,
        stop_date: str = None,
    ):
        """
        Plot capital curves for all strategies with overall average line.
        
        Args:
            results: Dict[penguin_name] = (portfolio, metrics)
            output_file: Path to save PNG
            num_bars: Number of bars (optional, extracted from portfolio if not provided)
            binning: Timeframe string ("1m", "5m", "15m", "1h", "1d")
            start_date: Start date string for x-axis
            stop_date: Stop date string for x-axis
        """
        # Convert results format to curves dict
        curves = {}
        for penguin_name, (portfolio, _) in results.items():
            curves[penguin_name] = portfolio.value_history
        
        # Extract num_bars if not provided
        if num_bars is None and curves:
            num_bars = len(list(curves.values())[0])
        
        # Use plotting module
        plot_capital_curves(curves, str(output_file), num_bars, binning, start_date, stop_date)
    
    @staticmethod
    def save_results(
        results: Dict[str, Tuple[Portfolio, Dict]],
        archive_dir: Path,
        current_dir: Path,
        trades_by_bar: Dict = None,
    ):
        """
        Save backtest results to both archive and current directories.
        
        Args:
            results: Dict[penguin_name] = (portfolio, metrics)
            archive_dir: Archive directory path (timestamped)
            current_dir: Current run directory path (always latest)
            trades_by_bar: Dict[bar_idx] = [trade_strings] for detailed logging
        """
        archive_dir = Path(archive_dir)
        current_dir = Path(current_dir)
        
        archive_dir.mkdir(parents=True, exist_ok=True)
        current_dir.mkdir(parents=True, exist_ok=True)
        
        
        output_dirs = [archive_dir, current_dir]
        
        # Prepare data to save
        curves_data = {}
        for penguin_name, (portfolio, _) in results.items():
            curves_data[penguin_name] = [round(v, 2) for v in portfolio.value_history]
        
        metrics_data = {}
        for penguin_name, (_, metrics) in results.items():
            metrics_data[penguin_name] = metrics
        
        # Prepare trades log content
        trades_content = "Penguin Capitalist - Historical Backtest Log\n"
        trades_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        trades_content += "=" * 80 + "\n\n"
        
        if trades_by_bar:
            trades_content += "EXECUTION DETAILS\n"
            trades_content += "-" * 80 + "\n\n"
            
            for bar_idx, trades in sorted(trades_by_bar.items()):
                if trades:
                    trades_content += f"Bar {bar_idx}:\n"
                    for trade in trades:
                        trades_content += f"{trade}\n"
                    trades_content += "\n"
            
            trades_content += "\n" + "=" * 80 + "\n\n"
        
        trades_content += "STRATEGY SUMMARY\n"
        trades_content += "-" * 80 + "\n\n"
        
        for penguin_name, (portfolio, metrics) in results.items():
            trades_content += f"\n{penguin_name}\n"
            trades_content += f"  Final Value:    ${metrics['final_value']:,.2f}\n"
            trades_content += f"  Total Return:   ${metrics['total_return']:,.2f}  ({metrics['return_pct']:.2f}%)\n"
            trades_content += f"  Max Drawdown:   {metrics['max_drawdown']:.2f}%\n"
            trades_content += f"  Sharpe Ratio:   {metrics['sharpe_ratio']:.2f}\n"
            trades_content += f"  Total Trades:   {metrics['total_trades']}\n"
            trades_content += f"  Buy Trades:     {metrics['buy_trades']}\n"
            trades_content += f"  Sell Trades:    {metrics['sell_trades']}\n"
            trades_content += "\n  Recent Trades:\n"
            
            for trade in portfolio.trades[-20:]:
                trades_content += f"    {trade}\n"
            
            trades_content += "\n" + "-" * 80 + "\n"
        
        # Save to both directories
        for output_dir in output_dirs:
            curves_file = output_dir / "curves_data.json"
            with open(curves_file, 'w') as f:
                json.dump(curves_data, f, indent=2)
            
            metrics_file = output_dir / "metrics_summary.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics_data, f, indent=2)
            
            trades_file = output_dir / "trades_log.txt"
            with open(trades_file, 'w') as f:
                f.write(trades_content)
        
        print(f"\nSaved results to:")
        print(f"  Archive:   {archive_dir}")
        print(f"  Current:   {current_dir}")
    
    @staticmethod
    def print_summary(results: Dict[str, Tuple[Portfolio, Dict]]):
        """
        Print a summary table of all penguins performance.
        
        Args:
            results: Dict[penguin_name] = (portfolio, metrics)
        """
        print("\n" + "=" * 100)
        print(f"{'STRATEGY':<35} {'FINAL VALUE':>15} {'RETURN %':>12} {'TRADES':>10} {'SHARPE':>10}")
        print("=" * 100)
        
        # Sort by return percentage
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1][1]['return_pct'],
            reverse=True
        )
        
        for penguin_name, (_, metrics) in sorted_results:
            print(
                f"{penguin_name:<35} "
                f"${metrics['final_value']:>14,.2f} "
                f"{metrics['return_pct']:>11.2f}% "
                f"{metrics['total_trades']:>10} "
                f"{metrics['sharpe_ratio']:>10.2f}"
            )
        
        print("=" * 100)
        
        # Show best performer
        best_penguin, (_, best_metrics) = sorted_results[0]
        print(f"\n🏆 Best Performer: {best_penguin}")
        print(f"   Final Value: ${best_metrics['final_value']:,.2f}")
        print(f"   Return: {best_metrics['return_pct']:.2f}%")
        print(f"   Max Drawdown: {best_metrics['max_drawdown']:.2f}%")
        print(f"   Sharpe Ratio: {best_metrics['sharpe_ratio']:.2f}\n")
    
    @staticmethod
    def generate_pdf_report(
        results: Dict[str, Tuple[Portfolio, Dict]],
        output_file: Path,
        plot_file: Path = None,
        num_bars: int = None,
        binning: str = "1m",
        start_date: str = None,
        stop_date: str = None,
    ):
        """
        Generate a comprehensive PDF report with capital curves and detailed trade summaries.
        
        Args:
            results: Dict[penguin_name] = (portfolio, metrics)
            output_file: Path to save PDF
            plot_file: Path to capital curves PNG (optional, not used in this format)
            num_bars: Number of bars (optional, extracted from portfolio if not provided)
            binning: Timeframe string ("1m", "5m", "15m", "1h", "1d")
            start_date: Start date string for x-axis
            stop_date: Stop date string for x-axis
        """
        # Convert results to individual dicts for plotting module
        curves = {}
        portfolios = {}
        latest_prices = {}
        
        for penguin_name, (portfolio, _) in results.items():
            curves[penguin_name] = portfolio.value_history
            portfolios[penguin_name] = portfolio
            
            # Collect latest prices from trades
            for trade in portfolio.trades:
                if trade.symbol not in latest_prices:
                    latest_prices[trade.symbol] = trade.price
        
        # Extract num_bars if not provided
        if num_bars is None and curves:
            num_bars = len(list(curves.values())[0])
        
        # Use plotting module to generate PDF with detailed trade summaries
        create_final_report_pdf(curves, portfolios, str(output_file), latest_prices, num_bars, binning, start_date, stop_date)

