"""Main entry point for historical backtesting simulation."""
import os
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Tuple, List
from collections import defaultdict
import pytz
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tqdm import tqdm
from backtest.portfolio import Portfolio
from backtest.data_loader import DataLoader
from backtest.evaluator import Evaluator
from scripts.synthetic_spread_model import SyntheticSpreadModel
from scripts.validation import check_consistency
from scripts.support_resistance import compute_and_log_support_resistance_zones
from scripts.plotting import plot_multitimeframe_sr_history, create_png_gallery_pdf
from config import (
    SYMBOLS,
    INITIAL_CAPITAL,
    TRANSACTION_COST,
    START_DATE,
    STOP_DATE,
    BINNING,
    ACTIVE_PENGUINS,
    SAVE_TO_RUN_OLD,
    ENABLE_ADDITIONAL_PLOTS,
)


def parse_datetime_string(dt_str: str) -> datetime:
    """
    Parse datetime from config format string.
    
    Accepts:
    - ISO format: "2026-02-20 14:30:00"
    - With timezone: "2026-02-20 14:30:00+01:00"
    - Special keyword: "TODAY" (resolves to yesterday at 23:50:00 UTC to avoid recent SIP data restrictions)
    
    Assumes UTC if no timezone specified.
    """
    dt_str = dt_str.strip()
    
    # Handle special keyword "TODAY"
    if dt_str.upper() == "TODAY":
        # Use yesterday at 23:50 UTC to avoid recent SIP data restrictions
        yesterday = datetime.now(pytz.UTC).replace(hour=23, minute=50, second=0, microsecond=0) - timedelta(days=1)
        return yesterday
    
    # Try parsing with timezone first
    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            return dt
        except ValueError:
            continue
    
    raise ValueError(f"Cannot parse datetime: {dt_str}")


def get_next_run_number(run_old_dir: Path) -> int:
    """Get the next run number for archives (e.g., run1, run2, run3, ...)."""
    current_date = datetime.now().strftime("%y%m%d")
    date_dir = run_old_dir / current_date
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
    end_datetime: datetime,
    binning: str,
    initial_capital: float,
    transaction_cost: float,
    penguin_classes: List,
) -> Tuple[Dict[str, Tuple[Portfolio, Dict]], Dict, List[datetime], Dict[str, Dict]]:
    """
    Run historical backtest.
    
    Args:
        symbols: List of symbols to trade
        start_datetime: Start datetime (UTC)
        end_datetime: End datetime (UTC)
        binning: Timeframe string ("1m", "5m", "15m", "1h", "1d")
        initial_capital: Initial capital
        transaction_cost: Transaction cost per trade
        penguin_classes: List of penguin strategy classes
    
    Returns:
        Dict[penguin_name] = (portfolio, metrics)
    """
    
    # Ensure both datetimes are UTC
    if start_datetime.tzinfo is None:
        start_datetime = pytz.UTC.localize(start_datetime)
    if end_datetime.tzinfo is None:
        end_datetime = pytz.UTC.localize(end_datetime)
    
    # Convert to UTC if needed
    start_datetime_utc = start_datetime.astimezone(pytz.UTC)
    end_datetime_utc = end_datetime.astimezone(pytz.UTC)
    
    # Determine required symbols from active penguins when possible.
    # If every active penguin declares TRADED_SYMBOLS, we only load that union.
    # If at least one penguin is unrestricted, keep the full configured symbol list.
    restricted_sets = []
    for penguin_class in penguin_classes:
        traded = getattr(penguin_class, "TRADED_SYMBOLS", None)
        if traded is None:
            restricted_sets = []
            break
        restricted_sets.append(set(traded))

    if restricted_sets and len(restricted_sets) == len(penguin_classes):
        requested_symbols = sorted(set().union(*restricted_sets).intersection(set(symbols)))
        if requested_symbols:
            symbols = requested_symbols

    print(f"\n{'='*80}")
    print(f"BACKTEST CONFIGURATION")
    print(f"{'='*80}")
    print(f"Start Time (UTC):  {start_datetime_utc}")
    print(f"End Time (UTC):    {end_datetime_utc}")
    print(f"Binning:           {binning}")
    print(f"Initial Capital:   ${initial_capital:,.2f}")
    print(f"Transaction Cost:  ${transaction_cost:.2f}")
    print(f"Symbols:           {len(symbols)}")
    print(f"{'='*80}\n")
    
    # Load data
    print("Step 1: Loading historical data from Alpaca...")
    loader = DataLoader()
    try:
        data, sparse_warning = loader.load_bars(
            symbols,
            start_datetime_utc,
            end_datetime_utc,
            binning
        )
        if sparse_warning:
            print(sparse_warning)
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
    
    # Initialize synthetic spread model for realistic bid/ask
    spread_model = SyntheticSpreadModel()
    
    print(f"\nStep 3: Initializing {len(penguin_classes)} strategies...")
    for penguin_class in tqdm(penguin_classes, desc="Initializing strategies"):
        try:
            penguin = penguin_class()
            if hasattr(penguin, "record_history"):
                penguin.record_history = bool(ENABLE_ADDITIONAL_PLOTS)
            pen_name = penguin.name
            portfolios[pen_name] = Portfolio(initial_capital, transaction_cost)
            penguins[pen_name] = penguin
        except Exception as e:
            print(f"  ✗ {penguin_class.__name__}: {e}")

    sr_penguin_names = {
        name for name, penguin in penguins.items() if getattr(penguin, "USES_SR_LINES", False)
    }
    
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
        quotes = {}
        for symbol in current_prices:
            bar = data[symbol][timestamp]
            bid, ask, _ = spread_model.get_bid_ask(
                mid_price=bar["close"],
                high=bar["high"],
                low=bar["low"],
                timestamp=timestamp,
                volume=bar.get("volume", 0),
                symbol=symbol,
            )
            quotes[symbol] = (bid, ask)

        for penguin_name, penguin in penguins.items():
            portfolio = portfolios[penguin_name]
            penguin_symbols = getattr(penguin, "TRADED_SYMBOLS", None)
            if penguin_symbols is not None:
                symbols_for_penguin = [s for s in symbols if s in penguin_symbols]
            else:
                symbols_for_penguin = symbols
            
            # Get lookback requirement for this penguin
            lookback_bars = getattr(penguin, "LOOKBACK_BARS", 1000)
            
            for symbol in symbols_for_penguin:
                if symbol not in current_prices:
                    continue
                
                # Pass only necessary price history window to penguin.
                # This dramatically improves performance for large backtests.
                full_history = price_history[symbol]
                if len(full_history) < 10:  # Need minimum history
                    continue
                
                # Slice only the last lookback_bars from history
                mid_prices = full_history[-lookback_bars:] if len(full_history) > lookback_bars else full_history
                
                bid, ask = quotes[symbol]
                
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
    print("\nClosing all positions...")
    
    for penguin_name, portfolio in tqdm(portfolios.items(), desc="Closing positions"):
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
    print("\nCalculating performance metrics...")
    results = {}
    for penguin_name, portfolio in tqdm(portfolios.items(), desc="Computing metrics"):
        metrics = Evaluator.calculate_metrics(portfolio, initial_capital)
        results[penguin_name] = (portfolio, metrics)
    
    sr_histories = {}
    for penguin_name, penguin in penguins.items():
        if hasattr(penguin, "export_sr_history"):
            sr_histories[penguin_name] = penguin.export_sr_history()

    return results, trades_by_bar, sorted_timestamps, sr_histories


