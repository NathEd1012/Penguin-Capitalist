# penguins/support_resistance_penguin.py
from typing import List, Tuple, Dict, Optional
from penguins.base_penguin import BasePenguin


def _mean(values: List[float]) -> float:
    """Compute mean of values without numpy."""
    return sum(values) / len(values) if values else 0


class SupportResistancePenguin(BasePenguin):
    """
    Support/Resistance Zone-based trading strategy.
    
    Identifies support and resistance zones from historical price pivots,
    trades on rejection patterns near these zones.
    
    Key Parameters:
    - left/right: Pivot detection window (must confirm after 'right' bars)
    - atr_n: ATR period for volatility
    - zone_k: Zone width multiplier (zone_width = zone_k * ATR)
    - min_touches: Minimum touches to confirm zone strength
    - rr_min: Minimum Risk/Reward ratio for entry
    - stop_m: Stop-loss buffer multiplier (stop_m * ATR)
    - recency_weight: Weight for recent candles (0..1)
    """
    
    def __init__(
        self,
        left: int = 3,
        right: int = 3,
        atr_n: int = 14,
        zone_k: float = 0.5,
        min_touches: int = 2,
        rr_min: float = 1.5,
        stop_m: float = 1.0,
        recency_weight: float = 0.2,
    ):
        super().__init__("SupportResistancePenguin")
        self.left = left
        self.right = right
        self.atr_n = atr_n
        self.zone_k = zone_k
        self.min_touches = min_touches
        self.rr_min = rr_min
        self.stop_m = stop_m
        self.recency_weight = recency_weight
        
        # Cache zones per symbol to avoid recomputing every tick
        self._zone_cache: Dict[str, Dict] = {}
        self._cache_bars: Dict[str, int] = {}
        self._recompute_interval = 10  # Recompute zones every 10 bars
        
    def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio) -> Tuple[str, int]:
        """
        Main decision function. Returns (BUY|SELL|HOLD, quantity).
        
        Strategy:
        - BUY: Price near support zone + bullish rejection signal
        - SELL: Price near resistance zone + bearish rejection signal OR take profit
        - HOLD: No clear setup
        """
        if len(mid_prices) < self.left + self.right + self.atr_n:
            return "HOLD", 0
        
        current_price = mid_prices[-1]
        atr_val = self._compute_atr(mid_prices, self.atr_n)
        
        # Skip if ATR is invalid
        if atr_val <= 0:
            return "HOLD", 0
        
        # Recompute zones if cache is stale or doesn't exist
        if symbol not in self._zone_cache or \
           (len(mid_prices) - self._cache_bars.get(symbol, 0)) >= self._recompute_interval:
            zones = self._detect_and_cluster_zones(mid_prices, atr_val)
            self._zone_cache[symbol] = zones
            self._cache_bars[symbol] = len(mid_prices)
        else:
            zones = self._zone_cache[symbol]
        
        if not zones:
            return "HOLD", 0
        
        # Check position status
        has_position = (
            symbol in portfolio.positions and
            portfolio.positions[symbol].qty > 0
        )
        
        # Decision logic
        if not has_position:
            # Look for BUY signals
            signal = self._check_buy_signal(current_price, mid_prices, zones, atr_val)
            if signal:
                return "BUY", 1
        else:
            # Look for SELL signals
            signal = self._check_sell_signal(
                current_price, mid_prices, zones, atr_val,
                portfolio.positions[symbol].avg_price
            )
            if signal:
                qty = portfolio.positions[symbol].qty
                return "SELL", qty
        
        return "HOLD", 0
    
    def _check_buy_signal(
        self,
        current_price: float,
        mid_prices: List[float],
        zones: List[Dict],
        atr_val: float
    ) -> bool:
        """
        Buy setup:
        1. Current price is near or inside a support zone
        2. Show bullish rejection (e.g., close above midpoint after dip)
        3. Next resistance zone is far enough (good R/R)
        """
        support_zones = [z for z in zones if z["type"] == "support"]
        resistance_zones = [z for z in zones if z["type"] == "resistance"]
        
        if not support_zones:
            return False
        
        # Find nearest support zone
        nearest_support = min(support_zones, key=lambda z: abs(current_price - z["center"]))
        
        zone_distance = abs(current_price - nearest_support["center"])
        zone_width = nearest_support["high"] - nearest_support["low"]
        
        # Check if price is near support (within zone + small margin)
        if zone_distance > zone_width * 0.7:
            return False
        
        # Check for bullish rejection: recent candles show reversal from low
        if len(mid_prices) < 3:
            return False
        
        # Simple rejection: recent low is in zone, recent close is higher
        recent_low = min(mid_prices[-3:])
        recent_close = mid_prices[-1]
        
        # Check if low was in zone
        if recent_low < nearest_support["low"] or recent_low > nearest_support["high"]:
            return False
        
        # Check if price bounced (close is above midpoint of zone)
        if recent_close <= nearest_support["center"]:
            return False
        
        # R/R check: find nearest resistance
        if resistance_zones:
            nearest_resistance = min(resistance_zones, key=lambda z: abs(current_price - z["center"]))
            risk = current_price - (nearest_support["low"] - self.stop_m * atr_val)
            reward = nearest_resistance["high"] - current_price
            
            if risk > 0 and reward / risk < self.rr_min:
                return False
        
        return True
    
    def _check_sell_signal(
        self,
        current_price: float,
        mid_prices: List[float],
        zones: List[Dict],
        atr_val: float,
        entry_price: float
    ) -> bool:
        """
        Sell setup:
        1. Price touches resistance zone + bearish rejection, OR
        2. Price reached R/R take-profit target
        """
        resistance_zones = [z for z in zones if z["type"] == "resistance"]
        support_zones = [z for z in zones if z["type"] == "support"]
        
        if not resistance_zones:
            return False
        
        nearest_resistance = min(resistance_zones, key=lambda z: abs(current_price - z["center"]))
        
        # Check if price is near resistance
        zone_distance = abs(current_price - nearest_resistance["center"])
        zone_width = nearest_resistance["high"] - nearest_resistance["low"]
        
        # Take profit if we reached resistance with good profit
        if zone_distance < zone_width * 0.6:
            # Check for bearish rejection or just take profit
            if len(mid_prices) >= 3:
                recent_high = max(mid_prices[-3:])
                recent_close = mid_prices[-1]
                
                # Bearish rejection: high in zone, close below midpoint
                if recent_high >= nearest_resistance["low"] and recent_close < nearest_resistance["center"]:
                    return True
            
            # Also take profit if price reached target R/R
            if support_zones:
                nearest_support = min(support_zones, key=lambda z: abs(z["center"] - entry_price))
                stop_price = nearest_support["low"] - self.stop_m * atr_val
                risk = entry_price - stop_price
                target_price = entry_price + risk * self.rr_min
                
                if current_price >= target_price:
                    return True
        
        # Hard stop: if price breaks below all zones, exit
        lowest_support_low = min([z["low"] for z in support_zones], default=0)
        if current_price < lowest_support_low - atr_val and current_price < entry_price * 0.98:
            return True
        
        return False
    
    def _detect_and_cluster_zones(
        self,
        mid_prices: List[float],
        atr_val: float
    ) -> List[Dict]:
        """
        Detect pivot points and cluster them into support/resistance zones.
        
        Prevents lookahead bias by only considering confirmed pivots
        (right bars after the pivot point must have passed).
        """
        # Only detect pivots that are fully confirmed
        # We need at least 'right' bars after the pivot to confirm it
        if len(mid_prices) < self.left + self.right + 1:
            return []
        
        # Detect pivots on confirmed part only
        max_idx = len(mid_prices) - self.right - 1
        pivots = self._detect_pivots(mid_prices[:max_idx + 1], self.left, self.right)
        
        if len(pivots) < self.min_touches:
            return []
        
        # Cluster nearby levels into zones
        zones = self._cluster_levels_into_zones(pivots, atr_val)
        
        # Score zones by strength (number of touches, recency)
        zones = self._score_zones(zones, mid_prices)
        
        return zones
    
    def _compute_atr(self, prices: List[float], n: int) -> float:
        """
        Compute ATR (Average True Range) from close prices only.
        Less accurate than with OHLCV, but works for this strategy.
        """
        if len(prices) < n:
            return 0
        
        trs = []
        for i in range(1, len(prices)):
            # True Range approximation: using consecutive close differences
            tr = abs(prices[i] - prices[i - 1])
            trs.append(tr)
        
        return _mean(trs[-n:]) if len(trs) >= n else _mean(trs) if trs else 0
    
    def _detect_pivots(
        self,
        prices: List[float],
        left: int,
        right: int
    ) -> List[Tuple[float, int, str]]:
        """
        Detect swing highs and swing lows (pivot points).
        
        A pivot is confirmed only after 'right' bars pass.
        Returns: List of (price, index, type) tuples.
        """
        pivots = []
        
        # We can only safely detect pivots from left+1 to len-right-1
        for i in range(left, len(prices) - right):
            # Local high: price[i] is higher than left and right neighbors
            if all(prices[i] >= prices[i - j] for j in range(1, left + 1)) and \
               all(prices[i] >= prices[i + j] for j in range(1, right + 1)):
                if prices[i] > 0:
                    pivots.append((prices[i], i, "resistance"))
            
            # Local low: price[i] is lower than left and right neighbors
            elif all(prices[i] <= prices[i - j] for j in range(1, left + 1)) and \
                 all(prices[i] <= prices[i + j] for j in range(1, right + 1)):
                if prices[i] > 0:
                    pivots.append((prices[i], i, "support"))
        
        return pivots
    
    def _cluster_levels_into_zones(
        self,
        pivots: List[Tuple[float, int, str]],
        atr_val: float
    ) -> List[Dict]:
        """
        Cluster nearby pivot points into zones.
        Zone width is determined by atr_val and zone_k parameter.
        """
        if not pivots:
            return []
        
        zone_width = self.zone_k * atr_val
        zones = []
        visited = set()
        
        for i, (price, idx, ptype) in enumerate(pivots):
            if i in visited:
                continue
            
            # Find all pivots of same type close to this one
            cluster = [(price, idx, ptype)]
            visited.add(i)
            
            for j, (p2, idx2, ptype2) in enumerate(pivots[i + 1:], start=i + 1):
                if j in visited or ptype2 != ptype:
                    continue
                if abs(p2 - price) <= zone_width * 1.5:
                    cluster.append((p2, idx2, ptype2))
                    visited.add(j)
            
            # Create zone from cluster
            prices_in_cluster = [p for p, _, _ in cluster]
            center = _mean(prices_in_cluster)
            zone_low = min(prices_in_cluster)
            zone_high = max(prices_in_cluster)
            
            # Expand zone by zone_width if too narrow
            if zone_high - zone_low < zone_width * 0.5:
                half_width = zone_width / 2
                zone_low = center - half_width
                zone_high = center + half_width
            
            zones.append({
                "type": ptype,
                "center": center,
                "low": zone_low,
                "high": zone_high,
                "touches": len(cluster),
                "indices": [idx for _, idx, _ in cluster],
            })
        
        return zones
    
    def _score_zones(
        self,
        zones: List[Dict],
        mid_prices: List[float]
    ) -> List[Dict]:
        """
        Score zones by strength:
        - More touches = stronger
        - Recent touches = more relevant
        """
        current_idx = len(mid_prices) - 1
        
        for zone in zones:
            # Base score from number of touches
            score = zone["touches"]
            
            # Boost recent touches
            recency_score = 0
            for idx in zone["indices"]:
                bars_ago = current_idx - idx
                if bars_ago >= 0:
                    # Recent = higher weight
                    weight = 1.0 / (1.0 + 0.1 * bars_ago)
                    recency_score += weight * self.recency_weight
            
            score += recency_score
            zone["score"] = score
        
        # Sort by score descending (strongest zones first)
        zones.sort(key=lambda z: z["score"], reverse=True)
        
        return zones
