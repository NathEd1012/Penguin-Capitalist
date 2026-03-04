"""Provider router with intelligent provider selection and fallback logic."""
import logging
from datetime import datetime
from typing import Optional
import pandas as pd

from market_data.base_provider import BaseProvider
from market_data.alpaca_provider import AlpacaProvider
from market_data.twelvedata_provider import TwelveDataProvider
from market_data.cache import DataCache

logger = logging.getLogger(__name__)


class ProviderRouter:
    """
    Intelligent router that selects the best provider based on symbol and handles fallback.
    
    Strategy:
    1. US tickers → try Alpaca first, fallback to Twelve Data
    2. Non-US tickers → use Twelve Data directly
    3. Cache results to avoid API limits
    """
    
    def __init__(self, use_cache: bool = True, cache_dir: str = "data_cache"):
        """
        Initialize router.
        
        Args:
            use_cache: Enable disk caching (default: True)
            cache_dir: Cache directory path
        """
        self.use_cache = use_cache
        self.cache = DataCache(cache_dir) if use_cache else None
        
        self.alpaca_client: Optional[AlpacaProvider] = None
        self.twelvedata_client: Optional[TwelveDataProvider] = None
        
        self._init_providers()
    
    def _init_providers(self):
        """Initialize API clients (lazy loading)."""
        try:
            self.alpaca_client = AlpacaProvider()
            logger.info("Alpaca provider initialized")
        except ValueError as e:
            logger.warning(f"Alpaca provider not available: {e}")
        
        try:
            self.twelvedata_client = TwelveDataProvider()
            logger.info("Twelve Data provider initialized")
        except ValueError as e:
            logger.warning(f"Twelve Data provider not available: {e}")
    
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> pd.DataFrame:
        """
        Fetch bars with intelligent provider selection and fallback.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "ASML.AMS")
            start: Start datetime (UTC)
            end: End datetime (UTC)
            timeframe: Candle interval ("1m", "5m", "15m", "1h", "1d")
        
        Returns:
            Standardized DataFrame with OHLCV data
        
        Raises:
            RuntimeError: If all providers fail
        """
        # Try cache first
        if self.use_cache and self.cache:
            cached = self.cache.get_cached_data_in_range(symbol, timeframe, start, end)
            if cached is not None and not cached.empty:
                logger.debug(f"Cache hit for {symbol} {timeframe}")
                return cached
        
        # Determine provider strategy
        is_us = AlpacaProvider.is_us_ticker(symbol)
        
        if is_us and self.alpaca_client:
            logger.debug(f"Trying Alpaca for US ticker {symbol}")
            try:
                df = self.alpaca_client.get_bars(symbol, start, end, timeframe)
                if not df.empty:
                    if self.use_cache:
                        self.cache.save_cache(symbol, timeframe, df)
                    return df
            except RuntimeError as e:
                logger.warning(f"Alpaca failed for {symbol}: {e}. Trying Twelve Data...")
        
        # Fallback to Twelve Data
        if self.twelvedata_client:
            logger.debug(f"Trying Twelve Data for {symbol}")
            try:
                df = self.twelvedata_client.get_bars(symbol, start, end, timeframe)
                if not df.empty:
                    if self.use_cache:
                        self.cache.save_cache(symbol, timeframe, df)
                    return df
            except RuntimeError as e:
                logger.warning(f"Twelve Data failed for {symbol}: {e}")
        
        raise RuntimeError(
            f"Could not fetch data for {symbol} from any provider. "
            f"Ensure API credentials are set and timeframe {timeframe} is supported."
        )


# Global router instance
_router: Optional[ProviderRouter] = None


def init_router(use_cache: bool = True, cache_dir: str = "data_cache") -> ProviderRouter:
    """Initialize global router instance."""
    global _router
    _router = ProviderRouter(use_cache=use_cache, cache_dir=cache_dir)
    return _router


def get_router() -> ProviderRouter:
    """Get or initialize global router instance."""
    global _router
    if _router is None:
        _router = ProviderRouter()
    return _router


def get_bars(
    symbol: str,
    start: datetime,
    end: datetime,
    timeframe: str,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Convenience function to fetch bars using the global router.
    
    Args:
        symbol: Stock symbol
        start: Start datetime
        end: End datetime
        timeframe: Candle interval
        use_cache: Enable caching for this call
    
    Returns:
        Standardized DataFrame with OHLCV data
    """
    router = get_router()
    return router.get_bars(symbol, start, end, timeframe)
