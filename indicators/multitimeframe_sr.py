"""Indicator helpers for multi-timeframe support/resistance calculations."""

from typing import Dict, List, Optional, Tuple

DEFAULT_TIMEFRAMES: Dict[str, Tuple[int, int]] = {
    "1y": (252 * 390, 390),
    "3m": (63 * 390, 390),
    "1m": (21 * 390, 390),
    "1w": (5 * 390, 60),
    "1d": (390, 15),
}


def should_recalculate(current_bar_count: int, last_bar_count: int, lookback_bars: int, recalc_threshold_pct: float) -> bool:
    """Return True when enough bars passed to refresh cached levels."""
    bars_passed = current_bar_count - last_bar_count
    threshold = lookback_bars * recalc_threshold_pct
    return bars_passed >= threshold


def resample_to_candles(prices: List[float], candle_size: int) -> List[Tuple[float, float, float, float]]:
    """Resample minute prices into OHLC candles of given size."""
    if candle_size == 1 or len(prices) < candle_size:
        return [(p, p, p, p) for p in prices]

    candles = []
    for i in range(0, len(prices), candle_size):
        chunk = prices[i:i + candle_size]
        if not chunk:
            continue
        candles.append((chunk[0], max(chunk), min(chunk), chunk[-1]))
    return candles


def compute_range_sr_lines(prices: List[float], candle_size: int) -> Tuple[Optional[float], Optional[float]]:
    """Compute simple support/resistance from min low and max high."""
    if len(prices) < 10:
        return None, None

    candles = resample_to_candles(prices, candle_size)
    if not candles:
        return None, None

    highs = [c[1] for c in candles]
    lows = [c[2] for c in candles]
    return min(lows), max(highs)


def update_range_sr_cache(
    cache: Dict[str, Dict],
    symbol: str,
    mid_prices: List[float],
    timeframes: Dict[str, Tuple[int, int]],
    recalc_threshold_pct: float,
) -> None:
    """Update cached range-based S/R lines for all configured timeframes."""
    if symbol not in cache:
        cache[symbol] = {"lines": {}, "last_bar_count": {}}

    current_bar_count = len(mid_prices)

    for tf_name, (lookback_bars, candle_size) in timeframes.items():
        last_bar_count = cache[symbol]["last_bar_count"].get(tf_name, 0)
        if last_bar_count != 0 and not should_recalculate(current_bar_count, last_bar_count, lookback_bars, recalc_threshold_pct):
            continue

        prices_for_tf = mid_prices[-lookback_bars:] if current_bar_count >= lookback_bars else mid_prices
        support, resistance = compute_range_sr_lines(prices_for_tf, candle_size)
        if support is None or resistance is None:
            continue

        cache[symbol]["lines"][tf_name] = {
            "support": support,
            "resistance": resistance,
        }
        cache[symbol]["last_bar_count"][tf_name] = current_bar_count


def get_range_sr_signals(cache: Dict[str, Dict], symbol: str, current_price: float) -> Dict[str, str]:
    """Return per-timeframe position signals vs support/resistance."""
    if symbol not in cache or not cache[symbol].get("lines"):
        return {}

    signals: Dict[str, str] = {}
    for tf_name, lines in cache[symbol]["lines"].items():
        support = lines["support"]
        resistance = lines["resistance"]
        if support >= resistance:
            continue

        range_size = resistance - support

        if current_price > resistance:
            distance_pct = (current_price - resistance) / range_size * 100
            signals[tf_name] = "NEAR_R_ABOVE" if distance_pct < 5 else "ABOVE_R"
        elif current_price < support:
            distance_pct = (support - current_price) / range_size * 100
            signals[tf_name] = "NEAR_S_BELOW" if distance_pct < 5 else "BELOW_S"
        else:
            distance_to_support = (current_price - support) / range_size
            if distance_to_support < 0.15:
                signals[tf_name] = "NEAR_S"
            elif distance_to_support > 0.85:
                signals[tf_name] = "NEAR_R"
            else:
                signals[tf_name] = "BETWEEN"

    return signals


def record_range_sr_snapshot(
    cache: Dict[str, Dict],
    sr_history: Dict[str, List[Dict[str, Optional[float]]]],
    symbol: str,
    current_price: float,
    timeframes: Dict[str, Tuple[int, int]],
) -> None:
    """Store one plotting snapshot with current range-based levels."""
    if symbol not in sr_history:
        sr_history[symbol] = []

    symbol_lines = cache.get(symbol, {}).get("lines", {})
    snapshot: Dict[str, Optional[float]] = {"price": current_price}

    for tf_name in timeframes.keys():
        tf_lines = symbol_lines.get(tf_name, {})
        snapshot[f"{tf_name}_support"] = tf_lines.get("support")
        snapshot[f"{tf_name}_resistance"] = tf_lines.get("resistance")

    sr_history[symbol].append(snapshot)


def extract_pivots(candles: List[Tuple[float, float, float, float]], window: int = 2) -> List[float]:
    """Extract local pivot highs and lows from candles."""
    if len(candles) < (window * 2 + 1):
        return []

    highs = [c[1] for c in candles]
    lows = [c[2] for c in candles]
    pivots: List[float] = []

    for i in range(window, len(candles) - window):
        left_h = highs[i - window:i]
        right_h = highs[i + 1:i + 1 + window]
        left_l = lows[i - window:i]
        right_l = lows[i + 1:i + 1 + window]

        if highs[i] >= max(left_h) and highs[i] >= max(right_h):
            pivots.append(highs[i])
        if lows[i] <= min(left_l) and lows[i] <= min(right_l):
            pivots.append(lows[i])

    return pivots


