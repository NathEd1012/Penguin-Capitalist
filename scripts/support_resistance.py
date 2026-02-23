"""Support & Resistance calculations and logging."""

import os
from datetime import datetime
from data import get_timeframe_bars


def compute_and_log_support_resistance_zones(sr_penguin, symbols, scales):
    """Compute S&R zones for all symbols and log to file.
    
    Args:
        sr_penguin: SupportResistancePenguin instance
        symbols: List of symbols to analyze
        scales: List of (scale_name, timeframe, lookback_days) tuples
    """
    
    def _zones_overlap_strict(cluster, zone):
        """Check if zone overlaps with any zone in cluster (no tolerance)."""
        for existing in cluster["zones"]:
            overlaps = not (
                existing["high"] < zone["low"]
                or zone["high"] < existing["low"]
            )
            if overlaps:
                return True
        return False

    zones_log_path = os.path.join("run_current", "support_resistance_zones.txt")
    with open(zones_log_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("SUPPORT & RESISTANCE ZONES LOG\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Evaluated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("Parameters:\n")
        f.write(
            f"  - Pivot detection window: {sr_penguin.left} bars left, {sr_penguin.right} bars right\n"
        )
        f.write(f"  - ATR period: {sr_penguin.atr_n} bars\n")
        f.write(
            f"  - Minimum bars needed: {sr_penguin.left + sr_penguin.right + sr_penguin.atr_n} bars\n"
        )
        f.write(f"  - Zone width multiplier: {sr_penguin.zone_k}\n")
        f.write("  - Minimum touches: 2\n")
        f.write("  - Reaction requirement: move >= 1 ATR within 3 bars\n")
        f.write("  - Merge tolerance: 0.3% of current price\n")
        f.write("  - Scales: 5Min/3D, 15Min/10D, 60Min/60D, 1D/6M\n\n")

        for symbol in symbols:
            f.write("=" * 80 + "\n")
            f.write(f"SYMBOL: {symbol} (MULTI-SCALE)\n")
            f.write("=" * 80 + "\n\n")

            per_scale_zones = []
            latest_price = None

            for scale_name, timeframe, lookback_days in scales:
                try:
                    scale_history = get_timeframe_bars(
                        [symbol],
                        timeframe=timeframe,
                        lookback_days=lookback_days,
                    ).get(symbol, [])
                except Exception as e:
                    scale_history = []
                    print(
                        f"Warning: failed to load {scale_name} bars for {symbol}: {e}"
                    )

                if not scale_history:
                    continue

                if latest_price is None:
                    latest_price = scale_history[-1]

                zones = sr_penguin.compute_scale_zones(
                    scale_history,
                    min_touches=2,
                    reaction_lookahead=3,
                    reaction_atr_mult=1.0,
                )
                for zone in zones:
                    # Cap touches and reactions to 10 per scale
                    capped_touches = min(zone["touches"], 10)
                    capped_reactions = min(zone.get("reactions", 0), 10)
                    per_scale_zones.append(
                        {
                            "center": zone["center"],
                            "low": zone["low"],
                            "high": zone["high"],
                            "touches": capped_touches,
                            "reactions": capped_reactions,
                            "score": zone.get("score", 0),
                            "scale": scale_name,
                        }
                    )

            if not per_scale_zones:
                f.write("No zones detected.\n\n")
                continue

            current_price = latest_price if latest_price is not None else 0.0
            tolerance = current_price * 0.003
            max_zone_width = current_price * 0.005  # Max 0.5% of price

            clusters = []
            for zone in sorted(per_scale_zones, key=lambda z: z["center"]):
                merged = False
                for cluster in clusters:
                    if _zones_overlap_strict(cluster, zone):
                        cluster["zones"].append(zone)
                        merged = True
                        break
                if not merged:
                    clusters.append({"zones": [zone]})

            merged_zones = []
            for cluster in clusters:
                zones = cluster["zones"]
                strongest = max(zones, key=lambda z: z["score"])
                
                # Calculate merged bounds
                merged_low = min(z["low"] for z in zones)
                merged_high = max(z["high"] for z in zones)
                merged_center = (merged_low + merged_high) / 2
                
                # Cap width to 0.5% of price
                if merged_high - merged_low > max_zone_width:
                    merged_low = merged_center - max_zone_width / 2
                    merged_high = merged_center + max_zone_width / 2
                
                merged_zone = {
                    "center": merged_center,
                    "low": merged_low,
                    "high": merged_high,
                    "touches": sum(z["touches"] for z in zones),
                    "reactions": sum(z["reactions"] for z in zones),
                    "score": strongest["score"],
                    "scales": sorted({z["scale"] for z in zones}),
                }
                merged_zones.append(merged_zone)

            merged_zones.sort(key=lambda z: z["score"], reverse=True)

            f.write(f"Current price: ${current_price:.2f}\n\n")
            f.write(f"ZONES ({len(merged_zones)}):\n")
            for idx, zone in enumerate(merged_zones, 1):
                if zone["center"] < current_price - tolerance:
                    label = "SUPPORT"
                elif zone["center"] > current_price + tolerance:
                    label = "RESISTANCE"
                else:
                    label = "PIVOT/RANGE"

                f.write(f"  Zone #{idx} [{label}]:\n")
                f.write(
                    f"    Center: ${zone['center']:.2f}\n"
                    f"    Range: ${zone['low']:.2f} - ${zone['high']:.2f}\n"
                    f"    Touches: {zone['touches']}\n"
                    f"    Reactions: {zone['reactions']}\n"
                    f"    Strength Score: {zone['score']:.2f}\n"
                    f"    Scales: {', '.join(zone['scales'])}\n"
                )

            f.write("\n")
    
    print(f"✅ Support & Resistance zones logged to {zones_log_path}")
