"""Realistic synthetic bid/ask spread model for backtesting."""

from datetime import datetime, time
from typing import Dict, Tuple, Optional, Union, List
import pytz


class SyntheticSpreadModel:
    """
    Generates realistic bid/ask spreads for backtesting using minute-level OHLCV data.
    
    Spread is based on:
    - Price level (0.02% of mid price by default)
    - Candle volatility (5% of candle range by default)
    - Volume factor (tighter spreads on high volume, wider on low volume)
    - Market hours (wider during opening and closing periods)
    
    This model efficiently handles large datasets of minute candles.
    
    Example:
        model = SyntheticSpreadModel(
            market_open_time="14:30",  # 9:30 AM ET in UTC
            market_close_time="20:00"   # 4:00 PM ET in UTC
        )
        
        bid, ask, spread = model.get_bid_ask(
            mid_price=150.50,
            high=151.25,
            low=150.10,
            timestamp="2026-01-20T14:30:00Z",
            volume=1000000
        )
    """
    
    def __init__(
        self,
        base_price_factor: float = 0.0002,
        volatility_factor: float = 0.05,
        market_open_time: str = "14:30",
        market_close_time: str = "20:00",
        opening_period_minutes: int = 15,
        closing_period_minutes: int = 15,
        opening_spread_multiplier: float = 1.5,
        closing_spread_multiplier: float = 1.2,
        timezone: str = "UTC",
        volume_window: int = 50,
    ):
        """
        Initialize the synthetic spread model.
        
        Args:
            base_price_factor: Spread as fraction of price (default 0.0002 = 0.02%)
            volatility_factor: Multiplier for (high - low) range (default 0.05 = 5%)
            market_open_time: Market open time in "HH:MM" format (default "14:30" UTC = 9:30 AM ET)
            market_close_time: Market close time in "HH:MM" format (default "20:00" UTC = 4:00 PM ET)
            opening_period_minutes: Minutes after open to apply opening multiplier (default 15)
            closing_period_minutes: Minutes before close to apply closing multiplier (default 15)
            opening_spread_multiplier: Spread multiplier during first N minutes (default 1.5x)
            closing_spread_multiplier: Spread multiplier during last N minutes (default 1.2x)
            timezone: Timezone for timestamp interpretation (default "UTC")
            volume_window: Number of bars to use for average volume calculation (default 50)
        """
        self.base_price_factor = base_price_factor
        self.volatility_factor = volatility_factor
        
        # Parse market times
        open_parts = market_open_time.split(":")
        self.market_open_hour = int(open_parts[0])
        self.market_open_minute = int(open_parts[1])
        
        close_parts = market_close_time.split(":")
        self.market_close_hour = int(close_parts[0])
        self.market_close_minute = int(close_parts[1])
        
        self.opening_period_minutes = opening_period_minutes
        self.closing_period_minutes = closing_period_minutes
        self.opening_spread_multiplier = opening_spread_multiplier
        self.closing_spread_multiplier = closing_spread_multiplier
        
        self.timezone = pytz.timezone(timezone) if timezone != "UTC" else pytz.UTC
        
        # Volume tracking per symbol
        self.volume_history: Dict[str, List[float]] = {}
        self.volume_window = volume_window
    
    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        """Clamp value between min and max."""
        return max(min_val, min(max_val, value))
    
    def _get_volume_factor(self, symbol: str, current_volume: float) -> float:
        """
        Calculate volume factor as: clamp(avg_volume / current_volume, 0.5, 2.0)
        
        - Low volume → high factor → wider spread (harder to trade)
        - High volume → low factor → tighter spread (easier to trade)
        
        Args:
            symbol: Symbol identifier
            current_volume: Current candle volume
        
        Returns:
            Volume factor (0.5 to 2.0)
        """
        if symbol not in self.volume_history or not self.volume_history[symbol]:
            return 1.0  # Default if no history
        
        # Get average volume from recent window
        recent_volumes = self.volume_history[symbol][-self.volume_window:]
        avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 1.0
        
        # Avoid division by zero
        if current_volume <= 0:
            return 2.0  # Very wide spread for zero volume
        
        # Calculate factor: avg_volume / current_volume
        volume_factor = avg_volume / current_volume
        
        # Clamp to reasonable range
        return self._clamp(volume_factor, 0.5, 2.0)
    
    def _track_volume(self, symbol: str, volume: float) -> None:
        """Track volume history for a symbol."""
        if symbol not in self.volume_history:
            self.volume_history[symbol] = []
        self.volume_history[symbol].append(volume)
    
    def _parse_timestamp(self, timestamp: Union[datetime, str]) -> datetime:
        """Parse and normalize timestamp to timezone-aware datetime."""
        if isinstance(timestamp, str):
            # Handle ISO format with Z suffix
            ts_str = timestamp.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts_str)
        else:
            dt = timestamp
        
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        else:
            dt = dt.astimezone(self.timezone)
        
        return dt
    
    def _is_opening_period(self, timestamp: Union[datetime, str]) -> bool:
        """Check if timestamp is within first N minutes of market open."""
        dt = self._parse_timestamp(timestamp)
        current_time = dt.time()
        market_open_time = time(self.market_open_hour, self.market_open_minute)
        market_close_time = time(self.market_close_hour, self.market_close_minute)
        
        # Market must be open
        if not (market_open_time <= current_time < market_close_time):
            return False
        
        # Calculate minutes from open
        open_dt = dt.replace(
            hour=self.market_open_hour,
            minute=self.market_open_minute,
            second=0,
            microsecond=0
        )
        minutes_from_open = int((dt - open_dt).total_seconds() / 60)
        
        return minutes_from_open < self.opening_period_minutes
    
    def _is_closing_period(self, timestamp: Union[datetime, str]) -> bool:
        """Check if timestamp is within last N minutes before market close."""
        dt = self._parse_timestamp(timestamp)
        current_time = dt.time()
        market_open_time = time(self.market_open_hour, self.market_open_minute)
        market_close_time = time(self.market_close_hour, self.market_close_minute)
        
        # Market must be open
        if not (market_open_time <= current_time < market_close_time):
            return False
        
        # Calculate minutes to close
        close_dt = dt.replace(
            hour=self.market_close_hour,
            minute=self.market_close_minute,
            second=0,
            microsecond=0
        )
        minutes_to_close = int((close_dt - dt).total_seconds() / 60)
        
        return minutes_to_close < self.closing_period_minutes
    
    def get_bid_ask(
        self,
        mid_price: float,
        high: float,
        low: float,
        timestamp: Union[datetime, str],
        volume: Optional[float] = None,
        symbol: Optional[str] = None,
    ) -> Tuple[float, float, float]:
        """
        Calculate realistic bid/ask prices and spread for a candle.
        
        Args:
            mid_price: Candle close price (used as mid price)
            high: Candle high price
            low: Candle low price
            timestamp: Candle timestamp (datetime or ISO string)
            volume: Volume in units (optional, used for volume factor calculation)
            symbol: Symbol identifier (required if volume is provided)
        
        Returns:
            Tuple of (bid, ask, spread) where:
            - bid = mid_price - spread/2
            - ask = mid_price + spread/2
            - spread = base spread adjusted for market hours and volume
        """
        # Calculate base spread components
        price_component = mid_price * self.base_price_factor
        volatility_component = (high - low) * self.volatility_factor
        
        # Spread is the maximum of price-based and volatility-based components
        spread = max(price_component, volatility_component)
        
        # Adjust spread for market hours
        if self._is_opening_period(timestamp):
            spread *= self.opening_spread_multiplier
        elif self._is_closing_period(timestamp):
            spread *= self.closing_spread_multiplier
        
        # Apply volume factor if volume data provided
        if volume is not None and symbol is not None:
            # Track volume
            self._track_volume(symbol, volume)
            
            # Apply volume factor
            volume_factor = self._get_volume_factor(symbol, volume)
            spread *= volume_factor
        
        # Compute bid/ask around mid price
        bid = mid_price - spread / 2
        ask = mid_price + spread / 2
        
        return bid, ask, spread
    
    def get_spread_only(
        self,
        mid_price: float,
        high: float,
        low: float,
        timestamp: Union[datetime, str]
    ) -> float:
        """
        Get only the spread value (convenience method).
        
        Args:
            mid_price: Candle close price
            high: Candle high price
            low: Candle low price
            timestamp: Candle timestamp
        
        Returns:
            Spread value
        """
        _, _, spread = self.get_bid_ask(mid_price, high, low, timestamp)
        return spread
