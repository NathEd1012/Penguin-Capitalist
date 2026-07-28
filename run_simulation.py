"""Main entry point for historical backtesting simulation."""
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Tuple, List
from collections import defaultdict
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

mpl_config_dir = Path(os.environ.get("MPLCONFIGDIR", "/private/tmp/penguin_mplconfig"))
xdg_cache_dir = Path(os.environ.get("XDG_CACHE_HOME", "/private/tmp/penguin_xdg_cache"))
try:
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))
    os.environ.setdefault("MPLBACKEND", "Agg")
except Exception:
    pass

from tqdm import tqdm
from backtest.portfolio import Portfolio
from backtest.data_loader import DataLoader
from backtest.evaluator import Evaluator
from scripts.data_fixes.synthetic_spread_model import SyntheticSpreadModel
from penguins.decision_utils import call_penguin_decide
from config import (
    SYMBOLS,
    ACTIVE_SYMBOL_LIST,
    INITIAL_CAPITAL,
    EXEC_TRANSACTION_COST,
    START_DATE,
    STOP_DATE,
    BINNING,
    ACTIVE_PENGUINS,
    SAVE_TO_RUN_LOG,
    DIREKTORY_NAME,
    get_run_output_dir,
    TRAINING_STEP_ENABLED,
    TRAINING_ITERATIONS,
    TRAINING_SUBSET_MONTHS,
    TRAINING_SUBSET_STOCKS,
    TRAINING_RELATIVE_TO,
    TRAINING_RANDOM_SEED,
    TRAINING_START_DATE,
    TRAINING_STOP_DATE,
    TRAINING_TRANSACTION_COST,
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
    if isinstance(dt_str, datetime):
        dt = dt_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    dt_str = dt_str.strip()

    if dt_str.upper() == "TODAY":
        yesterday = datetime.now(timezone.utc).replace(hour=23, minute=50, second=0, microsecond=0) - timedelta(days=1)
        return yesterday

    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    raise ValueError(f"Cannot parse datetime: {dt_str}")


def _format_runtime_configuration_banner(
    *,
    start_datetime_utc,
    end_datetime_utc,
    binning,
    initial_capital,
    transaction_cost,
    symbols,
    active_symbol_list,
    training_step_enabled,
    training_relative_to,
    training_iterations,
    training_subset_stocks,
    training_subset_months,
    training_transaction_cost,
    training_random_seed,
    training_start_datetime_utc,
    training_end_datetime_utc,
) -> str:
    """Return the runtime banner text for backtest and training configuration."""

    lines = [
        f"{'=' * 80}",
        "BACKTEST CONFIGURATION",
        f"{'=' * 80}",
        f"Start Time (UTC):  {start_datetime_utc}",
        f"End Time (UTC):    {end_datetime_utc}",
        f"Binning:           {binning}",
        "",
        "PORTFOLIO CONFIGURATION",
        f"Initial Capital:   ${initial_capital:,.2f}",
        f"Transaction Cost:  ${transaction_cost:.2f}",
        f"Symbol List:       {active_symbol_list}",
        f"Symbols:           {len(symbols)}",
        f"{'=' * 80}",
        "",
        f"{'=' * 80}",
        "TRAINING CONFIGURATION",
        f"{'=' * 80}",
        f"Training Step Enabled: {str(training_step_enabled).lower()}",
        f"Training Relative To:  {training_relative_to}",
        f"Training Steps:        {training_iterations}",
        f"Training Sample:       {training_subset_stocks} stocks x {training_subset_months} month(s)",
        f"Training Transaction Cost: ${training_transaction_cost:.2f}",
        f"Training Seed:         {training_random_seed}",
        f"Training Start (UTC):  {training_start_datetime_utc}",
        f"Training End (UTC):    {training_end_datetime_utc}",
        f"{'=' * 80}",
    ]
    return "\n".join(lines)


def _replace_trainable_penguin_params(penguin, params: Dict[str, int | float]):
    try:
        updated_penguin = penguin.__class__(name=penguin.name, **params)
        if hasattr(penguin, "record_history"):
            updated_penguin.record_history = bool(getattr(penguin, "record_history"))
        return updated_penguin
    except Exception:
        if hasattr(penguin, "params"):
            for key, value in params.items():
                setattr(penguin.params, key, value)
        return penguin


def _penguin_history_requirements(penguin) -> tuple[int, int]:
    """Return (visible history window, minimum history before trading)."""
    try:
        lookback_bars = int(getattr(penguin, "LOOKBACK_BARS", 1000))
    except (TypeError, ValueError):
        lookback_bars = 1000

    try:
        min_history_required = int(getattr(penguin, "MIN_HISTORY_REQUIRED", 0))
    except (TypeError, ValueError):
        min_history_required = 0

    lookback_bars = max(1, lookback_bars)
    min_history_required = max(0, min_history_required)
    required_history_bars = max(lookback_bars, min_history_required)
    return lookback_bars, required_history_bars


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
        _, required_history_bars = _penguin_history_requirements(penguin_class)
        warmup_bars = max(warmup_bars, required_history_bars)
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
    training_step_allowed: bool = True,
) -> Tuple[
    Dict[str, Tuple[Portfolio, Dict]],
    Dict,
    List[datetime],
    Dict[str, Dict],
    Dict[str, List[Tuple[datetime, float]]],
    str,
]:
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
        start_datetime = start_datetime.replace(tzinfo=timezone.utc)
    if end_datetime.tzinfo is None:
        end_datetime = end_datetime.replace(tzinfo=timezone.utc)
    
    # Convert to UTC if needed
    start_datetime_utc = start_datetime.astimezone(timezone.utc)
    end_datetime_utc = end_datetime.astimezone(timezone.utc)

    warmup_bars = _history_warmup_bars(penguin_classes)
    warmup_minutes = _binning_to_minutes(binning)
    warmup_start_datetime_utc = start_datetime_utc - timedelta(minutes=warmup_bars * warmup_minutes)
    
    # Determine required symbols from active penguins when possible.
    # If every active penguin declares TRADED_SYMBOLS, we only load that union.
    # If at least one penguin is unrestricted, keep the full configured symbol list.
    restricted_sets = []
    all_restricted = True
    for penguin_class in penguin_classes:
        traded = getattr(penguin_class, "TRADED_SYMBOLS", None)
        if traded is None:
            all_restricted = False
            break

        restricted_sets.append(set(traded))

    if all_restricted and restricted_sets:
        requested_symbols = sorted(set().union(*restricted_sets).intersection(set(symbols)))
        if requested_symbols:
            symbols = requested_symbols

    print("\n" + _format_runtime_configuration_banner(
        start_datetime_utc=start_datetime_utc,
        end_datetime_utc=end_datetime_utc,
        binning=binning,
        initial_capital=initial_capital,
        transaction_cost=transaction_cost,
        symbols=symbols,
        active_symbol_list=ACTIVE_SYMBOL_LIST,
        training_step_enabled=TRAINING_STEP_ENABLED,
        training_relative_to=TRAINING_RELATIVE_TO,
        training_iterations=TRAINING_ITERATIONS,
        training_subset_stocks=TRAINING_SUBSET_STOCKS,
        training_subset_months=TRAINING_SUBSET_MONTHS,
        training_transaction_cost=TRAINING_TRANSACTION_COST,
        training_random_seed=TRAINING_RANDOM_SEED,
        training_start_datetime_utc=TRAINING_START_DATE,
        training_end_datetime_utc=TRAINING_STOP_DATE,
    ))
    
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
    
    ################################ STEP 2 ################################

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
    
    symbol_close_series: Dict[str, List[Tuple[datetime, float]]] = {}
    # Initialize portfolios and penguins
    portfolios = {}
    penguins = {}
    
    # Initialize synthetic spread model for realistic bid/ask
    spread_model = SyntheticSpreadModel()

    ################################ STEP 3 ################################


    print(f"\nStep 3: Initializing {len(penguin_classes)} strategies...")
    for penguin_spec in tqdm(penguin_classes, desc="Initializing strategies"):
        try:
            if isinstance(penguin_spec, type):
                penguin = penguin_spec()
            elif hasattr(penguin_spec, "decide"):
                penguin = penguin_spec
            else:
                penguin = penguin_spec()
            pen_name = penguin.name
            portfolios[pen_name] = Portfolio(initial_capital, transaction_cost)
            portfolios[pen_name].max_leverage = float(getattr(penguin, "MAX_LEVERAGE", 1.0))
            penguins[pen_name] = penguin
        except Exception as e:
            penguin_name = getattr(penguin_spec, "__name__", getattr(penguin_spec, "name", str(penguin_spec)))
            print(f"  ✗ {penguin_name}: {e}")

    ################################ STEP 3b ################################

    if training_step_allowed:
        active_trainables = []
        seen_trainable_classes = set()
        for penguin in penguins.values():
            penguin_class = penguin.__class__
            if getattr(penguin_class, "TRAINABLE", False) and penguin_class not in seen_trainable_classes:
                active_trainables.append(penguin_class)
                seen_trainable_classes.add(penguin_class)

        if active_trainables:
            from scripts.train_trainable_penguins import prepare_training_context, run_training_step

            training_start_dt = parse_datetime_string(TRAINING_START_DATE)
            training_end_dt = parse_datetime_string(TRAINING_STOP_DATE)
            training_symbols, _training_sorted_timestamps, training_tradeable_timestamps, training_quality_report_text = prepare_training_context(
                symbols=symbols,
                start_datetime=training_start_dt,
                end_datetime=training_end_dt,
                binning=binning,
                penguin_classes=active_trainables,
            )

            if training_quality_report_text and artifacts_dir is not None:
                training_warnings_path = Path(artifacts_dir) / "training_consistency_warnings.txt"
                with open(training_warnings_path, "w") as f:
                    f.write(training_quality_report_text)
                    f.write("\n")

            training_artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else Path(__file__).parent / "run_test" / "artifacts"
            trained_parameters = run_training_step(
                trainable_strategy_classes=active_trainables,
                symbols=training_symbols,
                tradeable_timestamps=training_tradeable_timestamps,
                binning=binning,
                initial_capital=initial_capital,
                artifacts_dir=training_artifacts_dir,
            )

            for penguin_name, penguin in list(penguins.items()):
                strategy_name = penguin.__class__.__name__
                if strategy_name in trained_parameters:
                    penguins[penguin_name] = _replace_trainable_penguin_params(
                        penguin,
                        trained_parameters[strategy_name]["best_params"],
                    )
        else:
            print("No trainable penguins are active; skipping Step 3b training.")

    ################################ STEP 4 ################################


    # Run simulation
    print(f"\nStep 4: Running backtest ({len(sorted_timestamps)} bars)...\n")
    
    # Prepare price history for each symbol
    price_history = defaultdict(list)
    volume_history = defaultdict(list)
    
    # Track trades by bar for detailed logging
    trades_by_bar = defaultdict(list)
    trade_bar_idx = -1
    
    for bar_idx, timestamp in percent_progress(sorted_timestamps, desc="Executing bars"):
        # Get current prices
        current_prices = {}
        for symbol in symbols:
            bar = data[symbol].get(timestamp)
            if bar and bar.get("data_quality", "OK") == "OK":
                current_prices[symbol] = bar['close']
        
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
                if symbol in volume_history and volume_history[symbol]:
                    volume_history[symbol].append(volume_history[symbol][-1])
                else:
                    volume_history[symbol].append(0.0)
            elif bar.get("data_quality", "OK") == "OK":
                price_history[symbol].append(bar['close'])
                volume_history[symbol].append(bar.get('volume', 0))
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

            lookback_bars, required_history_bars = _penguin_history_requirements(penguin)
            penguin_symbols = getattr(penguin, "TRADED_SYMBOLS", None)
            if penguin_symbols is not None:
                symbols_for_penguin = [s for s in symbols if s in penguin_symbols]
            else:
                symbols_for_penguin = symbols

            if hasattr(penguin, "decide_batch"):
                ready_symbols = [
                    symbol
                    for symbol in symbols_for_penguin
                    if symbol in quotes and len(price_history[symbol]) >= required_history_bars
                ]
                ready_quotes = {symbol: quotes[symbol] for symbol in ready_symbols}

                batch_orders = penguin.decide_batch(ready_symbols, ready_quotes, portfolio)
                for order_symbol, action, quantity in batch_orders:
                    if order_symbol not in ready_quotes or quantity <= 0:
                        continue

                    bid, ask = ready_quotes[order_symbol]
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
            
            for symbol in symbols_for_penguin:
                if symbol not in current_prices:
                    continue
                
                # Pass only data-backed windows to strategies. No penguin may trade
                # until its configured lookback/minimum history is available.
                full_history = price_history[symbol]
                if len(full_history) < required_history_bars:
                    continue
                
                mid_prices = full_history[-lookback_bars:]
                spy_prices = price_history.get("SPY", [])
                spy_window = spy_prices[-lookback_bars:] if len(spy_prices) > lookback_bars else spy_prices
                volumes = volume_history[symbol]
                volumes_window = volumes[-lookback_bars:] if len(volumes) > lookback_bars else volumes
                bid, ask = quotes[symbol]
                
                try:
                    action, quantity = call_penguin_decide(
                        penguin,
                        symbol,
                        mid_prices,
                        bid,
                        ask,
                        portfolio,
                        spy_prices=spy_window,
                        volumes=volumes_window,
                    )
                    
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
                
                except Exception as e:
                    # Silently skip errors to continue backtest
                    pass
            
            # Record portfolio value
            value = portfolio.get_total_value(current_prices)
            portfolio.add_value_snapshot(value)
        
    # ======================== FINAL LIQUIDATION ========================
    # CRITICAL CONSTRAINTS for end-of-backtest liquidation:
    # 1. DO NOT call penguin.decide() or any signal evaluation methods
    # 2. DO NOT rerank penguins
    # 3. DO NOT recompute indicators during liquidation
    # 4. ONLY close existing open positions at fair prices
    #
    # This ensures final positions are closed cleanly without artificially
    # triggering new trades or changing strategy rankings based on final-bar behavior.
    # ===================================================================
    
    print("\nClosing all positions...")
    
    for penguin_name, portfolio in tqdm(portfolios.items(), desc="Closing positions"):
        # For each open position in this portfolio, close it cleanly.
        # Use average price from last 10 bars to smooth final closing price
        # and avoid unrealistic single-bar spikes.
        for symbol, quantity in list(portfolio.positions.items()):
            if quantity > 0:
                # Get price history for this SPECIFIC symbol (last_price_by_symbol)
                symbol_prices = price_history[symbol][-10:] if symbol in price_history else []
                
                if symbol_prices:
                    # Use average of last 10 bars for smooth liquidation
                    close_price = np.mean(symbol_prices)
                else:
                    # Fallback: use final available price for this symbol
                    close_price = price_history[symbol][-1] if symbol in price_history else 0
                
                # Execute closing sell only if we have a valid price
                if close_price > 0:
                    portfolio.sell(symbol, quantity, close_price, sorted_timestamps[-1])
        
        # Record final portfolio value using symbol-specific price averaging
        # (previous_close_by_symbol)
        final_prices = {}
        for symbol in symbols:
            if symbol in price_history and price_history[symbol]:
                # Average last 10 bars for each symbol independently
                final_prices[symbol] = np.mean(price_history[symbol][-10:])
        
        final_value = portfolio.get_total_value(final_prices)
        portfolio.add_value_snapshot(final_value)
    
    # Calculate metrics
    print("\nCalculating performance metrics...")
    results = {}
    for penguin_name, portfolio in tqdm(portfolios.items(), desc="Computing metrics"):
        metrics = Evaluator.calculate_metrics(portfolio, initial_capital)
        results[penguin_name] = (portfolio, metrics)
    
    cleanup_start = time.perf_counter()
    print("\nReleasing large backtest buffers before returning...", flush=True)
    data = None
    price_history = None
    all_timestamps = None
    penguins = None
    portfolios = None
    loader = None
    spread_model = None
    symbol_data = None
    full_history = None
    mid_prices = None
    current_prices = None
    quotes = None
    final_prices = None
    symbol_prices = None
    bar = None
    print(f"Released large backtest buffers in {time.perf_counter() - cleanup_start:.2f}s", flush=True)
    return results, trades_by_bar, tradeable_timestamps, {}, symbol_close_series, quality_report_text


