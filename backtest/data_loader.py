"""Data loader for historical market data from Alpaca."""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pytz
from dotenv import load_dotenv
from tqdm import tqdm
from market_data.cache import DataCache
from corporate_actions import get_price_adjustment_events

# Load environment variables from .env file
load_dotenv()

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
        
        if not api_key or not secret_key:
            raise ValueError(
                "Missing Alpaca API credentials.\n"
                "Please set APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables,\n"
                "or ensure .env file has ALPACA_API_KEY and ALPACA_SECRET_KEY."
            )
        
        self.client = StockHistoricalDataClient(api_key, secret_key)
        # Repeated runs with identical ranges should be served from disk cache.
        self.cache = DataCache("data_cache")
    
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
            return TimeFrame.FiveMin, 5
        elif binning == "15m":
            return TimeFrame.FifteenMin, 15
        elif binning == "1h":
            return TimeFrame.Hour, 60
        elif binning == "1d":
            return TimeFrame.Day, 1440
        else:
            raise ValueError(f"Unsupported binning: {binning}. Use '1m', '5m', '15m', '1h', or '1d'")

    def _apply_price_adjustments(self, symbol: str, rows: Dict) -> Dict:
        """Apply known split adjustments so the historical series stays on one scale."""
        adjustments = get_price_adjustment_events(symbol)
        if not adjustments or not rows:
            return rows

        adjusted_rows: Dict = {}
        for timestamp, row in rows.items():
            adjusted_row = dict(row)

            cumulative_factor = 1.0
            for effective_ts, factor, _event in adjustments:
                if timestamp >= effective_ts:
                    cumulative_factor *= factor

            if cumulative_factor != 1.0:
                adjusted_row["open"] *= cumulative_factor
                adjusted_row["high"] *= cumulative_factor
                adjusted_row["low"] *= cumulative_factor
                adjusted_row["close"] *= cumulative_factor

            adjusted_rows[timestamp] = adjusted_row

        return adjusted_rows

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
    ) -> Tuple[Dict[str, Dict], str]:
        """
        Load historical bars for symbols.
        
        Args:
            symbols: List of stock symbols
            start_date: Start datetime
            end_date: End datetime
            binning: Timeframe string ("1m", "5m", "15m", "1h", "1d")
        
        Returns:
            (data_dict, warning_message)
            - data_dict: Dict[symbol][timestamp] = bar data (o, h, l, c, v)
            - warning_message: String with info about actual data range if sparse
        """
        tf, minutes_per_bar = self._binning_to_timeframe(binning)

        def _fetch_symbol(symbol: str) -> Dict:
            def _df_to_symbol_rows(df: Optional[pd.DataFrame]) -> Dict:
                out: Dict = {}
                if df is None or df.empty:
                    return out
                for row in df.itertuples(index=False):
                    ts = row.timestamp
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=pytz.UTC)
                    out[ts] = {
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close),
                        "volume": int(row.volume),
                    }
                return out

            def _fetch_range(range_start: datetime, range_end: datetime) -> Dict:
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
                    )

                    bars = self.client.get_stock_bars(request)
                    if not bars.df.empty:
                        # Alpaca usually returns MultiIndex (symbol, timestamp).
                        if symbol in bars.df.index.get_level_values(0):
                            symbol_data = bars.df.xs(symbol, level=0)
                        else:
                            # Fallback for single-index return shapes.
                            symbol_data = bars.df

                        for timestamp, row in symbol_data.iterrows():
                            if timestamp.tzinfo is None:
                                timestamp = timestamp.replace(tzinfo=pytz.UTC)
                            fetched_rows[timestamp] = {
                                "open": float(row["open"]),
                                "high": float(row["high"]),
                                "low": float(row["low"]),
                                "close": float(row["close"]),
                                "volume": int(row["volume"]),
                            }

                    # Advance by one bar to avoid infinite loops on inclusive boundaries.
                    window_start = window_end + timedelta(minutes=minutes_per_bar)

                return fetched_rows

            cache_bounds = self.cache.get_cache_bounds(symbol, binning)
            cached_slice_df = self.cache.get_cached_slice(symbol, binning, start_date, end_date)
            symbol_rows = _df_to_symbol_rows(cached_slice_df)

            missing_rows: Dict = {}
            if cache_bounds is None:
                # No cache available: fetch requested range.
                missing_rows.update(_fetch_range(start_date, end_date))
            else:
                cache_start, cache_end = cache_bounds
                # Fetch missing head segment.
                if start_date < cache_start:
                    head_end = min(end_date, cache_start)
                    missing_rows.update(_fetch_range(start_date, head_end))
                # Fetch missing tail segment.
                if end_date > cache_end:
                    tail_start = max(start_date, cache_end)
                    missing_rows.update(_fetch_range(tail_start, end_date))

            symbol_rows.update(missing_rows)
            adjusted_rows = self._apply_price_adjustments(symbol, symbol_rows)

            # Persist only newly fetched raw rows so cache grows incrementally.
            if missing_rows:
                fetched_df = self._rows_to_dataframe(missing_rows)
                existing_df = self.cache.load_cache(symbol, binning)

                if existing_df is None or existing_df.empty:
                    self.cache.save_cache(symbol, binning, fetched_df)
                else:
                    self.cache.merge_cache_and_new_data(symbol, binning, existing_df, fetched_df)

            return adjusted_rows
        
        print(f"Fetching data for {len(symbols)} symbols from {start_date} to {end_date}...")

        data = {symbol: {} for symbol in symbols}
        all_timestamps = set()

        # Too much parallelism triggers provider-side throttling on repeated runs.
        max_workers = min(4, max(1, len(symbols)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_symbol, symbol): symbol for symbol in symbols}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Fetching/organizing data"):
                symbol = futures[future]
                try:
                    symbol_rows = future.result()
                except Exception:
                    # Keep symbol empty if API call failed; stale-data filter will handle it.
                    symbol_rows = {}

                data[symbol] = symbol_rows
                all_timestamps.update(symbol_rows.keys())
        
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
    
    def detect_stale_data(
        self,
        data: Dict[str, Dict],
        lookback_bars: int = 10,
        min_volume_threshold: float = 100,
    ) -> Tuple[List[str], List[str]]:
        """
        Detect symbols with stale or insufficient data for historical backtesting.
        
        Args:
            data: Data dictionary from load_bars
            lookback_bars: Number of of recent bars to check (default 10 for 1-minute bars)
            min_volume_threshold: Minimum average volume threshold
        
        Returns:
            (valid_symbols, stale_symbols)
        """
        valid_symbols = []
        stale_symbols = []
        
        for symbol, bars_dict in data.items():
            # No data at all
            if not bars_dict:
                stale_symbols.append(symbol)
                continue
            
            timestamps = sorted(bars_dict.keys())
            
            # Check for minimum data points
            # For historical backtest, require at least 50% of requested bars
            if len(timestamps) < max(3, lookback_bars // 2):
                stale_symbols.append(symbol)
                continue
            
            # Get recent bars for volume check
            recent_bars = [bars_dict[ts] for ts in timestamps[-lookback_bars:]]
            
            # Check volume (average volume across recent bars)
            avg_volume = sum(b['volume'] for b in recent_bars) / len(recent_bars)
            if avg_volume < min_volume_threshold:
                stale_symbols.append(symbol)
                continue
            
            valid_symbols.append(symbol)
        
        return valid_symbols, stale_symbols
