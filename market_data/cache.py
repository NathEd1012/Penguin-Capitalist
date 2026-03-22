"""Disk caching system for market data to avoid unnecessary API calls."""
import os
import json
from pathlib import Path
from datetime import datetime
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

        cache_start = pd.to_datetime(cached_df["timestamp"].min(), utc=True)
        cache_end = pd.to_datetime(cached_df["timestamp"].max(), utc=True)
        self._write_meta(symbol, timeframe, cache_start, cache_end, len(cached_df))
        return cache_start, cache_end

    def get_cached_slice(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Return cached rows in [start, end] even when cache does not fully cover the range."""
        return self._read_cache_range(symbol, timeframe, start, end)
    
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
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
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
            meta = {
                "symbol": symbol,
                "timeframe": timeframe,
                "rows": int(rows),
                "start": pd.to_datetime(start_ts, utc=True).isoformat(),
                "end": pd.to_datetime(end_ts, utc=True).isoformat(),
            }
            self.get_meta_path(symbol, timeframe).write_text(json.dumps(meta), encoding="utf-8")
        except Exception:
            pass

    def _load_meta(self, symbol: str, timeframe: str):
        """Load cache metadata sidecar if present and valid."""
        meta_path = self.get_meta_path(symbol, timeframe)
        if not meta_path.exists():
            return None

        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            start = pd.to_datetime(raw.get("start"), utc=True)
            end = pd.to_datetime(raw.get("end"), utc=True)
            return {
                "start": start,
                "end": end,
                "rows": int(raw.get("rows", 0)),
            }
        except Exception:
            return None

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

        start_utc = pd.to_datetime(start, utc=True)
        end_utc = pd.to_datetime(end, utc=True)

        try:
            # Use parquet filters to avoid loading the full file when backend supports it.
            df = pd.read_parquet(
                path,
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

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df[(df["timestamp"] >= start_utc) & (df["timestamp"] <= end_utc)].copy()
        return df if not df.empty else None
    
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

        start_utc = pd.to_datetime(start, utc=True)
        end_utc = pd.to_datetime(end, utc=True)

        meta = self._load_meta(symbol, timeframe)
        if meta is not None:
            if meta["start"] > start_utc or meta["end"] < end_utc:
                return None
            return self._read_cache_range(symbol, timeframe, start, end)

        # Backward-compatible fallback for older cache files without metadata.
        cached_df = self.load_cache(symbol, timeframe)
        if cached_df is None or cached_df.empty:
            return None

        cache_start = cached_df["timestamp"].min()
        cache_end = cached_df["timestamp"].max()
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
