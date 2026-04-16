"""Generate support and resistance analysis reports from backtest results."""
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from datetime import datetime

from backtest.portfolio import Portfolio
from scripts.support_resistance import compute_and_log_support_resistance_zones
from scripts.multiframe import create_sr_multiframe_pdf_direct


def generate_sr_analysis(
    results: Dict[str, Tuple[Portfolio, Dict]],
    sr_histories: Dict[str, Dict],
    sr_penguin_names: Set[str],
    bar_timestamps: List[datetime],
    artifacts_dir: Path,
    enable_additional_plots: bool = False,
) -> None:
    """
    Generate all support and resistance analysis outputs.
    
    Args:
        results: Dict[penguin_name] = (portfolio, metrics)
        sr_histories: Dict[penguin_name] = symbol_history
        sr_penguin_names: Set of S/R-using strategy names
        bar_timestamps: List of timestamps from backtest
        artifacts_dir: Directory to save artifacts
        enable_additional_plots: Whether to enable additional PNG generation
    """
    artifacts_path = Path(artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    
    # Generate basic S&R zones
    if sr_penguin_names:
        print("\nAnalyzing support and resistance zones...")
        try:
            # Collect symbol prices only from active S/R-based strategies.
            symbol_prices = defaultdict(list)
            for penguin_name, (portfolio, _metrics) in results.items():
                if penguin_name not in sr_penguin_names:
                    continue
                for trade in portfolio.trades:
                    symbol_prices[trade.symbol].append(trade.price)

            # Compute S&R zones for current run.
            compute_and_log_support_resistance_zones(symbol_prices, str(artifacts_path))
            print("✅ S&R zones computed and saved")
        except Exception as e:
            print(f"⚠️  S&R analysis error: {e}")
    else:
        print("\nSkipping support and resistance zone analysis (no active S/R-based strategies)")

    # Generate multitimeframe S/R line plots (if enabled)
    if enable_additional_plots:
        print("\nSkipping multitimeframe S/R PNG generation (no sr_lines folders requested)")
    else:
        print("\nSkipping additional multitimeframe plots (ENABLE_ADDITIONAL_PLOTS=False)")

    # Always generate SR multiframe PDF directly from recorded S/R history.
    if sr_histories:
        print("\nGenerating SR multiframe PDF...")
        try:
            combined_history = {}
            for _penguin_name, history_by_symbol in sr_histories.items():
                if history_by_symbol:
                    combined_history.update(history_by_symbol)

            if combined_history:
                current_dir = artifacts_path.parent
                current_sr_pdf = current_dir / "SR_Multiframe_plots.pdf"
                create_sr_multiframe_pdf_direct(
                    combined_history,
                    current_sr_pdf,
                    bar_timestamps,
                )
                print(f"✅ SR multiframe PDF: {current_sr_pdf}")
            else:
                print("⚠️  No SR history data available for SR multiframe PDF")
        except Exception as e:
            print(f"⚠️  SR multiframe PDF error: {e}")
