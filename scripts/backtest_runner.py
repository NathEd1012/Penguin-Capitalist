"""Main backtest runner - executes historical backtests for all penguins."""
import os
import shutil
import sys
from datetime import datetime, timezone, timedelta
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
from scripts.data_fixes.synthetic_spread_model import SyntheticSpreadModel
from config import (
    SYMBOLS,
    ACTIVE_SYMBOL_LIST,
    INITIAL_CAPITAL,
    EXEC_TRANSACTION_COST,
    START_DATE,
    STOP_DATE,
    BINNING,
    ACTIVE_PENGUINS,
    SAVE_TO_RUN_OLD,
)



def percent_progress(iterable, desc: str):
    total = len(iterable)
    if total == 0:
        return

    progress = tqdm(total=total, desc=desc)
    last_percent = -1

    try:
        for index, item in enumerate(iterable, start=1):
            percent = (index * 100) // total
            if percent != last_percent:
                progress.update(index - progress.n)
                last_percent = percent
            yield index - 1, item

        if progress.n < total:
            progress.update(total - progress.n)
    finally:
        progress.close()


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


def _binning_to_minutes(binning: str) -> int:
    mapping = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "1h": 60,
        "1d": 1440,
    }
    try:
        return mapping[binning.strip().lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported binning: {binning}") from exc


def _history_warmup_bars(penguin_classes: List) -> int:
    warmup_bars = 0
    for penguin_class in penguin_classes:
        lookback_bars = int(getattr(penguin_class, "LOOKBACK_BARS", 1000))
        min_history_required = int(getattr(penguin_class, "MIN_HISTORY_REQUIRED", 0))
        warmup_bars = max(warmup_bars, max(1, lookback_bars), max(0, min_history_required))
    return warmup_bars


def run_backtest(
    symbols: List[str],
    start_datetime: datetime,
    end_datetime: datetime,
    binning: str,
    initial_capital: float,
    transaction_cost: float,
    penguin_classes: List,
    artifacts_dir: Path | None = None,
) -> Tuple[Dict[str, Tuple[Portfolio, Dict]], Dict, List[datetime], Dict[str, Dict], str]:
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

    warmup_bars = _history_warmup_bars(penguin_classes)
    warmup_minutes = _binning_to_minutes(binning)
    warmup_start_datetime_utc = start_datetime_utc - timedelta(minutes=warmup_bars * warmup_minutes)
    
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
            warmup_start_datetime_utc,
            end_datetime_utc,
            binning,
            enable_data_quality_checks=True,
        )
        if sparse_warning:
            print(sparse_warning)
        quality_report_text = loader.get_quality_report_text()
        if quality_report_text:
            if artifacts_dir is not None:
                warnings_path = artifacts_dir / "consistency_warnings.txt"
                with open(warnings_path, "w") as f:
                    f.write(quality_report_text)
                    f.write("\n")
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
    tradeable_timestamps = [timestamp for timestamp in sorted_timestamps if timestamp >= start_datetime_utc]
    print(f"  Tradeable bars from configured start: {len(tradeable_timestamps)}")
    
    # Initialize portfolios and penguins
    portfolios = {}
    penguins = {}
    
    # Initialize synthetic spread model for realistic bid/ask
    spread_model = SyntheticSpreadModel()
    
    print(f"\nStep 3: Initializing {len(penguin_classes)} strategies...")
    for penguin_class in tqdm(penguin_classes, desc="Initializing strategies"):
        try:
            penguin = penguin_class()
            pen_name = penguin.name
            portfolios[pen_name] = Portfolio(initial_capital, transaction_cost)
            portfolios[pen_name].max_leverage = float(getattr(penguin, "MAX_LEVERAGE", 1.0))
            penguins[pen_name] = penguin
        except Exception as e:
            print(f"  ✗ {penguin_class.__name__}: {e}")

    # Run simulation
    print(f"\nStep 4: Running backtest ({len(sorted_timestamps)} bars)...\n")
    
    # Prepare price history for each symbol
    price_history = defaultdict(list)

    # Track trades by bar for detailed logging
    trades_by_bar = defaultdict(list)
    trade_bar_idx = -1

    for bar_idx, timestamp in percent_progress(sorted_timestamps, desc="Executing bars"):
        # Get current prices
        current_prices = {}
        for symbol in symbols:
            bar = data[symbol].get(timestamp)
            if bar and bar.get("data_quality", "OK") == "OK":
                current_prices[symbol] = bar["close"]

        if not current_prices:
            continue

        # Update price history for each symbol
        for symbol in symbols:
            bar = data[symbol].get(timestamp)
            if bar is None:
                if symbol in price_history and price_history[symbol]:
                    # Keep last known price if data is missing entirely.
                    price_history[symbol].append(price_history[symbol][-1])
                else:
                    price_history[symbol].append(current_prices.get(symbol, 0))
            elif bar.get("data_quality", "OK") == "OK":
                price_history[symbol].append(bar["close"])
            else:
                # Quarantined bars are removed from the strategy-visible history.
                continue

        if timestamp < start_datetime_utc:
            continue

        trade_bar_idx += 1

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

            if hasattr(penguin, "set_current_timestamp"):
                penguin.set_current_timestamp(timestamp)

            if bar_idx == len(sorted_timestamps) - 1:
                continue

            if hasattr(penguin, "decide_batch"):
                batch_orders = penguin.decide_batch(symbols, quotes, portfolio)
                for order_symbol, action, quantity in batch_orders:
                    if order_symbol not in quotes or quantity <= 0:
                        continue

                    bid, ask = quotes[order_symbol]
                    if action == "BUY":
                        if portfolio.buy(order_symbol, quantity, ask, timestamp):
                            trades_by_bar[trade_bar_idx].append(
                                f"  {penguin_name}: BUY {quantity} {order_symbol} @ ${ask:.2f}"
                            )
                    elif action == "SELL":
                        if portfolio.sell(order_symbol, quantity, bid, timestamp):
                            trades_by_bar[trade_bar_idx].append(
                                f"  {penguin_name}: SELL {quantity} {order_symbol} @ ${bid:.2f}"
                            )

                value = portfolio.get_total_value(current_prices)
                portfolio.add_value_snapshot(value)
                continue

            # Set current timestamp for S/R penguins that track history
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

                # Only enforce minimum history requirement if penguin explicitly needs it
                min_history_required = getattr(penguin, "MIN_HISTORY_REQUIRED", 0)
                if len(full_history) < min_history_required:
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
                        portfolio,
                    )

                    # For non-leveraged SPY strategies, cap quantity to cash affordability.
                    if action == "BUY" and symbol == "SPY" and ask > 0 and portfolio.max_leverage <= 1.0:
                        max_affordable_qty = int(
                            max(portfolio.cash - portfolio.transaction_cost, 0) // ask
                        )
                        quantity = max_affordable_qty

                    if action == "BUY" and quantity > 0:
                        if portfolio.buy(symbol, quantity, ask, timestamp):
                            trades_by_bar[trade_bar_idx].append(
                                f"  {penguin_name}: BUY {quantity} {symbol} @ ${ask:.2f}"
                            )
                    elif action == "SELL" and quantity > 0:
                        if portfolio.sell(symbol, quantity, bid, timestamp):
                            trades_by_bar[trade_bar_idx].append(
                                f"  {penguin_name}: SELL {quantity} {symbol} @ ${bid:.2f}"
                            )

                except Exception:
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
    
    return results, trades_by_bar, tradeable_timestamps, quality_report_text


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

    base_dir = Path(__file__).parent.parent
    current_dir = base_dir / "run_current"
    current_artifacts_dir = current_dir / "artifacts"
    current_artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Run backtest
    results, trades_by_bar, bar_timestamps, data_quality_report = run_backtest(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=BINNING,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=EXEC_TRANSACTION_COST,
        penguin_classes=ACTIVE_PENGUINS,
        artifacts_dir=current_artifacts_dir,
    )
    
    # Generate report
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    Evaluator.print_summary(results)

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
    Evaluator.save_results(results, None, current_artifacts_dir, trades_by_bar, bar_timestamps)
    
    # Generate plots
    print("\nGenerating visualization...")
    current_plot = current_artifacts_dir / "capital_curves.png"
    
    # Get number of bars from first portfolio
    num_bars = None
    for portfolio, _ in results.values():
        num_bars = len(portfolio.value_history)
        break
    
    Evaluator.plot_capital_curves(
        results,
        current_plot,
        num_bars,
        BINNING,
        START_DATE,
        STOP_DATE,
        bar_timestamps,
        ACTIVE_SYMBOL_LIST,
    )
    
    # Generate PDF reports
    print("\nGenerating PDF report...")
    current_pdf = current_dir / "report.pdf"
    
    Evaluator.generate_pdf_report(
        results,
        current_pdf,
        current_plot,
        num_bars,
        BINNING,
        START_DATE,
        STOP_DATE,
        bar_timestamps,
        current_artifacts_dir,
        ACTIVE_SYMBOL_LIST,
    )
    
    print("\nSkipping consistency validation (removed)")
    
    # Mirror run_current into run_old only after current run is fully written.
    if archive_dir:
        archive_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(current_dir, archive_dir)

    print(f"\n✅ Backtest complete!")
    
    if archive_dir:
        print(f"\nArchive saved to:  {archive_dir}")
        print(f"  - report.pdf")
        print(f"  - artifacts/capital_curves.png")
        print(f"  - artifacts/json/curves_data.json")
        print(f"  - artifacts/json/metrics_summary.json")
        print(f"  - artifacts/trades_log.txt")
        print(f"  - artifacts/consistency_warnings.txt (if residual jumps)")
    
    print(f"\nCurrent run saved to: {current_dir}")
    print(f"  - report.pdf")
    print(f"  - artifacts/capital_curves.png")
    print(f"  - artifacts/json/curves_data.json")
    print(f"  - artifacts/json/metrics_summary.json")
    print(f"  - artifacts/trades_log.txt")
    print(f"  - artifacts/consistency_warnings.txt (if residual jumps)")
    
    print(f"\n{'='*80}")
    if archive_dir:
        print(f"Run #{archived_run_num} archived")
    else:
        print("Run updated (not archived - SAVE_TO_RUN_OLD is False)")


if __name__ == "__main__":
    main()
