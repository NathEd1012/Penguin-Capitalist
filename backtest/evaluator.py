"""Performance evaluation and reporting for backtests."""
import json
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path
from backtest.portfolio import Portfolio

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


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
    ):
        """
        Plot capital curves for all strategies.
        
        Args:
            results: Dict[penguin_name] = (portfolio, metrics)
            output_file: Path to save PNG
        """
        plt.figure(figsize=(14, 8))
        
        # Sort by final return for better visualization ordering
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1][1]['return_pct'],
            reverse=True
        )
        
        # Plot each strategy
        colors = plt.cm.tab20(np.linspace(0, 1, len(sorted_results)))
        
        for (penguin_name, (portfolio, metrics)), color in zip(sorted_results, colors):
            if portfolio.value_history:
                plt.plot(
                    range(len(portfolio.value_history)),
                    portfolio.value_history,
                    label=f"{penguin_name} ({metrics['return_pct']:.2f}%)",
                    linewidth=2,
                    color=color,
                    alpha=0.8
                )
        
        plt.axhline(y=5000, color='black', linestyle='--', linewidth=1, alpha=0.5, label='Initial Capital')
        plt.xlabel('Time Period', fontsize=12, fontweight='bold')
        plt.ylabel('Portfolio Value ($)', fontsize=12, fontweight='bold')
        plt.title('Penguin Capitalist - Strategy Performance Over Time', fontsize=14, fontweight='bold')
        plt.legend(loc='best', fontsize=9, ncol=2)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        plt.savefig(str(output_file), dpi=150, bbox_inches='tight')
        print(f"Saved capital curves plot to {output_file}")
        plt.close()
    
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
    ):
        """
        Generate a PDF report of backtest results.
        
        Args:
            results: Dict[penguin_name] = (portfolio, metrics)
            output_file: Path to save PDF
            plot_file: Path to capital curves PNG (optional)
        """
        if not HAS_REPORTLAB:
            print("⚠️  reportlab not installed. Skipping PDF generation.")
            print("   Install with: pip install reportlab")
            return
        
        doc = SimpleDocTemplate(str(output_file), pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=30,
            alignment=1,  # Center
        )
        story.append(Paragraph("Penguin Capitalist Backtest Report", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        story.append(Paragraph(f"<i>Generated: {timestamp}</i>", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Results table
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1][1]['return_pct'],
            reverse=True
        )
        
        table_data = [['Strategy', 'Final Value', 'Return %', 'Trades', 'Max DD %', 'Sharpe']]
        for penguin_name, (_, metrics) in sorted_results:
            table_data.append([
                penguin_name[:25],
                f"${metrics['final_value']:,.2f}",
                f"{metrics['return_pct']:.2f}%",
                str(metrics['total_trades']),
                f"{metrics['max_drawdown']:.2f}%",
                f"{metrics['sharpe_ratio']:.2f}",
            ])
        
        table = Table(table_data, colWidths=[2*inch, 1.2*inch, 1*inch, 0.8*inch, 1*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.3*inch))
        
        # Best performer highlight
        best_penguin, (_, best_metrics) = sorted_results[0]
        story.append(Paragraph("<b>🏆 Best Performer</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(f"<b>Strategy:</b> {best_penguin}", styles['Normal']))
        story.append(Paragraph(f"<b>Final Value:</b> ${best_metrics['final_value']:,.2f}", styles['Normal']))
        story.append(Paragraph(f"<b>Return:</b> {best_metrics['return_pct']:.2f}%", styles['Normal']))
        story.append(Paragraph(f"<b>Max Drawdown:</b> {best_metrics['max_drawdown']:.2f}%", styles['Normal']))
        story.append(Paragraph(f"<b>Sharpe Ratio:</b> {best_metrics['sharpe_ratio']:.2f}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Add capital curves plot if available
        if plot_file and Path(plot_file).exists():
            story.append(PageBreak())
            story.append(Paragraph("<b>Capital Curves</b>", styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))
            img = Image(str(plot_file), width=6.5*inch, height=3.5*inch)
            story.append(img)
        
        # Build PDF
        doc.build(story)
        print(f"Saved PDF report to {output_file}")

