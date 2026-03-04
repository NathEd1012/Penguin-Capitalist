"""Abstract base class for market data providers."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import pandas as pd


class BaseProvider(ABC):
    """
    Abstract base class for market data providers.
    
    All providers must return standardized DataFrames with:
    - timestamp (UTC datetime)
    - open, high, low, close (float)
    - volume (int)
    """
    
    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV bars.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            start: Start datetime (UTC)
            end: End datetime (UTC)
            timeframe: Candle interval ("1m", "5m", "15m", "1h", "1d")
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            All timestamps normalized to UTC.
        
        Raises:
            ValueError: If symbol or timeframe not supported
            RuntimeError: If API call fails after retries
        """
        pass
    
    def _validate_timeframe(self, timeframe: str) -> str:
        """Validate and normalize timeframe to provider format."""
        tf = timeframe.strip().lower()
        valid_timeframes = {"1m", "5m", "15m", "1h", "1d"}
        if tf not in valid_timeframes:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Use: {valid_timeframes}")
        return tf
    
    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame to standard format.
        
        Ensures:
        1. Columns: timestamp, open, high, low, close, volume
        2. timestamp is UTC datetime
        3. OHLCV columns are numeric
        4. Sorted by timestamp ascending
        """
        # Ensure required columns exist
        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(f"Missing columns. Required: {required_cols}")
        
        # Select and order columns
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        
        # Normalize timestamp to UTC
        if df["timestamp"].dtype == "object":
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        elif hasattr(df["timestamp"].dt, "tz"):
            if df["timestamp"].dt.tz is None:
                df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
            else:
                df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
        
        # Convert numeric columns
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        df["high"] = pd.to_numeric(df["high"], errors="coerce")
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("int64")
        
        # Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        # Remove any rows with missing OHLCV
        df = df.dropna(subset=["open", "high", "low", "close", "volume"])
        
        return df
