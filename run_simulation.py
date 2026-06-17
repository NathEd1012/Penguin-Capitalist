"""Main entry point for historical backtesting simulation."""
import json
import os
import random
import shutil
import sys
import time
from dataclasses import asdict
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
from scripts.synthetic_spread_model import SyntheticSpreadModel
from scripts.validation import check_consistency
from scripts.multiframe import (
    build_sr_strategy_sets,
    precompute_multiframe_levels,
    set_precomputed_levels_on_penguins,
)
from scripts.generate_sr_reports import generate_sr_analysis
from corporate_actions import has_corporate_action_near
from penguins import SP500
from config import (
    SYMBOLS,
    ACTIVE_SYMBOL_LIST,
    INITIAL_CAPITAL,
    TRANSACTION_COST,
    START_DATE,
    STOP_DATE,
    BINNING,
    ACTIVE_PENGUINS,
    SAVE_TO_RUN_OLD,
    ENABLE_ADDITIONAL_PLOTS,
    TRAINING_STEP_ENABLED,
    TRAINING_ITERATIONS,
    TRAINING_SUBSET_MONTHS,
    TRAINING_SUBSET_STOCKS,
    TRAINING_TRANSACTION_COST,
    TRAINING_BENCHMARK_SYMBOL,
    TRAINING_RANDOM_SEED,
    TRAINABLE_PENGUINS,
    TRAINING_RESULTS_FILENAME,
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
        yesterday = datetime.now(timezone.utc).replace(hour=23, minute=50, second=0, microsecond=0) - timedelta(days=1)
        return yesterday
    
    # Try parsing with timezone first
    for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
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


def _training_window_subset(sorted_timestamps: List[datetime], months: int, rng: random.Random) -> List[datetime]:
    if not sorted_timestamps:
        return []

    window_length = timedelta(days=max(1, months) * 30)
    latest_start = sorted_timestamps[-1] - window_length
    eligible_starts = [timestamp for timestamp in sorted_timestamps if timestamp <= latest_start]
    start_timestamp = rng.choice(eligible_starts) if eligible_starts else sorted_timestamps[0]
    end_timestamp = start_timestamp + window_length
    return [timestamp for timestamp in sorted_timestamps if start_timestamp <= timestamp <= end_timestamp]


def _training_symbol_subset(symbols: List[str], target_count: int, benchmark_symbol: str, rng: random.Random) -> List[str]:
    pool = list(dict.fromkeys(symbols))
    if benchmark_symbol in pool:
        pool.remove(benchmark_symbol)

    sample_size = min(len(pool), max(0, target_count - 1))
    subset = rng.sample(pool, sample_size) if sample_size > 0 else []
    if benchmark_symbol not in subset:
        subset.append(benchmark_symbol)
    return sorted(subset)


def _score_against_spy(candidate_metrics: Dict, benchmark_metrics: Dict) -> tuple[float, int, int]:
    relative_value = float(candidate_metrics.get("final_value", 0.0)) - float(benchmark_metrics.get("final_value", 0.0))
    return (
        relative_value,
        -int(candidate_metrics.get("buy_trades", 0)),
        -int(candidate_metrics.get("total_trades", 0)),
    )


def _sample_trainable_params(strategy_class, rng: random.Random) -> Dict[str, int | float]:
    strategy_name = strategy_class.__name__
    if strategy_name.endswith("TrainablePenguin1") or strategy_name.endswith("TrainablePenguin1_Manual"):
        buy_rsi = rng.uniform(18.0, 42.0)
        sell_rsi = rng.uniform(max(buy_rsi + 8.0, 55.0), 88.0)
        return {
            "rsi_period": rng.randint(7, 28),
            "buy_rsi": round(buy_rsi, 2),
            "sell_rsi": round(sell_rsi, 2),
            "max_cash_fraction_per_trade": round(rng.uniform(0.02, 0.20), 4),
            "stop_loss_pct": round(rng.uniform(0.01, 0.10), 4),
            "take_profit_pct": round(rng.uniform(0.02, 0.20), 4),
            "cooldown_bars": rng.randint(0, 30),
        }
    if strategy_name.endswith("TrainablePenguin2") or strategy_name.endswith("TrainablePenguin2_Manual"):
        return {
            "bb_period": rng.randint(10, 40),
            "bb_stddev": round(rng.uniform(1.0, 3.5), 2),
            "adx_period": rng.randint(7, 28),
            "adx_threshold": round(rng.uniform(10.0, 40.0), 2),
            "max_cash_fraction_per_trade": round(rng.uniform(0.02, 0.20), 4),
            "stop_loss_pct": round(rng.uniform(0.01, 0.10), 4),
            "take_profit_pct": round(rng.uniform(0.02, 0.20), 4),
            "cooldown_bars": rng.randint(0, 30),
        }
    raise ValueError(f"No parameter sampler is defined for {strategy_name}")


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


def _train_trainable_penguins(
    symbols: List[str],
    sorted_timestamps: List[datetime],
    binning: str,
    initial_capital: float,
    transaction_cost: float,
) -> Dict[str, Dict[str, object]]:
    rng = random.Random(TRAINING_RANDOM_SEED)
    trained_parameters: Dict[str, Dict[str, object]] = {}

    print(
        f"\nStep 3b: Training {len(TRAINABLE_PENGUINS)} trainable strategy(ies) "
        f"for {TRAINING_ITERATIONS} round(s) on {TRAINING_SUBSET_MONTHS} month(s) x {TRAINING_SUBSET_STOCKS} stock(s)..."
    )

    for strategy_class in TRAINABLE_PENGUINS:
        best_metrics = None
        best_score = None
        best_params: Dict[str, int | float] = {}

        baseline_instance = strategy_class()
        if hasattr(baseline_instance, "params"):
            try:
                best_params = asdict(baseline_instance.params)
            except Exception:
                best_params = dict(getattr(baseline_instance.params, "__dict__", {}))

        print(f"\n  Optimizing {strategy_class.__name__}")
        for trial_number in range(1, TRAINING_ITERATIONS + 1):
            trial_symbols = _training_symbol_subset(symbols, TRAINING_SUBSET_STOCKS, TRAINING_BENCHMARK_SYMBOL, rng)
            trial_timestamps = _training_window_subset(sorted_timestamps, TRAINING_SUBSET_MONTHS, rng)

            if not trial_symbols or not trial_timestamps:
                continue

            params = _sample_trainable_params(strategy_class, rng)
            candidate = strategy_class(**params)

            results, _, _, _, _, _ = run_backtest(
                symbols=trial_symbols,
                start_datetime=trial_timestamps[0],
                end_datetime=trial_timestamps[-1],
                binning=binning,
                initial_capital=initial_capital,
                transaction_cost=transaction_cost,
                penguin_classes=[candidate, SP500],
                enable_training_step=False,
            )

            candidate_metrics = results[candidate.name][1]
            benchmark_metrics = results[SP500().name][1]
            score = _score_against_spy(candidate_metrics, benchmark_metrics)

            if best_score is None or score > best_score:
                best_score = score
                best_metrics = candidate_metrics
                best_params = params

            print(
                f"    Trial {trial_number:03d}: relative=${score[0]:,.2f}, "
                f"buys={candidate_metrics.get('buy_trades', 0)}, score={score}"
            )

        trained_parameters[strategy_class.__name__] = {
            "best_params": best_params,
            "best_metrics": best_metrics,
            "best_score": list(best_score) if best_score is not None else None,
        }
        print(
            f"  Best {strategy_class.__name__}: relative=${(best_score[0] if best_score else 0.0):,.2f}, "
            f"buys={(best_metrics or {}).get('buy_trades', 0)}"
        )

    return trained_parameters


def run_backtest(
    symbols: List[str],
    start_datetime: datetime,
    end_datetime: datetime,
    binning: str,
    initial_capital: float,
    transaction_cost: float,
    penguin_classes: List,
    enable_training_step: bool = False,
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
        quality_report_text = loader.get_quality_report_text()
        if quality_report_text:
            print(f"\n{quality_report_text}")
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
    
    # Build close-price series only if S/R analysis or additional plots are enabled.
    # This step is expensive with large datasets and is currently unused (commented out).
    symbol_close_series: Dict[str, List[Tuple[datetime, float]]] = {}
    if ENABLE_ADDITIONAL_PLOTS:
        print("\n  Building close-price series for analytics...")
        for symbol in symbols:
            # `load_bars()` inserts bars in timestamp order, so we can reuse that order here.
            symbol_close_series[symbol] = [
                (ts, float(bar["close"])) for ts, bar in data[symbol].items()
            ]
        print(f"  ✓ Close-price series built for {len(symbol_close_series)} symbols")
    # Initialize portfolios and penguins
    portfolios = {}
    penguins = {}
    
    # Initialize synthetic spread model for realistic bid/ask
    spread_model = SyntheticSpreadModel()
    trained_parameters: Dict[str, Dict[str, object]] = {}

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
            if hasattr(penguin, "record_history"):
                penguin.record_history = bool(getattr(penguin, "USES_SR_LINES", False)) or bool(ENABLE_ADDITIONAL_PLOTS)
            pen_name = penguin.name
            portfolios[pen_name] = Portfolio(initial_capital, transaction_cost)
            portfolios[pen_name].max_leverage = float(getattr(penguin, "MAX_LEVERAGE", 1.0))
            penguins[pen_name] = penguin
        except Exception as e:
            penguin_name = getattr(penguin_spec, "__name__", getattr(penguin_spec, "name", str(penguin_spec)))
            print(f"  ✗ {penguin_name}: {e}")

    if enable_training_step:
        active_trainables = [
            penguin
            for penguin in penguins.values()
            if penguin.__class__ in set(TRAINABLE_PENGUINS)
        ]
        if active_trainables:
            trained_parameters = _train_trainable_penguins(
                symbols=symbols,
                sorted_timestamps=sorted_timestamps,
                binning=binning,
                initial_capital=initial_capital,
                transaction_cost=TRAINING_TRANSACTION_COST,
            )

            for penguin_name, penguin in list(penguins.items()):
                strategy_name = penguin.__class__.__name__
                if strategy_name in trained_parameters:
                    penguins[penguin_name] = _replace_trainable_penguin_params(
                        penguin,
                        trained_parameters[strategy_name]["best_params"],
                    )

            training_output_dir = Path(__file__).parent / "run_current" / "artifacts"
            training_output_dir.mkdir(parents=True, exist_ok=True)
            training_output_path = training_output_dir / TRAINING_RESULTS_FILENAME
            with open(training_output_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "iterations": TRAINING_ITERATIONS,
                        "subset_months": TRAINING_SUBSET_MONTHS,
                        "subset_stocks": TRAINING_SUBSET_STOCKS,
                        "benchmark_symbol": TRAINING_BENCHMARK_SYMBOL,
                        "transaction_cost": TRAINING_TRANSACTION_COST,
                        "trainable_strategies": trained_parameters,
                    },
                    handle,
                    indent=2,
                    default=str,
                )
            print(f"\nSaved training parameters to {training_output_path}")

    sr_penguin_names, precompute_sr_penguin_names = build_sr_strategy_sets(penguins)

    # Precompute multiframe S/R levels only for strategies that explicitly require it.
    if precompute_sr_penguin_names:
        print(f"\nStep 3c: Precomputing multiframe S/R levels for {len(precompute_sr_penguin_names)} strategy(ies)...")
        precomputed_sr_data = precompute_multiframe_levels(data, symbols, sorted_timestamps)

        # Set precomputed data on all S/R-using penguins
        set_precomputed_levels_on_penguins(penguins, precompute_sr_penguin_names, precomputed_sr_data)

        print(f"  ✓ Precomputed S/R levels for {len(precomputed_sr_data)} symbols\n")

    ################################ STEP 4 ################################


    # Run simulation
    print(f"\nStep 4: Running backtest ({len(sorted_timestamps)} bars)...\n")
    
    # Prepare price history for each symbol
    price_history = defaultdict(list)
    
    # Track trades by bar for detailed logging
    trades_by_bar = defaultdict(list)
    
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
            elif bar.get("data_quality", "OK") == "OK":
                price_history[symbol].append(bar['close'])
            else:
                # Quarantined bars are removed from the strategy-visible history.
                continue
        
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
                            trades_by_bar[bar_idx].append(
                                f"  {penguin_name}: BUY {quantity} {order_symbol} @ ${ask:.2f}"
                            )
                    elif action == "SELL":
                        if portfolio.sell(order_symbol, quantity, bid, timestamp):
                            trades_by_bar[bar_idx].append(
                                f"  {penguin_name}: SELL {quantity} {order_symbol} @ ${bid:.2f}"
                            )

                value = portfolio.get_total_value(current_prices)
                portfolio.add_value_snapshot(value)
                continue
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
        
        # Advance bar index for S/R penguins using precomputed levels
        """for penguin_name in sr_penguin_names:
            penguin = penguins[penguin_name]
            if hasattr(penguin, "_advance_bar"):
                penguin._advance_bar()"""
    
    # ======================== FINAL LIQUIDATION ========================
    # CRITICAL CONSTRAINTS for end-of-backtest liquidation:
    # 1. DO NOT call penguin.decide() or any signal evaluation methods
    # 2. DO NOT rerank penguins
    # 3. DO NOT recompute indicators or refresh S/R levels
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
    
    sr_histories = {}
    """for penguin_name, penguin in penguins.items():
        if hasattr(penguin, "export_sr_history"):
            sr_histories[penguin_name] = penguin.export_sr_history()
    """
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
    return results, trades_by_bar, sorted_timestamps, sr_histories, symbol_close_series, quality_report_text


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
    
    ################ Run backtest ################
    results, trades_by_bar, bar_timestamps, sr_histories, _symbol_close_series, data_quality_report = run_backtest(
        symbols=SYMBOLS,
        start_datetime=start_dt,
        end_datetime=end_dt,
        binning=BINNING,
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=TRANSACTION_COST,
        penguin_classes=ACTIVE_PENGUINS,
        enable_training_step=TRAINING_STEP_ENABLED,
    )
    print("\nrun_backtest() returned; generating results...", flush=True)
    
    # Identify S/R penguins from results
    """    sr_penguin_names = {name for name in sr_histories.keys()}
    """    
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

    data_quality_report_path = current_artifacts_dir / "data_quality_report.txt"
    with open(data_quality_report_path, 'w') as f:
        f.write(data_quality_report)
        f.write("\n")
    
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

    # SMA artifact export intentionally disabled.
    print("\nSkipping SMA artifact export (no sma folder requested)")
    
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
    except Exception as e:
        print(f"\n⚠️  PDF generation failed: {e}")
        print("Skipping PDF report (fonts or rendering issue).")
    
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
        warnings, bad_bar_indices = check_consistency(
            results=results,
            max_jump_pct=0.15,
            bar_timestamps=bar_timestamps
        )
        
        if warnings:
            print(f"\n⚠️  Consistency warnings detected ({len(warnings)})")
            for warning in warnings[:5]:  # Show first 5 warnings
                print(f"  - {warning}")
            if len(warnings) > 5:
                print(f"  ... and {len(warnings) - 5} more")
            
            # Save warnings to file
            current_warnings = current_artifacts_dir / "consistency_warnings.txt"
            with open(current_warnings, 'w') as f:
                f.write("Consistency Check Warnings (Real Issues + Faulty Data)\n")
                f.write("="*60 + "\n\n")
                for warning in warnings:
                    f.write(f"• {warning}\n")
                
                if bad_bar_indices:
                    f.write("\n" + "="*60 + "\n")
                    f.write("Bars with faulty data (trades should be reverted):\n")
                    f.write("="*60 + "\n\n")
                    for penguin_name, bar_indices in sorted(bad_bar_indices.items()):
                        if bar_indices:
                            f.write(f"  {penguin_name}: bars {sorted(bar_indices)}\n")
        else:
            print("✅ All consistency checks passed")
    except Exception as e:
        print(f"⚠️  Consistency validation error: {e}")
    
    # Generate Support & Resistance analysis reports
    """generate_sr_analysis(
        results=results,
        sr_histories=sr_histories,
        sr_penguin_names=sr_penguin_names,
        bar_timestamps=bar_timestamps,
        artifacts_dir=current_artifacts_dir,
        enable_additional_plots=ENABLE_ADDITIONAL_PLOTS,
    )"""
    
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
    print(f"  - artifacts/data_quality_report.txt")
    print(f"  - artifacts/data_quality_report.txt")
    print(f"  - artifacts/consistency_warnings.txt (if warnings)")
    print(f"  - artifacts/support_resistance_zones.txt")
    
    print(f"\n{'='*80}")
    if archive_dir:
        print(f"Run #{archived_run_num} archived")
    else:
        print("Run updated (not archived - SAVE_TO_RUN_OLD is False)")

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
