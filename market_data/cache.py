"""Disk caching system for market data to avoid unnecessary API calls."""
import os
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
    
    def cache_exists(self, symbol: str, timeframe: str) -> bool:
        """Check if cache file exists."""
        return self.get_cache_path(symbol, timeframe).exists()
    
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
            df.to_parquet(path, index=False)
        except Exception as e:
            # Silently fail if cache write fails
            pass
    
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
        cached_df = self.load_cache(symbol, timeframe)
        
        if cached_df is None or cached_df.empty:
            return None
        
        # Check if cache covers the requested range
        cache_start = cached_df["timestamp"].min()
        cache_end = cached_df["timestamp"].max()
        
        # Convert datetimes to UTC if needed
        start_utc = pd.to_datetime(start, utc=True)
        end_utc = pd.to_datetime(end, utc=True)
        
        # If cache doesn't cover the full range, return None
        if cache_start > start_utc or cache_end < end_utc:
            return None
        
        # Return subset within requested range
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
