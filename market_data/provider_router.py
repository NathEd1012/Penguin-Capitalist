"""Provider router with caching for Alpaca market data."""
import logging
from datetime import datetime
from typing import Optional
import pandas as pd

from market_data.base_provider import BaseProvider
from market_data.alpaca_provider import AlpacaProvider
from market_data.cache import DataCache

logger = logging.getLogger(__name__)


class ProviderRouter:
    """
    Router that serves Alpaca data with optional disk cache.
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
        
        self._init_providers()
    
    def _init_providers(self):
        """Initialize API clients (lazy loading)."""
        try:
            self.alpaca_client = AlpacaProvider()
            logger.info("Alpaca provider initialized")
        except ValueError as e:
            logger.warning(f"Alpaca provider not available: {e}")
        
        if not self.alpaca_client:
            logger.warning("Alpaca provider not available")
    
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
            symbol: Stock symbol (e.g., "AAPL")
            start: Start datetime (UTC)
            end: End datetime (UTC)
            timeframe: Candle interval ("1m", "5m", "15m", "1h", "1d")
        
        Returns:
            Standardized DataFrame with OHLCV data
        
        Raises:
            RuntimeError: If Alpaca is unavailable or request fails
        """
        # Try cache first
        if self.use_cache and self.cache:
            cached = self.cache.get_cached_data_in_range(symbol, timeframe, start, end)
            if cached is not None and not cached.empty:
                logger.debug(f"Cache hit for {symbol} {timeframe}")
                return cached
        
        if not self.alpaca_client:
            raise RuntimeError("Alpaca provider is not available. Check API credentials.")

        logger.debug(f"Fetching {symbol} from Alpaca")
        try:
            df = self.alpaca_client.get_bars(symbol, start, end, timeframe)
            if not df.empty and self.use_cache and self.cache:
                self.cache.save_cache(symbol, timeframe, df)
            return df
        except RuntimeError as e:
            raise RuntimeError(
                f"Could not fetch data for {symbol} from Alpaca: {e}. "
                f"Ensure credentials are set and timeframe {timeframe} is supported."
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
