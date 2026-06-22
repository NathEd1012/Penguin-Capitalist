"""Data loader for historical market data from Alpaca."""
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pytz
from dotenv import load_dotenv
from tqdm import tqdm
from market_data.cache import DataCache

# Conditionally import corporate-action helper. If IGNORE_CORPORATE_ACTIONS is set,
# provide a no-op fallback to avoid import-time errors or unnecessary processing.
if os.environ.get("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
    def get_price_adjustment_events(symbol: str):
        return []
    def has_corporate_action_near(symbol, timestamp, window_days=2, action_types=None):
        return False
else:
    # Import the corporate-action helpers from the scripts package.
    try:
        from scripts.corporate_actions import get_price_adjustment_events  # type: ignore
    except Exception:
        from scripts.corporate_actions import get_price_adjustment_events  # type: ignore

    try:
        from scripts.corporate_actions import has_corporate_action_near  # type: ignore
    except Exception:
        from scripts.corporate_actions import has_corporate_action_near  # type: ignore

# Load environment variables from .env file
load_dotenv()

QUALITY_OK = "OK"
QUALITY_MISSING_PREV = "MISSING_PREV"
QUALITY_SYNTHETIC_JUMP = "SYNTHETIC_JUMP"
QUALITY_SPLIT_SUSPECT = "SPLIT_SUSPECT"
QUALITY_OUTLIER = "OUTLIER"

DEFAULT_MAX_UNEXPLAINED_JUMP_PCT = 0.15

STRICT_ANOMALY_SYMBOLS = {
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLI",
    "XLP",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "ORCL",
    "ADBE",
    "CRM",
    "CSCO",
    "AMD",
    "QCOM",
    "TXN",
    "INTU",
    "NOW",
    "AMAT",
    "MU",
    "INTC",
    "LLY",
    "UNH",
    "JNJ",
    "JPM",
    "BAC",
    "WMT",
    "COST",
    "XOM",
    "CVX",
    "HD",
    "MCD",
    "KO",
    "PEP",
}

VOLATILE_ANOMALY_SYMBOLS = {
    "COIN",
    "SOFI",
    "AFRM",
    "HOOD",
    "UPST",
    "AI",
    "PATH",
    "RBLX",
    "MSTR",
    "RIOT",
    "MARA",
    "CAN",
    "GREE",
    "RIVN",
    "LCID",
    "NIO",
    "XPEV",
    "LI",
    "CVNA",
    "DKNG",
    "PENN",
    "CHWY",
    "W",
    "FSLY",
    "PLUG",
    "FCEL",
    "BLDP",
    "BE",
    "MRNA",
    "BNTX",
    "DNA",
    "CRSP",
    "EDIT",
    "NTLA",
    "BEAM",
    "BLUE",
    "ARCT",
    "SGEN",
}

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
        # Resolve cache path relative to project root (Penguin-Capitalist folder)
        project_root = Path(__file__).parent.parent
        cache_dir = project_root / "data_cache"
        self.cache = DataCache(str(cache_dir))
        self.last_removed_bars: Dict[str, List[Dict[str, object]]] = {}
        self.last_quality_summary: Dict[str, Dict[str, int]] = {}
    
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
        """Apply known split adjustments so the historical series stays on one scale.
        
        For timestamps BEFORE a split: multiply by split_factor (e.g., 10 for 10:1 split)
        to bring historical prices up to post-split levels.
        
        For timestamps ON or AFTER a split: multiply by 1/split_factor to bring
        post-split prices down to a normalized historical scale.
        """
        # Allow disabling corporate-action adjustments for quick experiments
        if os.environ.get("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
            return rows

        adjustments = get_price_adjustment_events(symbol)
        if not adjustments or not rows:
            return rows

        adjusted_rows: Dict = {}
        for timestamp, row in rows.items():
            adjusted_row = dict(row)

            cumulative_factor = 1.0
            for effective_ts, factor, _event in adjustments:
                if timestamp < effective_ts:
                    # Before split: multiply by factor to normalize historical prices
                    cumulative_factor *= factor
                else:
                    # On or after split: divide by factor (multiply by 1/factor)
                    cumulative_factor *= (1.0 / factor)

            if cumulative_factor != 1.0:
                adjusted_row["open"] *= cumulative_factor
                adjusted_row["high"] *= cumulative_factor
                adjusted_row["low"] *= cumulative_factor
                adjusted_row["close"] *= cumulative_factor

            adjusted_rows[timestamp] = adjusted_row

        return adjusted_rows

    def _corporate_action_boundary_score(self, symbol: str, rows: Dict) -> float:
        """Score discontinuities around known split boundaries."""
        if not rows:
            return 0.0

        adjustments = get_price_adjustment_events(symbol)
        if not adjustments:
            return 0.0

        timestamps = sorted(rows.keys())
        score = 0.0
        for effective_ts, _factor, _event in adjustments:
            before_candidates = [ts for ts in timestamps if ts < effective_ts]
            after_candidates = [ts for ts in timestamps if ts >= effective_ts]
            if not before_candidates or not after_candidates:
                continue

            before_ts = before_candidates[-1]
            after_ts = after_candidates[0]
            before_close = float(rows[before_ts]["close"])
            after_close = float(rows[after_ts]["close"])
            if before_close > 0 and after_close > 0:
                score += abs(after_close / before_close - 1.0)

        return score

    def _select_price_basis(self, symbol: str, rows: Dict) -> Dict:
        """Choose the smoother of raw vs split-adjusted prices for a symbol."""
        if os.environ.get("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
            return rows

        adjusted_rows = self._apply_price_adjustments(symbol, rows)
        if adjusted_rows is rows or not adjusted_rows:
            return rows

        raw_score = self._corporate_action_boundary_score(symbol, rows)
        adjusted_score = self._corporate_action_boundary_score(symbol, adjusted_rows)

        if adjusted_score + 1e-9 < raw_score:
            return adjusted_rows
        return rows

    @staticmethod
    def _anomaly_threshold_for_symbol(symbol: str) -> float:
        try:
            default_threshold = float(
                os.environ.get(
                    "DATA_CONSISTENCY_MAX_JUMP_PCT",
                    str(DEFAULT_MAX_UNEXPLAINED_JUMP_PCT),
                )
            )
        except ValueError:
            default_threshold = DEFAULT_MAX_UNEXPLAINED_JUMP_PCT

        if os.environ.get("DATA_CONSISTENCY_USE_SYMBOL_THRESHOLDS", "").lower() not in ("1", "true", "yes"):
            return default_threshold

        normalized = symbol.strip().upper()
        if normalized in STRICT_ANOMALY_SYMBOLS:
            return 0.09
        if normalized in VOLATILE_ANOMALY_SYMBOLS:
            return 0.25
        return default_threshold

    def _annotate_data_quality(self, symbol: str, rows: Dict) -> Dict:
        """Attach a per-bar quality flag and record any quarantined bars."""
        annotated_rows: Dict = {}
        removed_bars: List[Dict[str, object]] = []

        if not rows:
            self.last_removed_bars[symbol] = []
            return annotated_rows

        timestamps = sorted(rows.keys())
        threshold = self._anomaly_threshold_for_symbol(symbol)
        previous_timestamp = None
        previous_quality = None
        quarantine_after_unexplained_jump = os.environ.get(
            "DATA_CONSISTENCY_QUARANTINE_AFTER_JUMP",
            "1",
        ).lower() in ("1", "true", "yes")
        quarantined_series_detail = ""

        for index, timestamp in enumerate(timestamps):
            row = dict(rows[timestamp])
            quality = QUALITY_OK
            reason_detail = ""

            if quarantined_series_detail:
                quality = QUALITY_OUTLIER
                reason_detail = quarantined_series_detail
            elif index == 0:
                quality = QUALITY_MISSING_PREV
                reason_detail = "first bar has no prior history"
            else:
                prev_row = rows[previous_timestamp]
                prev_close = float(prev_row.get("close", 0.0))
                curr_close = float(row.get("close", 0.0))

                if prev_close <= 0 or curr_close <= 0:
                    quality = QUALITY_OUTLIER
                    reason_detail = "non-positive price in one-bar comparison"
                else:
                    jump_pct = abs(curr_close / prev_close - 1.0)
                    if jump_pct > 0.50:
                        quality = QUALITY_OUTLIER
                        reason_detail = f"one-bar jump {jump_pct:.2%} exceeded 50% hard cap"
                    elif jump_pct > threshold:
                        if has_corporate_action_near(
                            symbol=symbol,
                            timestamp=timestamp,
                            window_days=2,
                            action_types={"split", "reverse_split"},
                        ):
                            quality = QUALITY_SPLIT_SUSPECT
                            reason_detail = (
                                f"jump {jump_pct:.2%} near known split/reverse-split event"
                            )
                        elif previous_quality == QUALITY_MISSING_PREV:
                            quality = QUALITY_SYNTHETIC_JUMP
                            reason_detail = (
                                f"jump {jump_pct:.2%} immediately after missing history"
                            )
                        else:
                            quality = QUALITY_OUTLIER
                            reason_detail = f"jump {jump_pct:.2%} above {threshold:.2%} threshold"
                            if quarantine_after_unexplained_jump:
                                quarantined_series_detail = (
                                    f"after unexplained jump {jump_pct:.2%} at {timestamp.isoformat()}"
                                )

            row["data_quality"] = quality
            if reason_detail:
                row["quality_reason"] = reason_detail
            annotated_rows[timestamp] = row

            if quality != QUALITY_OK:
                removed_bars.append(
                    {
                        "timestamp": timestamp,
                        "reason": quality,
                        "close": float(row.get("close", 0.0)),
                        "detail": reason_detail,
                    }
                )

            previous_timestamp = timestamp
            previous_quality = quality

        self.last_removed_bars[symbol] = removed_bars
        return annotated_rows

    def get_quality_report_text(self) -> str:
        """Return a compact human-readable report of quarantined bars."""
        if not self.last_removed_bars:
            return "Historical data quality report: no quarantined bars detected."

        lines = ["Historical data quality report", "=" * 40]
        total_removed = 0

        for symbol in sorted(self.last_removed_bars):
            removed = self.last_removed_bars.get(symbol, [])
            if not removed:
                continue

            visible_removed = [item for item in removed if item.get("reason") != QUALITY_MISSING_PREV]
            if not visible_removed:
                continue

            total_removed += len(visible_removed)
            reason_counts = defaultdict(int)
            for item in visible_removed:
                reason_counts[str(item.get("reason", "UNKNOWN"))] += 1

            lines.append(f"{symbol}: {len(visible_removed)} quarantined bar(s)")
            for reason, count in sorted(reason_counts.items()):
                lines.append(f"  - {reason}: {count}")

            for item in visible_removed[:5]:
                timestamp = item.get("timestamp")
                ts_text = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
                detail = item.get("detail", "")
                lines.append(f"    * {ts_text} | {item.get('reason')} | {detail}")

        lines.append(f"Total quarantined bars: {total_removed}")
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

    @staticmethod
    def _freshness_probe_start(
        start_date: datetime,
        end_date: datetime,
        minutes_per_bar: int,
    ) -> datetime:
        """Return a recent range start that is cheap but wide enough for market closures."""
        if minutes_per_bar >= 1440:
            probe_window = timedelta(days=90)
        elif minutes_per_bar >= 60:
            probe_window = timedelta(days=30)
        else:
            probe_window = timedelta(days=14)

        probe_start = end_date - probe_window
        return max(start_date, probe_start)

    @staticmethod
    def _stale_reason_for_rows(
        bars_dict: Dict,
        lookback_bars: int = 10,
        min_volume_threshold: float = 100,
    ) -> Optional[str]:
        """Return None for tradable recent rows, otherwise a compact stale reason."""
        if not bars_dict:
            return "no data"

        timestamps = sorted(bars_dict.keys())
        if len(timestamps) < max(3, lookback_bars // 2):
            return "insufficient bars"

        recent_bars = [bars_dict[ts] for ts in timestamps[-lookback_bars:]]
        avg_volume = sum(bar["volume"] for bar in recent_bars) / len(recent_bars)
        if avg_volume < min_volume_threshold:
            return "low recent volume"

        return None
    
    def load_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        binning: str = "1m",
        prefilter_stale_symbols: bool = True,
    ) -> Tuple[Dict[str, Dict], str]:
        """
        Load historical bars for symbols.
        
        Args:
            symbols: List of stock symbols
            start_date: Start datetime
            end_date: End datetime
            binning: Timeframe string ("1m", "5m", "15m", "1h", "1d")
            prefilter_stale_symbols: Check a small recent window before loading long ranges
        
        Returns:
            (data_dict, warning_message)
            - data_dict: Dict[symbol][timestamp] = bar data (o, h, l, c, v)
            - warning_message: String with info about actual data range if sparse
        """
        tf, minutes_per_bar = self._binning_to_timeframe(binning)
        self.last_removed_bars = {}
        self.last_quality_summary = {}
        fetch_errors = []

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
                        fetched_rows[timestamp] = {
                            "open": float(row.open),
                            "high": float(row.high),
                            "low": float(row.low),
                            "close": float(row.close),
                            "volume": int(row.volume),
                        }

                # Advance by one bar to avoid infinite loops on inclusive boundaries.
                window_start = window_end + timedelta(minutes=minutes_per_bar)

            return fetched_rows

        def _safe_fetch_range(symbol: str, range_start: datetime, range_end: datetime) -> Dict:
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
            if cache_bounds is None:
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
        stale_reasons = defaultdict(int)

        # Native client / dataframe handling has been unstable under higher thread fan-out on large symbol sets.
        # Keep the default conservative, but allow an override for controlled experiments.
        try:
            max_workers = int(os.environ.get("DATA_LOADER_MAX_WORKERS", "1"))
        except ValueError:
            max_workers = 1
        max_workers = max(1, min(max_workers, len(symbols)))

        probe_start = self._freshness_probe_start(start_date, end_date, minutes_per_bar)
        full_symbols = list(symbols)
        use_prefilter = prefilter_stale_symbols and probe_start > start_date

        if use_prefilter:
            print(f"Prechecking recent data from {probe_start} to {end_date}...")
            fresh_symbols = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(_load_symbol_range, symbol, probe_start, end_date, False): symbol
                    for symbol in symbols
                }
                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Checking recent data",
                    mininterval=30,
                    miniters=1,
                ):
                    symbol = futures[future]
                    try:
                        probe_rows = future.result()
                    except Exception:
                        probe_rows = {}

                    stale_reason = self._stale_reason_for_rows(probe_rows)
                    if stale_reason is None:
                        fresh_symbols.append(symbol)
                    else:
                        stale_reasons[stale_reason] += 1
                        self.last_removed_bars[symbol] = []
                        self.last_quality_summary[symbol] = {}

            skipped = len(symbols) - len(fresh_symbols)
            print(f"  Recent-data precheck kept {len(fresh_symbols)} symbol(s), skipped {skipped}.")
            if stale_reasons:
                reason_text = ", ".join(
                    f"{reason}: {count}" for reason, count in sorted(stale_reasons.items())
                )
                print(f"  Precheck stale reasons: {reason_text}")
            full_symbols = fresh_symbols

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_load_symbol_range, symbol, start_date, end_date): symbol
                for symbol in full_symbols
            }
            for future in tqdm(as_completed(futures), total=len(futures), desc="Fetching/organizing data", mininterval=60, miniters=5000):
                symbol = futures[future]
                try:
                    symbol_rows = future.result()
                except Exception:
                    # Keep symbol empty if API call failed; stale-data filter will handle it.
                    symbol_rows = {}

                selected_rows = self._select_price_basis(symbol, symbol_rows)
                annotated_rows = self._annotate_data_quality(symbol, selected_rows)

                summary = defaultdict(int)
                for row in annotated_rows.values():
                    summary[str(row.get("data_quality", QUALITY_OK))] += 1
                self.last_quality_summary[symbol] = dict(summary)

                data[symbol] = annotated_rows
                all_timestamps.update(annotated_rows.keys())

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
            if self._stale_reason_for_rows(bars_dict, lookback_bars, min_volume_threshold):
                stale_symbols.append(symbol)
                continue
            
            valid_symbols.append(symbol)
        
        return valid_symbols, stale_symbols
