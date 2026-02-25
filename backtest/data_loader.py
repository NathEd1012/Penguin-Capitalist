"""Data loader for historical market data from Alpaca."""
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pytz
from dotenv import load_dotenv

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
    
    def load_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        timeframe_minutes: int = 1,
    ) -> Dict[str, Dict]:
        """
        Load historical bars for symbols.
        
        Args:
            symbols: List of stock symbols
            start_date: Start datetime
            end_date: End datetime
            timeframe_minutes: Minutes per bar (1, 5, 15, 60, etc.)
        
        Returns:
            Dict[symbol][timestamp] = bar data (o, h, l, c, v)
        """
        # Map minutes to TimeFrame
        if timeframe_minutes == 1:
            tf = TimeFrame.Minute
        elif timeframe_minutes == 5:
            tf = TimeFrame.FiveMin
        elif timeframe_minutes == 15:
            tf = TimeFrame.FifteenMin
        elif timeframe_minutes == 60:
            tf = TimeFrame.Hour
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe_minutes} minutes")
        
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=start_date,
            end=end_date,
            limit=100000,
        )
        
        print(f"Fetching data for {len(symbols)} symbols from {start_date} to {end_date}...")
        bars = self.client.get_stock_bars(request)
        
        # Organize data by symbol and timestamp
        data = {}
        for symbol in symbols:
            data[symbol] = {}
            if symbol in bars.df.index.get_level_values(0):
                symbol_data = bars.df.xs(symbol, level=0)
                for timestamp, row in symbol_data.iterrows():
                    # Ensure timezone-aware timestamp
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=pytz.UTC)
                    data[symbol][timestamp] = {
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': int(row['volume']),
                    }
        
        return data
    
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