def main():
    """Main entry point."""
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

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

    base_dir = Path(__file__).parent
    run_output_dir = get_run_output_dir(base_dir, bool(SAVE_TO_RUN_LOG), DIREKTORY_NAME)
    run_artifacts_dir = run_output_dir / "artifacts"
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Training is executed inside `run_backtest` as Step 3b when enabled.
    
    ################ Run backtest ################
    results, trades_by_bar, bar_timestamps, _, _, _ = run_backtest(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=BINNING,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=EXEC_TRANSACTION_COST,
        penguin_classes=ACTIVE_PENGUINS,
        artifacts_dir=run_artifacts_dir,
    )
    print("\nrun_backtest() returned; generating results...", flush=True)
    
    # Generate report
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    Evaluator.print_summary(results)

    Evaluator.save_results(results, None, run_output_dir, trades_by_bar, bar_timestamps)

    # SMA artifact export intentionally disabled.
    print("\nSkipping SMA artifact export (no sma folder requested)")
    
    # Generate plots
    print("\nGenerating visualization...")
    run_plot = run_artifacts_dir / "capital_curves.png"
    
    # Get number of bars from first portfolio
    num_bars = None
    for portfolio, _ in results.values():
        num_bars = len(portfolio.value_history)
        break
    
    Evaluator.plot_capital_curves(
        results,
        run_plot,
        num_bars,
        BINNING,
        START_DATE,
        STOP_DATE,
        bar_timestamps,
        ACTIVE_SYMBOL_LIST,
    )
    
    # Generate PDF reports
    print("\nGenerating PDF report...")
    run_pdf = run_output_dir / "report.pdf"
    # Ensure matplotlib has sensible fallback fonts on systems missing DejaVu.
    try:
        import matplotlib
        matplotlib.rcParams.setdefault("font.family", "sans-serif")
        matplotlib.rcParams.setdefault("font.sans-serif", ["Helvetica", "Arial", "DejaVu Sans", "Liberation Sans"])
        matplotlib.rcParams.setdefault("mathtext.fontset", "stix")
    except Exception:
        # If matplotlib isn't available here, PDF generation will fail later and be handled below.
        pass

    try:
        Evaluator.generate_pdf_report(
            results,
            run_pdf,
            run_plot,
            num_bars,
            BINNING,
            START_DATE,
            STOP_DATE,
            bar_timestamps,
            run_artifacts_dir,
            ACTIVE_SYMBOL_LIST,
        )
    except Exception as e:
        print(f"\n⚠️  PDF generation failed: {e}")
        print("Skipping PDF report (fonts or rendering issue).")
    
    print(f"\n✅ Backtest complete!")

    if SAVE_TO_RUN_LOG:
        print(f"\nLog saved to:  {run_output_dir}")
    else:
        print(f"\nTest run saved to: {run_output_dir}")
    print(f"  - report.pdf")
    print(f"  - artifacts/capital_curves.png")
    print(f"  - artifacts/json/curves_data.json")
    print(f"  - artifacts/json/metrics_summary.json")
    print(f"  - artifacts/trades_log.txt")
    print(f"  - artifacts/consistency_warnings.txt (if residual jumps)")
    
    print(f"\n{'='*80}")
    if SAVE_TO_RUN_LOG:
        print("Run archived in run_log")
    else:
        print("Run saved in run_test")

    # Attempt a clean shutdown: close plotting resources and detect background threads.
    try:
        import threading
        try:
            import matplotlib.pyplot as plt
            plt.close('all')
        except Exception:
            pass

        non_main = [t for t in threading.enumerate() if t is not threading.main_thread()]
        non_daemon = [t.name for t in non_main if not t.daemon and t.is_alive()]
        if non_daemon:
            print(f"\nNote: {len(non_daemon)} non-daemon background thread(s) still running: {non_daemon}")
            print("If you want the process to exit immediately, run with CTRL+C or enable forced exit in the runner.")
    except Exception:
        # Defensive: don't raise from shutdown diagnostics
        pass

    # Exit explicitly to avoid waiting for non-daemon threads in some environments.
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Backtest stopped.")
        sys.exit(130)
