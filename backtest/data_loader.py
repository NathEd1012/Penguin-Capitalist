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
    def describe_corporate_action_near(symbol, timestamp, window_days=2, action_types=None):
        return None
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

    try:
        from scripts.corporate_actions import describe_corporate_action_near  # type: ignore
    except Exception:
        from scripts.corporate_actions import describe_corporate_action_near  # type: ignore

# Load environment variables from .env file
load_dotenv()

QUALITY_OK = "OK"
QUALITY_MISSING_PREV = "MISSING_PREV"
QUALITY_SYNTHETIC_JUMP = "SYNTHETIC_JUMP"
QUALITY_CORPORATE_ACTION = "CORPORATE_ACTION"
QUALITY_SPLIT_SUSPECT = QUALITY_CORPORATE_ACTION
QUALITY_OUTLIER = "OUTLIER"

EVENT_CORPORATE_ACTION = "CORPORATE_ACTION"
EVENT_ONE_BAR_OUTLIER = "ONE_BAR_OUTLIER"
EVENT_UNRESOLVED_INCONSISTENCY = "UNRESOLVED_INCONSISTENCY"

DEFAULT_MAX_UNEXPLAINED_JUMP_PCT = 0.08

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
        self.last_resolved_bars: Dict[str, List[Dict[str, object]]] = {}
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
            adjusted_row = dict(row)

            cumulative_factor = 1.0
            for effective_ts, factor, _event in adjustments:
                if timestamp < effective_ts:
                    cumulative_factor *= factor

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
    def _anomaly_threshold() -> float:
        """Return the global unexplained one-bar jump threshold."""
        try:
            return float(
                os.environ.get(
                    "DATA_CONSISTENCY_MAX_JUMP_PCT",
                    str(DEFAULT_MAX_UNEXPLAINED_JUMP_PCT),
                )
            )
        except ValueError:
            return DEFAULT_MAX_UNEXPLAINED_JUMP_PCT

    def _annotate_data_quality(self, symbol: str, rows: Dict) -> Dict:
        """Attach a per-bar quality flag and record any quarantined bars."""
        annotated_rows: Dict = {}
        removed_bars: List[Dict[str, object]] = []
        resolved_bars: List[Dict[str, object]] = []

        if not rows:
            self.last_removed_bars[symbol] = []
            self.last_resolved_bars[symbol] = []
            return annotated_rows

        timestamps = sorted(rows.keys())
        threshold = self._anomaly_threshold()
        previous_timestamp = None
        previous_quality = None
        quarantine_after_unexplained_jump = os.environ.get(
            "DATA_CONSISTENCY_QUARANTINE_AFTER_JUMP",
            "1",
        ).lower() in ("1", "true", "yes")
        quarantined_series_detail = ""
        reported_outlier_events = set()
        reported_corporate_actions = set()
        active_unresolved_event: Optional[Dict[str, object]] = None

        def _format_action_detail(event: Dict[str, str]) -> str:
            event_type = str(event.get("type", "corporate_action")).replace("_", " ")
            ratio = event.get("ratio", "")
            ratio_text = f" {ratio}" if ratio else ""
            comment = event.get("comment", "").strip()
            suffix = f" ({comment})" if comment else ""
            return f"{event_type}{ratio_text} on {event.get('date', 'unknown date')}{suffix}"

        for effective_ts, _factor, event in get_price_adjustment_events(symbol):
            if timestamps[0] <= effective_ts <= timestamps[-1]:
                detail = (
                    describe_corporate_action_near(
                        symbol,
                        effective_ts,
                        window_days=2,
                        action_types={"split", "reverse_split"},
                    )
                    or _format_action_detail(event)
                )
                resolved_bars.append(
                    {
                        "timestamp": effective_ts,
                        "symbol": symbol,
                        "reason": QUALITY_CORPORATE_ACTION,
                        "category": EVENT_CORPORATE_ACTION,
                        "detail": detail,
                    }
                )
                reported_corporate_actions.add(detail)

        def _jump_detail(jump_pct: float) -> str:
            if jump_pct > 0.50:
                return f"one-bar jump {jump_pct:.2%} exceeded 50% hard cap"
            return f"jump {jump_pct:.2%} above {threshold:.2%} threshold"

        def _is_one_bar_outlier(index: int, prev_close: float, curr_close: float) -> Tuple[bool, float]:
            if index + 1 >= len(timestamps) or prev_close <= 0 or curr_close <= 0:
                return False, 0.0

            next_row = rows[timestamps[index + 1]]
            next_close = float(next_row.get("close", 0.0))
            if next_close <= 0:
                return False, 0.0

            next_vs_prev = abs(next_close / prev_close - 1.0)
            next_vs_curr = abs(next_close / curr_close - 1.0)
            return next_vs_prev <= threshold and next_vs_curr > threshold, next_vs_prev

        def _finish_unresolved_event() -> None:
            nonlocal active_unresolved_event
            if active_unresolved_event is None:
                return

            affected_bars = int(active_unresolved_event.get("affected_bars", 0))
            if affected_bars > 1:
                event_key = (
                    active_unresolved_event.get("category"),
                    active_unresolved_event.get("timestamp"),
                    active_unresolved_event.get("detail"),
                )
                if event_key not in reported_outlier_events:
                    removed_bars.append(dict(active_unresolved_event))
                    reported_outlier_events.add(event_key)

            active_unresolved_event = None

        def _start_unresolved_event(
            timestamp,
            row: Dict[str, object],
            reason_detail: str,
            jump_pct: float,
            prev_close: float,
            curr_close: float,
        ) -> None:
            nonlocal active_unresolved_event
            _finish_unresolved_event()
            active_unresolved_event = {
                "timestamp": timestamp,
                "end_timestamp": timestamp,
                "symbol": symbol,
                "reason": QUALITY_OUTLIER,
                "category": EVENT_UNRESOLVED_INCONSISTENCY,
                "affected_bars": 1,
                "close": float(row.get("close", 0.0)),
                "end_close": float(row.get("close", 0.0)),
                "previous_close": prev_close,
                "current_close": curr_close,
                "jump_pct": jump_pct,
                "detail": reason_detail,
            }

        for index, timestamp in enumerate(timestamps):
            row = dict(rows[timestamp])
            quality = QUALITY_OK
            reason_detail = ""
            event_category = ""

            if quarantined_series_detail:
                quality = QUALITY_OUTLIER
                reason_detail = quarantined_series_detail
                if active_unresolved_event is not None:
                    active_unresolved_event["affected_bars"] = (
                        int(active_unresolved_event.get("affected_bars", 0)) + 1
                    )
                    active_unresolved_event["end_timestamp"] = timestamp
                    active_unresolved_event["end_close"] = float(row.get("close", 0.0))
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
                    event_category = EVENT_UNRESOLVED_INCONSISTENCY
                    _start_unresolved_event(timestamp, row, reason_detail, 0.0, prev_close, curr_close)
                else:
                    jump_pct = abs(curr_close / prev_close - 1.0)
                    if jump_pct > threshold:
                        if has_corporate_action_near(
                            symbol=symbol,
                            timestamp=timestamp,
                            window_days=2,
                            action_types={"split", "reverse_split"},
                        ):
                            quality = QUALITY_CORPORATE_ACTION
                            reason_detail = (
                                f"jump {jump_pct:.2%} near known split/reverse-split event"
                            )
                            action_detail = describe_corporate_action_near(
                                symbol,
                                timestamp,
                                window_days=2,
                                action_types={"split", "reverse_split"},
                            )
                            if action_detail and action_detail not in reported_corporate_actions:
                                resolved_bars.append(
                                    {
                                        "timestamp": timestamp,
                                        "symbol": symbol,
                                        "reason": QUALITY_CORPORATE_ACTION,
                                        "category": EVENT_CORPORATE_ACTION,
                                        "detail": action_detail,
                                    }
                                )
                                reported_corporate_actions.add(action_detail)
                        elif previous_quality == QUALITY_MISSING_PREV:
                            quality = QUALITY_SYNTHETIC_JUMP
                            reason_detail = (
                                f"jump {jump_pct:.2%} immediately after missing history"
                            )
                        else:
                            is_single_bar, revert_pct = _is_one_bar_outlier(
                                index,
                                prev_close,
                                curr_close,
                            )
                            quality = QUALITY_OUTLIER
                            if is_single_bar:
                                event_category = EVENT_ONE_BAR_OUTLIER
                                reason_detail = (
                                    f"one-bar outlier {jump_pct:.2%}; next bar reverted "
                                    f"to within {revert_pct:.2%} of previous close"
                                )
                            else:
                                event_category = EVENT_UNRESOLVED_INCONSISTENCY
                                reason_detail = _jump_detail(jump_pct)
                                _start_unresolved_event(
                                    timestamp,
                                    row,
                                    reason_detail,
                                    jump_pct,
                                    prev_close,
                                    curr_close,
                                )
                                if quarantine_after_unexplained_jump:
                                    quarantined_series_detail = (
                                        f"after unresolved jump {jump_pct:.2%} at {timestamp.isoformat()}"
                                    )

            row["data_quality"] = quality
            if reason_detail:
                row["quality_reason"] = reason_detail
            if quality == QUALITY_CORPORATE_ACTION:
                _finish_unresolved_event()
                action_detail = (
                    describe_corporate_action_near(
                        symbol,
                        timestamp,
                        window_days=2,
                        action_types={"split", "reverse_split"},
                    )
                    or reason_detail
                )
                if action_detail not in reported_corporate_actions:
                    resolved_bars.append(
                        {
                            "timestamp": timestamp,
                            "symbol": symbol,
                            "reason": quality,
                            "category": EVENT_CORPORATE_ACTION,
                            "close": float(row.get("close", 0.0)),
                            "detail": action_detail,
                        }
                    )
                    reported_corporate_actions.add(action_detail)
                annotated_rows[timestamp] = row
                previous_timestamp = timestamp
                previous_quality = quality
                continue

            if quality == QUALITY_OUTLIER:
                if event_category == EVENT_ONE_BAR_OUTLIER:
                    event_key = (quality, reason_detail)
                    if event_key not in reported_outlier_events:
                        removed_bars.append(
                            {
                                "timestamp": timestamp,
                                "symbol": symbol,
                                "reason": quality,
                                "category": EVENT_ONE_BAR_OUTLIER,
                                "close": float(row.get("close", 0.0)),
                                "detail": reason_detail,
                            }
                        )
                        reported_outlier_events.add(event_key)
                continue

            _finish_unresolved_event()
            annotated_rows[timestamp] = row
            previous_timestamp = timestamp
            previous_quality = quality

        _finish_unresolved_event()
        self.last_removed_bars[symbol] = removed_bars
        self.last_resolved_bars[symbol] = resolved_bars
        return annotated_rows

    def get_quality_report_text(self) -> str:
        """Return residual price-jump inconsistencies detected during data fetching."""
        if not self.last_removed_bars and not self.last_resolved_bars:
            return ""

        corporate_actions: List[Dict[str, object]] = []
        one_bar_outliers: List[Dict[str, object]] = []
        unresolved_inconsistencies: List[Dict[str, object]] = []

        def _ts_text(value: object) -> str:
            return value.isoformat() if hasattr(value, "isoformat") else str(value)

        def _short_float(value: object) -> str:
            try:
                return f"{float(value):.4g}"
            except (TypeError, ValueError):
                return "n/a"

        all_symbols = sorted(set(self.last_removed_bars) | set(self.last_resolved_bars))
        for symbol in all_symbols:
            resolved = self.last_resolved_bars.get(symbol, [])
            unresolved = self.last_removed_bars.get(symbol, [])

            for item in resolved:
                if item.get("category") == EVENT_CORPORATE_ACTION:
                    corporate_actions.append(item)

            for item in unresolved:
                category = item.get("category")
                if category == EVENT_ONE_BAR_OUTLIER:
                    one_bar_outliers.append(item)
                elif category == EVENT_UNRESOLVED_INCONSISTENCY:
                    if int(item.get("affected_bars", 1)) > 1:
                        unresolved_inconsistencies.append(item)

        if not corporate_actions and not one_bar_outliers and not unresolved_inconsistencies:
            return ""

        lines = [
            "Data consistency events",
            "=" * 72,
            "Known corporate actions and one-bar outliers are summarized below.",
            "Unresolved inconsistencies are shown only when they persist for more than one bar.",
            "",
        ]

        if corporate_actions:
            lines.append("Corporate actions:")
            for item in corporate_actions:
                lines.append(
                    f"  - {item.get('symbol')} | {_ts_text(item.get('timestamp'))} | "
                    f"{item.get('detail', 'known corporate action')}"
                )
            lines.append("")

        if one_bar_outliers:
            lines.append("One-bar outliers:")
            for item in one_bar_outliers:
                lines.append(
                    f"  - {item.get('symbol')} | {_ts_text(item.get('timestamp'))} | "
                    f"{item.get('detail', 'one-bar outlier')} | close={_short_float(item.get('close'))}"
                )
            lines.append("")

        if unresolved_inconsistencies:
            lines.append("Unresolved inconsistencies (>1 bar):")
            for item in unresolved_inconsistencies:
                affected_bars = int(item.get("affected_bars", 0))
                lines.append(
                    f"  - {item.get('symbol')} | {_ts_text(item.get('timestamp'))}"
                    f" -> {_ts_text(item.get('end_timestamp'))} | {affected_bars} bars | "
                    f"{item.get('detail', 'unresolved price jump')} | "
                    f"first_close={_short_float(item.get('close'))}, "
                    f"last_close={_short_float(item.get('end_close'))}"
                )
            lines.append("")

        unresolved_bars = sum(int(item.get("affected_bars", 0)) for item in unresolved_inconsistencies)
        lines.append(
            "Totals: "
            f"corporate_actions={len(corporate_actions)}, "
            f"one_bar_outliers={len(one_bar_outliers)}, "
            f"unresolved_inconsistencies={len(unresolved_inconsistencies)}, "
            f"unresolved_affected_bars={unresolved_bars}"
        )
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
        enable_data_quality_checks: bool = True,
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
        self.last_resolved_bars = {}
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

                if enable_data_quality_checks:
                    selected_rows = self._select_price_basis(symbol, symbol_rows)
                    annotated_rows = self._annotate_data_quality(symbol, selected_rows)

                    summary = defaultdict(int)
                    for row in annotated_rows.values():
                        summary[str(row.get("data_quality", QUALITY_OK))] += 1
                    self.last_quality_summary[symbol] = dict(summary)
                else:
                    annotated_rows = symbol_rows
                    self.last_quality_summary[symbol] = {}

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
