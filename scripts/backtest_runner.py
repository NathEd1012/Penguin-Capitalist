"""Main backtest runner - executes historical backtests for all penguins."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple, List
from collections import defaultdict
import pytz
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm
from backtest.portfolio import Portfolio
from backtest.data_loader import DataLoader
from backtest.evaluator import Evaluator
from config import (
    SYMBOLS,
    INITIAL_CAPITAL,
    TRANSACTION_COST,
    BAR_TIMEFRAME_MINUTES,
    Run_start,
    NUM_BARS_TO_BACKTEST,
    ACTIVE_PENGUINS,
)


def parse_datetime_config(dt_int: int) -> datetime:
    """
    Parse datetime from config format YYYYMMDD_HHMM (as integer).
    Example: 202602201630 -> 2026-02-20 16:30 CET
    """
    dt_str = str(dt_int).zfill(12)  # Pad to 12 digits: YYYYMMDDHHMM
    
    year = int(dt_str[0:4])
    month = int(dt_str[4:6])
    day = int(dt_str[6:8])
    hour = int(dt_str[8:10])
    minute = int(dt_str[10:12])
    
    # CET timezone
    cet = pytz.timezone('Europe/Berlin')
    dt = cet.localize(datetime(year, month, day, hour, minute))
    return dt


def calculate_bars_end_datetime(start: datetime, num_bars: int, minutes_per_bar: int) -> datetime:
    """Calculate end datetime based on number of bars."""
    from datetime import timedelta
    return start + timedelta(minutes=num_bars * minutes_per_bar)


def generate_timeframe_string(start_dt: datetime, end_dt: datetime) -> str:
    """Generate a timeframe string for directory naming (e.g., '2026-02-20_1400-1600')."""
    start_str = start_dt.strftime('%Y-%m-%d_%H%M')
    end_str = end_dt.strftime('%H%M')
    return f"{start_str}-{end_str}"


def get_next_run_number(run_old_dir: Path) -> int:
    """Get the next run number for archives (e.g., run1, run2, run3, ...)."""
    date_dir = run_old_dir / "260225"
    date_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all existing run folders
    existing_runs = [d for d in date_dir.iterdir() if d.is_dir() and d.name.startswith("run")]
    
    if not existing_runs:
        return 1
    
    # Extract numbers and find max
    run_numbers = []
    for run_dir in existing_runs:
        try:
            num = int(run_dir.name[3:])  # Extract number from "runX"
            run_numbers.append(num)
        except ValueError:
            continue
    
    return max(run_numbers) + 1 if run_numbers else 1


def run_backtest(
    symbols: List[str],
    start_datetime: datetime,
    num_bars: int,
    timeframe_minutes: int,
    initial_capital: float,
    transaction_cost: float,
    penguin_classes: List,
) -> Dict[str, Tuple[Portfolio, Dict]]:
    """
    Run historical backtest.
    
    Args:
        symbols: List of symbols to trade
        start_datetime: Start datetime (CET)
        num_bars: Number of bars to simulate
        timeframe_minutes: Minutes per bar
        initial_capital: Initial capital
        transaction_cost: Transaction cost per trade
        penguin_classes: List of penguin strategy classes
    
    Returns:
        Dict[penguin_name] = (portfolio, metrics)
    """
    
    # Convert start datetime to UTC for Alpaca API
    if start_datetime.tzinfo is None:
        start_datetime = pytz.timezone('Europe/Berlin').localize(start_datetime)
    start_datetime_utc = start_datetime.astimezone(pytz.UTC)
    
    # Calculate end datetime
    end_datetime_utc = calculate_bars_end_datetime(
        start_datetime_utc,
        num_bars,
        timeframe_minutes
    )
    
    print(f"\n{'='*80}")
    print(f"BACKTEST CONFIGURATION")
    print(f"{'='*80}")
    print(f"Start Time (CET):  {start_datetime}")
    print(f"End Time (UTC):    {end_datetime_utc}")
    print(f"Duration:          ~{num_bars} bars × {timeframe_minutes} minutes")
    print(f"Initial Capital:   ${initial_capital:,.2f}")
    print(f"Transaction Cost:  ${transaction_cost:.2f}")
    print(f"Symbols:           {len(symbols)}")
    print(f"{'='*80}\n")
    
    # Load data
    print("Step 1: Loading historical data from Alpaca...")
    loader = DataLoader()
    try:
        data = loader.load_bars(
            symbols,
            start_datetime_utc,
            end_datetime_utc,
            timeframe_minutes
        )
    except Exception as e:
        print(f"Error loading data: {e}")
        print("Make sure APCA_API_KEY_ID and APCA_API_SECRET_KEY are set.")
        sys.exit(1)
    
    # Detect stale data
    print("\nStep 2: Detecting stale data...")
    valid_symbols, stale_symbols = loader.detect_stale_data(data)
    
    print(f"  Valid symbols: {len(valid_symbols)}")
    if stale_symbols:
        print(f"  Stale symbols ({len(stale_symbols)}): {', '.join(stale_symbols)}")
    
    symbols = valid_symbols
    if not symbols:
        print("No valid symbols to trade!")
        sys.exit(1)
    
    # Get sorted timestamps for all symbols
    all_timestamps = set()
    for symbol_data in data.values():
        all_timestamps.update(symbol_data.keys())
    
    sorted_timestamps = sorted(all_timestamps)
    print(f"\n  Total bars across all symbols: {len(sorted_timestamps)}")
    
    # Initialize portfolios and penguins
    portfolios = {}
    penguins = {}
    
    print(f"\nStep 3: Initializing {len(penguin_classes)} strategies...")
    for penguin_class in penguin_classes:
        try:
            penguin = penguin_class()
            pen_name = penguin.name
            portfolios[pen_name] = Portfolio(initial_capital, transaction_cost)
            penguins[pen_name] = penguin
            print(f"  ✓ {pen_name}")
        except Exception as e:
            print(f"  ✗ {penguin_class.__name__}: {e}")
    
    # Run simulation
    print(f"\nStep 4: Running backtest ({len(sorted_timestamps)} bars)...\n")
    
    # Prepare price history for each symbol
    price_history = defaultdict(list)
    
    # Track trades by bar for detailed logging
    trades_by_bar = defaultdict(list)
    
    for bar_idx, timestamp in enumerate(tqdm(sorted_timestamps, desc="Executing bars")):
        # Get current prices
        current_prices = {}
        for symbol in symbols:
            if timestamp in data[symbol]:
                bar = data[symbol][timestamp]
                current_prices[symbol] = bar['close']
        
        if not current_prices:
            continue
        
        # Update price history for each symbol
        for symbol in symbols:
            if timestamp in data[symbol]:
                bar = data[symbol][timestamp]
                price_history[symbol].append(bar['close'])
            elif symbol in price_history:
                # Keep last known price if data missing
                price_history[symbol].append(price_history[symbol][-1])
            else:
                price_history[symbol].append(current_prices.get(symbol, 0))
        
        # Let each penguin make decisions
        for penguin_name, penguin in penguins.items():
            portfolio = portfolios[penguin_name]
            
            for symbol in symbols:
                if symbol not in current_prices:
                    continue
                
                # Get mid prices for analysis (last 100 bars)
                mid_prices = price_history[symbol][-100:]
                if len(mid_prices) < 10:  # Need minimum history
                    continue
                
                # Get bid/ask (use close ± small spread)
                close = current_prices[symbol]
                bid = close * 0.999
                ask = close * 1.001
                
                try:
                    action, quantity = penguin.decide(
                        symbol,
                        mid_prices,
                        bid,
                        ask,
                        portfolio
                    )
                    
                    if action == "BUY" and quantity > 0:
                        if portfolio.buy(symbol, quantity, ask, timestamp):
                            trades_by_bar[bar_idx].append(
                                f"  {penguin_name}: BUY {quantity} {symbol} @ ${ask:.2f}"
                            )
                    elif action == "SELL" and quantity > 0:
                        if portfolio.sell(symbol, quantity, bid, timestamp):
                            trades_by_bar[bar_idx].append(
                                f"  {penguin_name}: SELL {quantity} {symbol} @ ${bid:.2f}"
                            )
                
                except Exception as e:
                    # Silently skip errors to continue backtest
                    pass
            
            # Record portfolio value
            value = portfolio.get_total_value(current_prices)
            portfolio.add_value_snapshot(value)
    
    # Sell all positions at end - use average price from last 10 bars to avoid unrealistic jumps
    print("\nClosing all positions...\n")
    
    for penguin_name, portfolio in portfolios.items():
        # For each position, close using average price of last few bars
        for symbol, quantity in list(portfolio.positions.items()):
            if quantity > 0:
                # Get price history - use last 10 bars average
                symbol_prices = price_history[symbol][-10:] if symbol in price_history else []
                
                if symbol_prices:
                    close_price = np.mean(symbol_prices)
                else:
                    # Fallback to final price
                    close_price = price_history[symbol][-1] if symbol in price_history else 0
                
                if close_price > 0:
                    portfolio.sell(symbol, quantity, close_price, sorted_timestamps[-1])
        
        # Add final snapshot with smoothed price
        final_prices = {}
        for symbol in symbols:
            if symbol in price_history and price_history[symbol]:
                final_prices[symbol] = np.mean(price_history[symbol][-10:])
        
        final_value = portfolio.get_total_value(final_prices)
        portfolio.add_value_snapshot(final_value)
    
    # Calculate metrics
    print("Calculating performance metrics...")
    results = {}
    for penguin_name, portfolio in portfolios.items():
        metrics = Evaluator.calculate_metrics(portfolio, initial_capital)
        results[penguin_name] = (portfolio, metrics)
    
    return results, trades_by_bar


def main():
    """Main entry point."""
    # Parse config
    start_dt = parse_datetime_config(Run_start)
    
    # Number of bars to simulate (from config)
    num_bars = NUM_BARS_TO_BACKTEST
    
    print("\n" + "="*80)
    print("PENGUIN CAPITALIST - HISTORICAL BACKTEST")
    print("="*80)
    
    # Run backtest
    results, trades_by_bar = run_backtest(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        num_bars=num_bars,
        timeframe_minutes=BAR_TIMEFRAME_MINUTES,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=TRANSACTION_COST,
        penguin_classes=ACTIVE_PENGUINS,
    )
    
    # Generate report
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    Evaluator.print_summary(results)
    
    # Create archive and current directories
    base_dir = Path(__file__).parent.parent
    run_old_base = base_dir / "run_old"
    
    # Get next run number
    next_run_num = get_next_run_number(run_old_base)
    archive_dir = run_old_base / "260225" / f"run{next_run_num}"
    current_dir = base_dir / "run_current"
    
    # Save results to both locations
    Evaluator.save_results(results, archive_dir, current_dir, trades_by_bar)
    
    # Generate plots
    print("\nGenerating visualization...")
    archive_plot = archive_dir / "capital_curves.png"
    current_plot = current_dir / "capital_curves.png"
    
    Evaluator.plot_capital_curves(results, archive_plot)
    Evaluator.plot_capital_curves(results, current_plot)
    
    # Generate PDF reports
    print("\nGenerating PDF report...")
    archive_pdf = archive_dir / "backtest_report.pdf"
    current_pdf = current_dir / "backtest_report.pdf"
    
    Evaluator.generate_pdf_report(results, archive_pdf, archive_plot)
    Evaluator.generate_pdf_report(results, current_pdf, current_plot)
    
    print(f"\n✅ Backtest complete!")
    print(f"\nArchive saved to:  {archive_dir}")
    print(f"  - capital_curves.png")
    print(f"  - curves_data.json")
    print(f"  - metrics_summary.json")
    print(f"  - trades_log.txt")
    print(f"  - backtest_report.pdf")
    print(f"\nCurrent run saved to: {current_dir}")
    print(f"  - capital_curves.png")
    print(f"  - curves_data.json")
    print(f"  - metrics_summary.json")
    print(f"  - trades_log.txt")
    print(f"  - backtest_report.pdf")
    print(f"\n{'='*80}")
    print(f"Run #{next_run_num} archived")


if __name__ == "__main__":
    main()