def main():
    """Main entry point."""
    # Parse config dates
    try:
        start_dt = parse_datetime_string(START_DATE)
        end_dt = parse_datetime_string(STOP_DATE)
    except ValueError as e:
        print(f"Error parsing config dates: {e}")
        print(f"  START_DATE: {START_DATE}")
        print(f"  STOP_DATE: {STOP_DATE}")
        sys.exit(1)
    
    print("\n" + "="*80)
    print("PENGUIN CAPITALIST - HISTORICAL BACKTEST")
    print("="*80)
    
    # Run backtest
    results, trades_by_bar, bar_timestamps, sr_histories = run_backtest(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=BINNING,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=TRANSACTION_COST,
        penguin_classes=ACTIVE_PENGUINS,
    )
    
    # Identify S/R penguins from results
    sr_penguin_names = {name for name in sr_histories.keys()}
    
    # Generate report
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    Evaluator.print_summary(results)
    
    # Create archive and current directories
    base_dir = Path(__file__).parent
    current_dir = base_dir / "run_current"
    current_artifacts_dir = current_dir / "artifacts"
    current_artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Conditionally set up archive directory based on config
    if SAVE_TO_RUN_OLD:
        run_old_base = base_dir / "run_old"
        next_run_num = get_next_run_number(run_old_base)
        current_date = datetime.now().strftime("%y%m%d")
        archive_dir = run_old_base / current_date / f"run{next_run_num}"
        archived_run_num = next_run_num
    else:
        archive_dir = None
        archived_run_num = None
    
    # Always write run_current first.
    Evaluator.save_results(results, None, current_artifacts_dir, trades_by_bar)
    
    # Generate plots
    print("\nGenerating visualization...")
    current_plot = current_artifacts_dir / "capital_curves.png"
    
    # Get number of bars from first portfolio
    num_bars = None
    for portfolio, _ in results.values():
        num_bars = len(portfolio.value_history)
        break
    
    Evaluator.plot_capital_curves(results, current_plot, num_bars, BINNING, START_DATE, STOP_DATE, bar_timestamps)
    
    # Generate PDF reports
    print("\nGenerating PDF report...")
    current_pdf = current_dir / "report.pdf"
    
    Evaluator.generate_pdf_report(results, current_pdf, current_plot, num_bars, BINNING, START_DATE, STOP_DATE, bar_timestamps)
    
    # Validate consistency (check for price jumps)
    print("\nValidating consistency...")
    try:
        # Collect latest prices and curve values for validation
        latest_prices = {}
        curve_values = {}
        for penguin_name, (portfolio, metrics) in results.items():
            if portfolio.trades:
                # Get latest price for each symbol from last trade
                for trade in portfolio.trades:
                    latest_prices[trade.symbol] = trade.price
            curve_values[penguin_name] = portfolio.value_history
        
        # Run consistency checks
        warnings = check_consistency(
            results=results,
            max_jump_pct=0.15
        )
        
        if warnings:
            print(f"\n⚠️  Consistency warnings detected ({len(warnings)}):")
            for warning in warnings[:5]:  # Show first 5 warnings
                print(f"  - {warning}")
            if len(warnings) > 5:
                print(f"  ... and {len(warnings) - 5} more")
            
            # Save warnings to file
            current_warnings = current_artifacts_dir / "consistency_warnings.txt"
            with open(current_warnings, 'w') as f:
                f.write("Consistency Check Warnings\n")
                f.write("="*60 + "\n\n")
                for warning in warnings:
                    f.write(f"• {warning}\n")
        else:
            print("✅ All consistency checks passed")
    except Exception as e:
        print(f"⚠️  Consistency validation error: {e}")
    
    # Generate Support & Resistance zones
    if sr_penguin_names:
        print("\nAnalyzing support and resistance zones...")
        try:
            # Collect symbol prices only from active S/R-based strategies.
            symbol_prices = defaultdict(list)
            for penguin_name, (portfolio, metrics) in results.items():
                if penguin_name not in sr_penguin_names:
                    continue
                for trade in portfolio.trades:
                    symbol_prices[trade.symbol].append(trade.price)

            # Compute S&R zones for current run.
            compute_and_log_support_resistance_zones(symbol_prices, str(current_artifacts_dir))
            print("✅ S&R zones computed and saved")
        except Exception as e:
            print(f"⚠️  S&R analysis error: {e}")
    else:
        print("\nSkipping support and resistance zone analysis (no active S/R-based strategies)")

    # Generate multitimeframe S/R line plots (if enabled)
    if ENABLE_ADDITIONAL_PLOTS:
        print("\nGenerating multitimeframe S/R line plots...")
        try:
            current_pngs = []

            for penguin_name, history_by_symbol in sr_histories.items():
                if not history_by_symbol:
                    continue

                current_sr_dir = current_artifacts_dir / f"{penguin_name}_sr_lines"
                created_current = plot_multitimeframe_sr_history(
                    history_by_symbol,
                    current_sr_dir,
                    bar_timestamps,
                )
                current_pngs.extend(created_current)

                print(f"✅ {penguin_name}: generated {len(created_current)} S&R line plot(s)")

            # Create one combined PDF containing all multitimeframe PNG plots.
            if current_pngs:
                current_sr_pdf = current_artifacts_dir / "multitimeframe_sr_plots.pdf"
                create_png_gallery_pdf(current_pngs, current_sr_pdf)
                print(f"✅ Combined multitimeframe PDF: {current_sr_pdf}")

        except Exception as e:
            print(f"⚠️  Multitimeframe S&R plotting error: {e}")
    else:
        print("\nSkipping additional multitimeframe plots (ENABLE_ADDITIONAL_PLOTS=False)")
    
    # Mirror run_current into run_old only after current run is fully written.
    if archive_dir:
        archive_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(current_dir, archive_dir)

    print(f"\n✅ Backtest complete!")
    
    if archive_dir:
        print(f"\nArchive saved to:  {archive_dir}")
        print(f"  - report.pdf")
        print(f"  - artifacts/capital_curves.png")
        print(f"  - artifacts/curves_data.json")
        print(f"  - artifacts/metrics_summary.json")
        print(f"  - artifacts/trades_log.txt")
        print(f"  - artifacts/consistency_warnings.txt (if warnings)")
        print(f"  - artifacts/support_resistance_zones.txt")
    
    print(f"\nCurrent run saved to: {current_dir}")
    print(f"  - report.pdf")
    print(f"  - artifacts/capital_curves.png")
    print(f"  - artifacts/curves_data.json")
    print(f"  - artifacts/metrics_summary.json")
    print(f"  - artifacts/trades_log.txt")
    print(f"  - artifacts/consistency_warnings.txt (if warnings)")
    print(f"  - artifacts/support_resistance_zones.txt")
    
    print(f"\n{'='*80}")
    if archive_dir:
        print(f"Run #{archived_run_num} archived")
    else:
        print("Run updated (not archived - SAVE_TO_RUN_OLD is False)")


if __name__ == "__main__":
    main()
