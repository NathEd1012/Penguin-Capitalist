"""Alpaca market data provider for US equities."""
import os
from datetime import datetime
from typing import Optional
import pandas as pd
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from market_data.base_provider import BaseProvider


class AlpacaProvider(BaseProvider):
    """Fetch historical OHLCV data from Alpaca for US equities."""
    
    # Timeframe mapping
    TIMEFRAME_MAP = {
        "1m": TimeFrame.Minute,
        "5m": TimeFrame.FiveMin,
        "15m": TimeFrame.FifteenMin,
        "1h": TimeFrame.Hour,
        "1d": TimeFrame.Day,
    }
    
    def __init__(self):
        """Initialize Alpaca client with credentials from .env."""
        load_dotenv()
        
        api_key = os.environ.get("APCA_API_KEY_ID")
        secret_key = os.environ.get("APCA_API_SECRET_KEY")
        
        # Fallback to .env naming
        if not api_key:
            api_key = os.environ.get("ALPACA_API_KEY")
        if not secret_key:
            secret_key = os.environ.get("ALPACA_SECRET_KEY")
        
        if not api_key or not secret_key:
            raise ValueError(
                "Missing Alpaca credentials. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY "
                "or ALPACA_API_KEY and ALPACA_SECRET_KEY in .env"
            )
        
        self.client = StockHistoricalDataClient(api_key, secret_key)
    
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> pd.DataFrame:
        """
        Fetch bars from Alpaca.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            start: Start datetime (UTC)
            end: End datetime (UTC)
            timeframe: Candle interval ("1m", "5m", "15m", "1h", "1d")
        
        Returns:
            Standardized DataFrame with OHLCV data
        
        Raises:
            ValueError: If timeframe not supported
            RuntimeError: If API call fails
        """
        # Validate timeframe
        tf = self._validate_timeframe(timeframe)
        alpaca_tf = self.TIMEFRAME_MAP[tf]
        
        # Build request
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=alpaca_tf,
            start=start,
            end=end,
            limit=10000,  # Alpaca default
        )
        
        try:
            # Fetch data
            bars = self.client.get_stock_bars(request)
            
            # Handle empty response
            if bars.df.empty:
                return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
            
            # Convert to DataFrame
            df = bars.df.reset_index()
            
            # Rename columns to standard format
            df = df.rename(columns={
                "time": "timestamp",
            })
            
            # Filter for this symbol (in case of multi-symbol request)
            if "symbol" in df.columns:
                df = df[df["symbol"] == symbol].drop(columns=["symbol"])
            
            # Normalize
            return self._normalize_dataframe(df)
        
        except Exception as e:
            raise RuntimeError(f"Alpaca API error for {symbol}: {str(e)}")
    
    @staticmethod
    def is_us_ticker(symbol: str) -> bool:
        """
        Check if symbol is likely a US ticker.
        
        Simple heuristic: US tickers are typically 1-4 uppercase letters.
        """
        symbol = symbol.strip().upper()
        return 1 <= len(symbol) <= 4 and symbol.isalpha()