def cluster_levels(raw_levels: List[float], cluster_tolerance_pct: float) -> List[Tuple[float, int]]:
    """Cluster nearby pivots and return (center, touch_count)."""
    if not raw_levels:
        return []

    levels = sorted(raw_levels)
    clusters: List[List[float]] = [[levels[0]]]

    for level in levels[1:]:
        center = sum(clusters[-1]) / len(clusters[-1])
        if center <= 0:
            continue
        if abs(level - center) / center <= cluster_tolerance_pct:
            clusters[-1].append(level)
        else:
            clusters.append([level])

    clustered = []
    for cluster in clusters:
        center = sum(cluster) / len(cluster)
        touches = len(cluster)
        clustered.append((center, touches))

    clustered.sort(key=lambda x: (-x[1], x[0]))
    return clustered


def compute_reaction_levels(
    prices: List[float],
    candle_size: int,
    cluster_tolerance_pct: float,
    max_levels_per_timeframe: int,
) -> List[float]:
    """Compute strongest reaction levels for one timeframe."""
    if len(prices) < 20:
        return []

    candles = resample_to_candles(prices, candle_size)
    if len(candles) < 7:
        return []

    pivots = extract_pivots(candles, window=2)
    clustered = cluster_levels(pivots, cluster_tolerance_pct)
    if not clustered:
        return []

    top = clustered[:max_levels_per_timeframe]
    return sorted([level for level, _ in top])


def update_reaction_level_cache(
    cache: Dict[str, Dict],
    symbol: str,
    mid_prices: List[float],
    timeframes: Dict[str, Tuple[int, int]],
    recalc_threshold_pct: float,
    cluster_tolerance_pct: float,
    max_levels_per_timeframe: int,
) -> None:
    """Update cached reaction levels across all configured timeframes."""
    if symbol not in cache:
        cache[symbol] = {"levels": {}, "last_bar_count": {}}

    current_bar_count = len(mid_prices)

    for tf_name, (lookback_bars, candle_size) in timeframes.items():
        last_bar_count = cache[symbol]["last_bar_count"].get(tf_name, 0)
        if last_bar_count != 0 and not should_recalculate(current_bar_count, last_bar_count, lookback_bars, recalc_threshold_pct):
            continue

        prices_for_tf = mid_prices[-lookback_bars:] if current_bar_count >= lookback_bars else mid_prices
        levels = compute_reaction_levels(
            prices_for_tf,
            candle_size,
            cluster_tolerance_pct,
            max_levels_per_timeframe,
        )
        if not levels:
            continue

        cache[symbol]["levels"][tf_name] = levels
        cache[symbol]["last_bar_count"][tf_name] = current_bar_count


def nearest_reaction_level(cache: Dict[str, Dict], symbol: str, current_price: float) -> Optional[float]:
    """Get nearest reaction level across all timeframes for symbol."""
    symbol_levels = cache.get(symbol, {}).get("levels", {})
    all_levels: List[float] = []
    for tf_levels in symbol_levels.values():
        all_levels.extend(tf_levels)

    if not all_levels:
        return None

    return min(all_levels, key=lambda level: abs(level - current_price))


def record_reaction_snapshot(
    cache: Dict[str, Dict],
    sr_history: Dict[str, List[Dict[str, Optional[float]]]],
    symbol: str,
    current_price: float,
    timeframes: Dict[str, Tuple[int, int]],
    max_levels_per_timeframe: int,
    snapshot_timestamp=None,
) -> None:
    """Store one plotting snapshot with current reaction lines."""
    if symbol not in sr_history:
        sr_history[symbol] = []

    row: Dict[str, Optional[float]] = {"price": current_price}
    if snapshot_timestamp is not None:
        row["timestamp"] = snapshot_timestamp
    symbol_levels = cache.get(symbol, {}).get("levels", {})

    for tf_name in timeframes.keys():
        levels = symbol_levels.get(tf_name, [])
        for i in range(max_levels_per_timeframe):
            key = f"{tf_name}_line_{i + 1}"
            row[key] = levels[i] if i < len(levels) else None

    sr_history[symbol].append(row)


def precompute_reaction_levels_for_full_history(
    prices: List[float],
    timeframes: Dict[str, Tuple[int, int]],
    cluster_tolerance_pct: float = 0.006,
    max_levels_per_timeframe: int = 3,
) -> List[Dict[str, List[float]]]:
    """
    Precompute reaction levels for all bars using full available history.
    
    Args:
        prices: List of all price points (e.g., close prices for entire backtest period)
        timeframes: Dict mapping tf_name to (lookback_bars, candle_size)
        cluster_tolerance_pct: Clustering tolerance
        max_levels_per_timeframe: Max levels to keep per timeframe
    
    Returns:
        List of dicts, one per bar, with timeframe -> [levels] mapping
        Index 0 corresponds to bar 0, etc.
    """
    num_bars = len(prices)
    result: List[Dict[str, List[float]]] = []
    
    for bar_idx in range(num_bars):
        row: Dict[str, List[float]] = {}
        
        # For this bar, use history up to this point
        history_up_to_bar = prices[:bar_idx + 1]
        
        for tf_name, (lookback_bars, candle_size) in timeframes.items():
            # Get prices for this timeframe's lookback window
            if len(history_up_to_bar) < lookback_bars:
                prices_for_tf = history_up_to_bar
            else:
                prices_for_tf = history_up_to_bar[-lookback_bars:]
            
            # Compute reaction levels
            levels = compute_reaction_levels(
                prices_for_tf,
                candle_size,
                cluster_tolerance_pct,
                max_levels_per_timeframe,
            )
            row[tf_name] = levels
        
        result.append(row)
    
    return result
