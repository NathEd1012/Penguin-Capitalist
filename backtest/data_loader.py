"""Data loader for historical market data from Alpaca."""
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.enums import Adjustment
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
import pytz
from dotenv import load_dotenv
from tqdm import tqdm
from market_data.cache import DataCache
from backtest.data_cleaning import (
    CleaningPolicy, SymbolBars, annotate_quality, normalize_splits,
    prepare_market_data, pricing_symbols,
)

from scripts.data_fixes.corporate_actions import get_price_adjustment_events

# Load environment variables from .env file
load_dotenv()

def _bounded_load(executor, symbols, load, max_workers):
    """Keep at most max_workers raw symbol dictionaries awaiting cleaning."""
    iterator = iter(symbols)
    pending = {}
    for _ in range(max_workers):
        symbol = next(iterator, None)
        if symbol is not None:
            pending[executor.submit(load, symbol)] = symbol
    while pending:
        done, _ = wait(pending, return_when=FIRST_COMPLETED)
        for future in done:
            symbol = pending.pop(future)
            yield symbol, future.result()
            next_symbol = next(iterator, None)
            if next_symbol is not None:
                pending[executor.submit(load, next_symbol)] = next_symbol


class DataLoader:
    """Load historical OHLCV data from Alpaca."""
    
    def __init__(self):
        """Initialize Alpaca data client."""
        # Try standard Alpaca environment variables first
        api_key = os.environ.get("APCA_API_KEY_ID")
        secret_key = os.environ.get("APCA_API_SECRET_KEY")
        
        # Fall back to .env file naming convention
        if not api_key:
            api_key = os.environ.get("ALPACA_API_KEY")
        if not secret_key:
            secret_key = os.environ.get("ALPACA_SECRET_KEY")
        
        # Cache inspection and offline replay do not require credentials.
        self.client = StockHistoricalDataClient(api_key, secret_key) if api_key and secret_key else None
        # Repeated runs with identical ranges should be served from disk cache.
        # Use scratch when configured so large caches do not consume home quota.
        project_root = Path(__file__).parent.parent
        cache_dir = Path(
            os.environ.get("PENGUIN_DATA_CACHE_DIR", project_root / "data_cache")
        ).expanduser()
        self.cache = DataCache(str(cache_dir))
        self.last_quality_summary: Dict[str, Dict[str, int]] = {}
        self.last_price_basis_adjusted: Dict[str, bool] = {}
    
    def _binning_to_timeframe(self, binning: str) -> Tuple[TimeFrame, int]:
        """
        Convert binning string to Alpaca TimeFrame and minutes.
        
        Args:
            binning: String like "1m", "5m", "15m", "1h", "1d"
        
        Returns:
            (TimeFrame, minutes_per_bar)
        """
        binning = binning.strip().lower()
        
        if binning == "1m":
            return TimeFrame.Minute, 1
        elif binning == "5m":
            return TimeFrame(5, TimeFrameUnit.Minute), 5
        elif binning == "15m":
            return TimeFrame(15, TimeFrameUnit.Minute), 15
        elif binning == "1h":
            return TimeFrame.Hour, 60
        elif binning == "1d":
            return TimeFrame.Day, 1440
        else:
            raise ValueError(f"Unsupported binning: {binning}. Use '1m', '5m', '15m', '1h', or '1d'")

    def _apply_price_adjustments(self, symbol: str, rows: Dict) -> Dict:
        """Apply known split adjustments so the historical series stays on one scale.

        For timestamps before an event, multiply by the event's price factor
        (e.g. 0.1 for a 10-for-1 split, 20 for a 1-for-20 reverse split).
        Timestamps on or after the event already trade on the new scale.
        """
        # Allow disabling corporate-action adjustments for quick experiments
        if os.environ.get("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
            return rows

        adjustments = get_price_adjustment_events(symbol)
        if not adjustments or not rows:
            return rows

        adjusted_rows: Dict = {}
        for timestamp, row in rows.items():
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError(
                    f"Naive bar timestamp cannot be used for split processing: "
                    f"{symbol} {timestamp!s}"
                )
            timestamp_utc = timestamp.astimezone(timezone.utc)
            adjusted_row = dict(row)

            cumulative_factor = 1.0
            for effective_ts, factor, event in adjustments:
                if timestamp_utc < effective_ts:
                    cumulative_factor *= factor

            if cumulative_factor != 1.0:
                adjusted_row["open"] *= cumulative_factor
                adjusted_row["high"] *= cumulative_factor
                adjusted_row["low"] *= cumulative_factor
                adjusted_row["close"] *= cumulative_factor
                if "volume" in adjusted_row:
                    adjusted_row["volume"] /= cumulative_factor

            adjusted_rows[timestamp] = adjusted_row

        return adjusted_rows

    def _select_price_basis(self, symbol: str, rows: Dict) -> Dict:
        return normalize_splits(symbol, rows)

    def _annotate_data_quality(self, symbol: str, rows: Dict) -> Dict:
        return annotate_quality(symbol, rows, CleaningPolicy.from_environment())

    def get_quality_report_text(self) -> str:
        """Bounded per-symbol summary, rather than millions of event strings."""
        lines = ["Prepared data quality (causal checks; raw cache unchanged)"]
        for symbol, counts in sorted(self.last_quality_summary.items()):
            lines.append(f"  {symbol}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        return "\n".join(lines)

    @staticmethod
    def _rows_to_dataframe(rows: Dict) -> pd.DataFrame:
        """Convert timestamp keyed OHLCV rows into a DataFrame."""
        if not rows:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        return pd.DataFrame(
            [
                {
                    "timestamp": ts,
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
                for ts, row in rows.items()
            ]
        ).sort_values("timestamp").reset_index(drop=True)

    def load_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        binning: str = "1m",
        prefilter_stale_symbols: bool = True,
        enable_data_quality_checks: bool = True,
        refresh_cache: bool = False,
        cache_only: bool = False,
        include_dependencies: bool = True,
    ) -> Tuple[Dict[str, Dict], str]:
        """
        Load historical bars for symbols.
        
        Args:
            symbols: List of stock symbols
            start_date: Start datetime
            end_date: End datetime
            binning: Timeframe string ("1m", "5m", "15m", "1h", "1d")
            prefilter_stale_symbols: Apply causal session-coverage eligibility
            refresh_cache: Fetch the entire requested range and merge it with the cache
        
        Returns:
            (data_dict, warning_message)
            - data_dict: Dict[symbol][timestamp] = bar data (o, h, l, c, v)
            - warning_message: String with info about actual data range if sparse
        """
        requested_symbols = list(dict.fromkeys(symbols))
        symbols = pricing_symbols(requested_symbols) if include_dependencies else requested_symbols
        policy = CleaningPolicy.from_environment()
        tf, minutes_per_bar = self._binning_to_timeframe(binning)
        self.last_quality_summary = {}
        self.last_price_basis_adjusted = {}
        fetch_errors = []

        def _df_to_symbol_rows(df: Optional[pd.DataFrame]) -> Dict:
            out: Dict = {}
            if df is None or df.empty:
                return out
            for row in df.itertuples(index=False):
                ts = row.timestamp
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=pytz.UTC)
                values = {
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": float(row.volume),
                }
                if ts in out and (out[ts] != values or out[ts].get("source_conflict")):
                    values["source_conflict"] = True
                out[ts] = values
            return out

        def _fetch_range(symbol: str, range_start: datetime, range_end: datetime) -> Dict:
            fetched_rows: Dict = {}
            if range_start > range_end:
                return fetched_rows

            # Avoid API truncation at 100k bars by requesting in time chunks.
            chunk_bars_target = 90000
            chunk_minutes = max(minutes_per_bar, minutes_per_bar * chunk_bars_target)
            chunk_delta = timedelta(minutes=chunk_minutes)

            window_start = range_start
            while window_start <= range_end:
                window_end = min(window_start + chunk_delta, range_end)

                request = StockBarsRequest(
                    symbol_or_symbols=[symbol],
                    timeframe=tf,
                    start=window_start,
                    end=window_end,
                    limit=100000,
                    adjustment=Adjustment.RAW,
                )

                bars = self.client.get_stock_bars(request)
                if not bars.df.empty:
                    # Alpaca usually returns MultiIndex (symbol, timestamp).
                    if isinstance(bars.df.index, pd.MultiIndex):
                        level_symbols = bars.df.index.get_level_values(0)
                        if symbol not in level_symbols:
                            window_start = window_end + timedelta(minutes=minutes_per_bar)
                            continue
                        symbol_data = bars.df.xs(symbol, level=0)
                    else:
                        # Fallback for single-index return shapes.
                        symbol_data = bars.df

                    for row in symbol_data.itertuples(index=True):
                        timestamp = row.Index
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=pytz.UTC)
                        values = {
                            "open": float(row.open),
                            "high": float(row.high),
                            "low": float(row.low),
                            "close": float(row.close),
                            "volume": float(row.volume),
                        }
                        if timestamp in fetched_rows and fetched_rows[timestamp] != values:
                            raise ValueError(f"Conflicting provider bars: {symbol} {timestamp}")
                        fetched_rows[timestamp] = values

                # Advance by one bar to avoid infinite loops on inclusive boundaries.
                window_start = window_end + timedelta(minutes=minutes_per_bar)

            return fetched_rows

        def _safe_fetch_range(symbol: str, range_start: datetime, range_end: datetime) -> Dict:
            if cache_only:
                return {}
            if self.client is None:
                raise ValueError("Missing Alpaca credentials for uncached data; use cache_only=True for inspection")
            try:
                return _fetch_range(symbol, range_start, range_end)
            except Exception as exc:
                fetch_errors.append(
                    (
                        symbol,
                        range_start,
                        range_end,
                        f"{type(exc).__name__}: {str(exc)[:220]}",
                    )
                )
                return {}

        def _should_fetch_head_gap(range_start: datetime, cache_start: datetime) -> bool:
            """Skip tiny leading gaps caused by weekends, holidays, or premarket sparsity."""
            head_gap = cache_start - range_start
            if range_start.date() != cache_start.date() and head_gap <= timedelta(days=4):
                return False
            return True

        def _load_symbol_range(
            symbol: str,
            range_start: datetime,
            range_end: datetime,
            persist_missing: bool = True,
        ) -> Dict:
            cached_slice_df, cache_bounds = self.cache.get_cached_slice_with_bounds(
                symbol,
                binning,
                range_start,
                range_end,
            )
            symbol_rows = _df_to_symbol_rows(cached_slice_df)

            missing_rows: Dict = {}
            if refresh_cache:
                # Fetch the full frame so missing timestamps inside cache bounds are found.
                missing_rows.update(_safe_fetch_range(symbol, range_start, range_end))
            elif cache_bounds is None:
                # No cache available: fetch requested range.
                missing_rows.update(_safe_fetch_range(symbol, range_start, range_end))
            else:
                cache_start, cache_end = cache_bounds
                # Fetch missing head segment.
                if range_start < cache_start and _should_fetch_head_gap(range_start, cache_start):
                    head_end = min(range_end, cache_start)
                    missing_rows.update(_safe_fetch_range(symbol, range_start, head_end))
                # Fetch missing tail segment.
                if range_end > cache_end:
                    tail_start = max(range_start, cache_end)
                    missing_rows.update(_safe_fetch_range(symbol, tail_start, range_end))

            symbol_rows.update(missing_rows)
            # Persist only newly fetched raw rows so cache grows incrementally.
            if missing_rows and persist_missing:
                fetched_df = self._rows_to_dataframe(missing_rows)
                existing_df = None
                if cached_slice_df is not None and cache_bounds is not None:
                    cache_start, cache_end = cache_bounds
                    if range_start <= cache_start and range_end >= cache_end:
                        existing_df = cached_slice_df

                if existing_df is None:
                    existing_df = self.cache.load_cache(symbol, binning)

                if existing_df is None or existing_df.empty:
                    self.cache.save_cache(symbol, binning, fetched_df)
                else:
                    self.cache.merge_cache_and_new_data(symbol, binning, existing_df, fetched_df)

            return symbol_rows
        
        print(f"Fetching data for {len(symbols)} symbols from {start_date} to {end_date}...")

        data = {symbol: {} for symbol in symbols}
        all_timestamps = set()

        # Native client / dataframe handling has been unstable under higher thread fan-out on large symbol sets.
        # Keep the default conservative, but allow an override for controlled experiments.
        try:
            max_workers = int(os.environ.get("DATA_LOADER_MAX_WORKERS", "1"))
        except ValueError:
            max_workers = 1
        max_workers = max(1, min(max_workers, len(symbols)))

        full_symbols = list(symbols)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = _bounded_load(executor, full_symbols,
                                    lambda symbol: _load_symbol_range(symbol, start_date, end_date), max_workers)
            for symbol, symbol_rows in tqdm(results, total=len(full_symbols),
                                            desc="Loading/cleaning data", mininterval=30):
                selected_rows = self._select_price_basis(symbol, symbol_rows)
                self.last_price_basis_adjusted[symbol] = True  # canonical units; never split again at runtime

                if enable_data_quality_checks:
                    annotated_rows = self._annotate_data_quality(symbol, selected_rows)

                    summary = defaultdict(int)
                    for row in annotated_rows.values():
                        summary[str(row.get("data_quality", "OK"))] += 1
                    self.last_quality_summary[symbol] = dict(summary)
                else:
                    annotated_rows = SymbolBars(selected_rows, basis_events=selected_rows.basis_events)
                    self.last_quality_summary[symbol] = {}

                data[symbol] = annotated_rows
                all_timestamps.update(annotated_rows.keys())

        prepare_market_data(data, end_date, minutes_per_bar, policy,
                            coverage=enable_data_quality_checks and prefilter_stale_symbols)
        self.last_quality_summary = {symbol: rows.summary for symbol, rows in data.items()}

        if fetch_errors:
            print(
                f"  Warning: {len(fetch_errors)} missing cache segment fetch(es) failed; "
                "continuing with cached data where available."
            )
            for symbol, range_start, range_end, message in fetch_errors[:5]:
                print(f"    {symbol}: {range_start} to {range_end} | {message}")
        
        # Check for data sparseness and generate warning if needed
        warning_msg = ""
        if all_timestamps:
            actual_start = min(all_timestamps)
            actual_end = max(all_timestamps)
            
            # Check if actual data range differs significantly from requested range
            if actual_start > start_date or actual_end < end_date:
                warning_msg = (
                    f"\n⚠️  DATA SPARSENESS WARNING:\n"
                    f"   Requested: {start_date} to {end_date}\n"
                    f"   Actual:    {actual_start} to {actual_end}\n"
                    f"   (Using only the {len(all_timestamps)} available timestamps)\n"
                )
        
        return data, warning_msg
    
    @staticmethod
    def detect_stale_data(data: Dict[str, Dict]) -> Tuple[List[str], List[str]]:
        """Return symbols with usable observations; eligibility is per timestamp."""
        # Eligibility is prepared per timestamp, never inferred from the end of
        # a training/test slice. Keep valuation-only and historically active data.
        valid_symbols = [s for s, rows in data.items() if any(
            row.get("data_quality", "OK") == "OK" for row in rows.values())]
        return valid_symbols, [s for s in data if s not in valid_symbols]
