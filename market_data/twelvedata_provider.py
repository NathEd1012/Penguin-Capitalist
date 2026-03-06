"""Twelve Data market data provider for global assets."""
import os
from pathlib import Path
from datetime import datetime
import time
import requests
import pandas as pd
from dotenv import load_dotenv

from market_data.base_provider import BaseProvider


class TwelveDataProvider(BaseProvider):
    """Fetch historical data from Twelve Data API for global assets."""
    
    BASE_URL = "https://api.twelvedata.com/time_series"
    
    # Interval mapping
    INTERVAL_MAP = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "1h": "1h",
        "1d": "1day",
    }
    
    # Rate limiting
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    
    def __init__(self):
        """Initialize Twelve Data client with API key from .env."""
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)

        self.api_key = (os.environ.get("TWELVE_DATA_API_KEY") or "").strip().strip('"').strip("'")
        if not self.api_key:
            raise ValueError(
                "Missing Twelve Data API key. Set TWELVE_DATA_API_KEY in .env"
            )
    
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> pd.DataFrame:
        """
        Fetch bars from Twelve Data.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "ASML.AMS", "BABA")
            start: Start datetime (UTC)
            end: End datetime (UTC)
            timeframe: Candle interval ("1m", "5m", "15m", "1h", "1d")
        
        Returns:
            Standardized DataFrame with OHLCV data
        
        Raises:
            ValueError: If timeframe not supported
            RuntimeError: If API call fails after retries
        """
        # Validate timeframe
        tf = self._validate_timeframe(timeframe)
        interval = self.INTERVAL_MAP[tf]
        
        params = {
            "symbol": symbol,
            "interval": interval,
            "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
            "apikey": self.api_key,
            "format": "JSON",
            "timezone": "UTC",
        }
        
        # Retry logic
        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.get(self.BASE_URL, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                # Check for API errors
                if "status" in data and data["status"] != "ok":
                    raise RuntimeError(f"Twelve Data API error: {data.get('message', 'Unknown error')}")
                
                if not data.get("values"):
                    return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
                
                # Parse response
                df = pd.DataFrame(data["values"])
                
                # Rename columns
                df = df.rename(columns={
                    "datetime": "timestamp",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                })
                
                # Normalize
                return self._normalize_dataframe(df)
            
            except requests.exceptions.RequestException as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                raise RuntimeError(f"Twelve Data API error for {symbol} (attempt {attempt + 1}): {str(e)}")
            
            except (KeyError, ValueError) as e:
                raise RuntimeError(f"Failed to parse Twelve Data response for {symbol}: {str(e)}")
        
        raise RuntimeError(f"Failed to fetch data for {symbol} after {self.MAX_RETRIES} retries")
