"""Synthetic bid/ask quotes using the bidask EDGE spread estimator."""

from datetime import datetime, time
from collections import OrderedDict, deque
from math import isfinite
from typing import Dict, Tuple, Optional, Union

from bidask import edge
import pytz


DEFAULT_SPREAD_WINDOW = 50


class SyntheticSpreadModel:
    """
    Estimate the relative spread from trailing OHLC bars with bidask.edge,
    then multiply by the current close to obtain the full spread in price units.
    Each symbol has its own window, including the current completed candle.
    Feed candles in timestamp order; no future candles enter the estimate.
    Use observe_candle on every candle and get_bid_ask only when executing an
    order to maintain the full history without estimating a spread on HOLD bars.

    The legacy price/range formula is used during warmup (fewer than three
    bars), when EDGE returns a non-finite estimate, or when open_price is
    omitted. Market-hour and volume adjustments apply to either base spread.
    
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
            volume=1000000,
            symbol="AAPL",
            open_price=150.40,
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
        spread_window: int = DEFAULT_SPREAD_WINDOW,
    ):
        """
        Initialize the synthetic spread model.
        
        Args:
            base_price_factor: Fallback spread fraction (default 0.0002 = 0.02%)
            volatility_factor: Fallback multiplier for (high - low) (default 0.05)
            market_open_time: Market open time in "HH:MM" format (default "14:30" UTC = 9:30 AM ET)
            market_close_time: Market close time in "HH:MM" format (default "20:00" UTC = 4:00 PM ET)
            opening_period_minutes: Minutes after open to apply opening multiplier (default 15)
            closing_period_minutes: Minutes before close to apply closing multiplier (default 15)
            opening_spread_multiplier: Spread multiplier during first N minutes (default 1.5x)
            closing_spread_multiplier: Spread multiplier during last N minutes (default 1.2x)
            timezone: Timezone for timestamp interpretation (default "UTC")
            volume_window: Number of bars to use for average volume calculation (default 50)
            spread_window: Trailing OHLC bars for EDGE (at least 3; default 50)
        """
        if isinstance(spread_window, bool) or not isinstance(spread_window, int) or spread_window < 3:
            raise ValueError("spread_window must be an integer of at least 3")
        self.base_price_factor = base_price_factor
        self.volatility_factor = volatility_factor
        self.spread_window = spread_window
        self._ohlc_history: Dict[Optional[str], deque] = {}
        self._last_timestamp: Dict[Optional[str], datetime] = {}
        
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
        self.market_open_time = time(self.market_open_hour, self.market_open_minute)
        self.market_close_time = time(self.market_close_hour, self.market_close_minute)
        self._period_cache: OrderedDict[Union[datetime, str], Tuple[bool, bool]] = OrderedDict()
        
        # Volume tracking per symbol
        self.volume_history: Dict[str, deque[float]] = {}
        self.volume_window_sums: Dict[str, float] = {}
        self.volume_window = volume_window

    def reset_symbol(self, symbol: Optional[str]) -> None:
        """Discard history at a price-basis change such as an unadjusted split."""
        self._ohlc_history.pop(symbol, None)
        self._last_timestamp.pop(symbol, None)
        self.volume_history.pop(symbol, None)
        self.volume_window_sums.pop(symbol, None)

    def observe_candle(
        self,
        mid_price: float,
        high: float,
        low: float,
        timestamp: Union[datetime, str],
        volume: Optional[float] = None,
        symbol: Optional[str] = None,
        open_price: Optional[float] = None,
    ) -> None:
        """Record a completed OHLCV candle without computing its spread.

        Re-observing the same completed OHLC candle does not append it again,
        so get_bid_ask may safely follow observation at an execution timestamp.
        """
        is_new_candle = True
        if open_price is not None:
            if not all(isfinite(price) and price > 0 for price in (open_price, high, low, mid_price)):
                raise ValueError("OHLC prices must be finite and positive")
            if not (low <= open_price <= high and low <= mid_price <= high):
                raise ValueError("Open and close must lie within the candle's low/high range")

            dt = self._parse_timestamp(timestamp)
            previous_timestamp = self._last_timestamp.get(symbol)
            if previous_timestamp is not None and dt < previous_timestamp:
                raise ValueError("Candles must be supplied in timestamp order for each symbol")
            history = self._ohlc_history.setdefault(symbol, deque(maxlen=self.spread_window))
            candle = (open_price, high, low, mid_price)
            is_new_candle = dt != previous_timestamp
            if is_new_candle:
                history.append(candle)
                self._last_timestamp[symbol] = dt
            elif history[-1] != candle:
                raise ValueError("A completed candle cannot change at the same timestamp")

        if is_new_candle and volume is not None and symbol is not None:
            self._track_volume(symbol, volume)

    def _estimate_base_spread(
        self,
        mid_price: float,
        high: float,
        low: float,
        symbol: Optional[str],
        open_price: Optional[float],
    ) -> float:
        """Estimate the spread from the already observed trailing window."""
        fallback = max(
            mid_price * self.base_price_factor,
            (high - low) * self.volatility_factor,
        )
        if open_price is None:
            return fallback
        history = self._ohlc_history[symbol]
        if len(history) < 3:
            return fallback
        opens, highs, lows, closes = zip(*history)
        relative_spread = edge(opens, highs, lows, closes, sign=False)
        if not isfinite(relative_spread):
            return fallback
        return mid_price * relative_spread
    
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
        window_len = min(len(self.volume_history[symbol]), self.volume_window)
        avg_volume = self.volume_window_sums.get(symbol, 0.0) / window_len if window_len else 1.0
        
        # Avoid division by zero
        if current_volume <= 0:
            return 2.0  # Very wide spread for zero volume
        
        # Calculate factor: avg_volume / current_volume
        volume_factor = avg_volume / current_volume
        
        # Clamp to reasonable range
        if volume_factor < 0.5:
            return 0.5
        if volume_factor > 2.0:
            return 2.0
        return volume_factor
    
    def _track_volume(self, symbol: str, volume: float) -> None:
        """Track volume history for a symbol."""
        history = self.volume_history.setdefault(
            symbol, deque(maxlen=self.volume_window)
        )
        history.append(volume)

        window_sum = self.volume_window_sums.get(symbol, 0.0) + volume
        if len(history) == self.volume_window:
            window_sum = sum(history)
        self.volume_window_sums[symbol] = window_sum
    
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
        elif self.timezone is pytz.UTC and dt.utcoffset() is not None and dt.utcoffset().total_seconds() == 0:
            return dt
        else:
            dt = dt.astimezone(self.timezone)
        
        return dt

    def _get_period_flags(self, timestamp: Union[datetime, str]) -> Tuple[bool, bool]:
        """Return cached opening/closing period flags for a timestamp."""
        cached = self._period_cache.get(timestamp)
        if cached is not None:
            self._period_cache.move_to_end(timestamp)
            return cached

        dt = self._parse_timestamp(timestamp)
        current_time = dt.time()
        if not (self.market_open_time <= current_time < self.market_close_time):
            flags = (False, False)
        else:
            open_dt = dt.replace(
                hour=self.market_open_hour,
                minute=self.market_open_minute,
                second=0,
                microsecond=0,
            )
            close_dt = dt.replace(
                hour=self.market_close_hour,
                minute=self.market_close_minute,
                second=0,
                microsecond=0,
            )
            flags = (
                int((dt - open_dt).total_seconds() / 60) < self.opening_period_minutes,
                int((close_dt - dt).total_seconds() / 60) < self.closing_period_minutes,
            )

        self._period_cache[timestamp] = flags
        self._period_cache.move_to_end(timestamp)
        while len(self._period_cache) > self.volume_window:
            self._period_cache.popitem(last=False)
        return flags
    
    def _is_opening_period(self, timestamp: Union[datetime, str]) -> bool:
        """Check if timestamp is within first N minutes of market open."""
        return self._get_period_flags(timestamp)[0]
    
    def _is_closing_period(self, timestamp: Union[datetime, str]) -> bool:
        """Check if timestamp is within last N minutes before market close."""
        return self._get_period_flags(timestamp)[1]
    
    def get_bid_ask(
        self,
        mid_price: float,
        high: float,
        low: float,
        timestamp: Union[datetime, str],
        volume: Optional[float] = None,
        symbol: Optional[str] = None,
        open_price: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """
        Calculate bid/ask prices around the close of a completed candle.
        
        Args:
            mid_price: Candle close price (used as mid price)
            high: Candle high price
            low: Candle low price
            timestamp: Candle timestamp (datetime or ISO string)
            volume: Volume in units (optional, used for volume factor calculation)
            symbol: Symbol identifier for independent spread and volume history.
                If omitted, calls share a single unnamed stream.
            open_price: Actual candle open, required for EDGE estimation.
                If omitted, use the legacy price/range fallback.
        
        Returns:
            Tuple of (bid, ask, spread) where:
            - bid = mid_price - spread/2
            - ask = mid_price + spread/2
            - spread = EDGE estimate in price units, adjusted for hours and volume
        """
        self.observe_candle(
            mid_price, high, low, timestamp,
            volume=volume, symbol=symbol, open_price=open_price,
        )
        spread = self._estimate_base_spread(
            mid_price, high, low, symbol, open_price
        )
        
        # Adjust spread for market hours
        is_opening_period, is_closing_period = self._get_period_flags(timestamp)
        if is_opening_period:
            spread *= self.opening_spread_multiplier
        elif is_closing_period:
            spread *= self.closing_spread_multiplier
        
        # Apply volume factor if volume data provided
        if volume is not None and symbol is not None:
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
        timestamp: Union[datetime, str],
        volume: Optional[float] = None,
        symbol: Optional[str] = None,
        open_price: Optional[float] = None,
    ) -> float:
        """
        Get only the spread value (convenience method).
        
        Args:
            mid_price: Candle close price
            high: Candle high price
            low: Candle low price
            timestamp: Candle timestamp
            volume: Optional candle volume
            symbol: Symbol identifier; use the same value as get_bid_ask
            open_price: Actual candle open for EDGE estimation
        
        Returns:
            Spread value
        """
        _, _, spread = self.get_bid_ask(
            mid_price, high, low, timestamp,
            volume=volume, symbol=symbol, open_price=open_price,
        )
        return spread
