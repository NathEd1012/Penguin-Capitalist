"""Disk caching system for market data to avoid unnecessary API calls."""
import os
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd


class DataCache:
    """Disk-based caching using parquet files."""
    
    def __init__(self, cache_dir: str = "data_cache"):
        """
        Initialize cache.
        
        Args:
            cache_dir: Directory for cache files (default: data_cache)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._meta_cache = {}
        self._missing_meta = set()

    @staticmethod
    def _cache_key(symbol: str, timeframe: str) -> tuple:
        return symbol, timeframe

    @staticmethod
    def _normalize_dt(value):
        """Return a timezone-aware UTC datetime/Timestamp for comparisons."""
        if isinstance(value, pd.Timestamp):
            if value.tzinfo is None:
                return value.tz_localize(timezone.utc)
            return value.tz_convert(timezone.utc)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return pd.to_datetime(value, utc=True)

    @staticmethod
    def _parse_meta_timestamp(value: str) -> datetime:
        """Parse ISO metadata timestamps without the heavier pandas parser."""
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _ensure_utc_timestamp_column(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or "timestamp" not in df.columns:
            return df
        timestamp = df["timestamp"]
        needs_conversion = not pd.api.types.is_datetime64_any_dtype(timestamp)
        if not needs_conversion:
            try:
                needs_conversion = timestamp.dt.tz is None
            except AttributeError:
                needs_conversion = True
        if needs_conversion:
            df = df.copy()
            df["timestamp"] = pd.to_datetime(timestamp, utc=True)
        return df
    
    def get_cache_path(self, symbol: str, timeframe: str) -> Path:
        """Get cache file path for symbol and timeframe."""
        filename = f"{symbol}_{timeframe}.parquet"
        return self.cache_dir / filename

    def get_meta_path(self, symbol: str, timeframe: str) -> Path:
        """Get metadata sidecar path for symbol and timeframe."""
        filename = f"{symbol}_{timeframe}.meta.json"
        return self.cache_dir / filename
    
    def cache_exists(self, symbol: str, timeframe: str) -> bool:
        """Check if cache file exists."""
        return self.get_cache_path(symbol, timeframe).exists()

    def get_cache_bounds(self, symbol: str, timeframe: str):
        """Return cached timestamp bounds as (start, end) in UTC, or None."""
        path = self.get_cache_path(symbol, timeframe)
        if not path.exists():
            return None

        meta = self._load_meta(symbol, timeframe)
        if meta is not None:
            return meta["start"], meta["end"]

        # Fallback for legacy cache files without sidecar metadata.
        cached_df = self.load_cache(symbol, timeframe)
        if cached_df is None or cached_df.empty or "timestamp" not in cached_df.columns:
            return None

        cache_start = self._normalize_dt(cached_df["timestamp"].min())
        cache_end = self._normalize_dt(cached_df["timestamp"].max())
        self._write_meta(symbol, timeframe, cache_start, cache_end, len(cached_df))
        return cache_start, cache_end

    def get_cached_slice_with_bounds(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ):
        """Return (cached rows in range, cache bounds), avoiding non-overlap parquet reads."""
        path = self.get_cache_path(symbol, timeframe)
        if not path.exists():
            return None, None

        bounds = self.get_cache_bounds(symbol, timeframe)
        if bounds is None:
            return None, None

        cache_start, cache_end = bounds
        start_utc = self._normalize_dt(start)
        end_utc = self._normalize_dt(end)
        if end_utc < cache_start or start_utc > cache_end:
            return None, bounds

        return self._read_cache_range_from_path(path, start_utc, end_utc), bounds

    def get_cached_slice(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Return cached rows in [start, end] even when cache does not fully cover the range."""
        cached_df, _bounds = self.get_cached_slice_with_bounds(symbol, timeframe, start, end)
        return cached_df
    
    def load_cache(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Load cached data.
        
        Args:
            symbol: Stock symbol
            timeframe: Candle interval
        
        Returns:
            DataFrame or None if cache doesn't exist
        """
        path = self.get_cache_path(symbol, timeframe)
        if not path.exists():
            return None
        
        try:
            df = pd.read_parquet(path)
            # Ensure timestamp is datetime
            df = self._ensure_utc_timestamp_column(df)
            return df
        except Exception:
            # Silently return None if cache is corrupted
            return None
    
    def save_cache(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        """
        Save data to cache.
        
        Args:
            symbol: Stock symbol
            timeframe: Candle interval
            df: DataFrame to cache
        """
        path = self.get_cache_path(symbol, timeframe)
        try:
            if df is None or df.empty:
                return

            to_save = df.copy()
            if "timestamp" in to_save.columns:
                to_save["timestamp"] = pd.to_datetime(to_save["timestamp"], utc=True)
            to_save = to_save.sort_values("timestamp").reset_index(drop=True)

            to_save.to_parquet(path, index=False)

            # Persist lightweight metadata for fast range checks.
            if "timestamp" in to_save.columns and not to_save.empty:
                self._write_meta(
                    symbol,
                    timeframe,
                    to_save["timestamp"].min(),
                    to_save["timestamp"].max(),
                    int(len(to_save)),
                )
        except Exception:
            # Silently fail if cache write fails
            pass

    def _write_meta(self, symbol: str, timeframe: str, start_ts, end_ts, rows: int) -> None:
        """Write metadata sidecar. Failures are non-fatal."""
        try:
            start_utc = self._normalize_dt(start_ts)
            end_utc = self._normalize_dt(end_ts)
            meta = {
                "symbol": symbol,
                "timeframe": timeframe,
                "rows": int(rows),
                "start": start_utc.isoformat(),
                "end": end_utc.isoformat(),
            }
            self.get_meta_path(symbol, timeframe).write_text(json.dumps(meta), encoding="utf-8")
            key = self._cache_key(symbol, timeframe)
            self._meta_cache[key] = {"start": start_utc, "end": end_utc, "rows": int(rows)}
            self._missing_meta.discard(key)
        except Exception:
            pass

    def _load_meta(self, symbol: str, timeframe: str):
        """Load cache metadata sidecar if present and valid."""
        key = self._cache_key(symbol, timeframe)
        if key in self._meta_cache:
            return self._meta_cache[key]
        if key in self._missing_meta:
            return None

        meta_path = self.get_meta_path(symbol, timeframe)
        if not meta_path.exists():
            self._missing_meta.add(key)
            return None

        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            meta = {
                "start": self._parse_meta_timestamp(raw.get("start")),
                "end": self._parse_meta_timestamp(raw.get("end")),
                "rows": int(raw.get("rows", 0)),
            }
            self._meta_cache[key] = meta
            return meta
        except Exception:
            self._missing_meta.add(key)
            return None

    def _read_cache_range_from_path(
        self,
        path: Path,
        start_utc,
        end_utc,
    ) -> pd.DataFrame:
        try:
            # Use parquet filters to avoid loading the full file when backend supports it.
            df = pd.read_parquet(
                path,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
                filters=[
                    ("timestamp", ">=", start_utc),
                    ("timestamp", "<=", end_utc),
                ],
            )
        except Exception:
            # Fallback for engines that do not support pushdown filters.
            df = pd.read_parquet(path)

        if df is None or df.empty:
            return None

        df = self._ensure_utc_timestamp_column(df)
        if "timestamp" in df.columns:
            df = df[(df["timestamp"] >= start_utc) & (df["timestamp"] <= end_utc)].copy()
        return df if not df.empty else None

    def _read_cache_range(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Read only the requested timestamp range from parquet when possible."""
        path = self.get_cache_path(symbol, timeframe)
        if not path.exists():
            return None

        return self._read_cache_range_from_path(
            path,
            self._normalize_dt(start),
            self._normalize_dt(end),
        )
    
    def get_cached_data_in_range(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """
        Get cached data that covers the requested time range.
        
        Returns:
            DataFrame if cache covers the range, None otherwise
        """
        path = self.get_cache_path(symbol, timeframe)
        if not path.exists():
            return None

        start_utc = self._normalize_dt(start)
        end_utc = self._normalize_dt(end)

        meta = self._load_meta(symbol, timeframe)
        if meta is not None:
            if meta["start"] > start_utc or meta["end"] < end_utc:
                return None
            return self._read_cache_range_from_path(path, start_utc, end_utc)

        # Backward-compatible fallback for older cache files without metadata.
        cached_df = self.load_cache(symbol, timeframe)
        if cached_df is None or cached_df.empty:
            return None

        cache_start = self._normalize_dt(cached_df["timestamp"].min())
        cache_end = self._normalize_dt(cached_df["timestamp"].max())
        # One-time migration for legacy cache files without sidecar metadata.
        self._write_meta(symbol, timeframe, cache_start, cache_end, len(cached_df))
        if cache_start > start_utc or cache_end < end_utc:
            return None

        return cached_df[
            (cached_df["timestamp"] >= start_utc) & 
            (cached_df["timestamp"] <= end_utc)
        ].copy()
    
    def merge_cache_and_new_data(
        self,
        symbol: str,
        timeframe: str,
        cached_df: pd.DataFrame,
        new_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge cached and new data, avoiding duplicates.
        
        Args:
            symbol: Stock symbol
            timeframe: Candle interval
            cached_df: Existing cached data
            new_df: New fetched data
        
        Returns:
            Merged DataFrame
        """
        if cached_df is None or cached_df.empty:
            return new_df
        
        if new_df is None or new_df.empty:
            return cached_df
        
        # Concatenate and drop duplicates by timestamp
        merged = pd.concat([cached_df, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["timestamp"], keep="last")
        merged = merged.sort_values("timestamp").reset_index(drop=True)
        
        # Save merged data back to cache
        self.save_cache(symbol, timeframe, merged)
        
        return merged
    
    def clear_cache(self, symbol: str = None, timeframe: str = None) -> None:
        """
        Clear cache files.
        
        Args:
            symbol: Clear only this symbol (None = all)
            timeframe: Clear only this timeframe (None = all)
        """
        if symbol is None:
            # Clear entire cache directory
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(exist_ok=True)
        else:
            # Clear specific file
            path = self.get_cache_path(symbol, timeframe or "*")
            if "*" in str(path):
                for f in self.cache_dir.glob(f"{symbol}_*.parquet"):
                    f.unlink()
            else:
                if path.exists():
                    path.unlink()
