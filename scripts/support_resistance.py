"""Support and Resistance Zone Analysis."""
from pathlib import Path
from collections import defaultdict


def compute_and_log_support_resistance_zones(symbol_prices, output_dir="run_current"):
    """
    Compute support and resistance zones from trade price history.
    
    Args:
        symbol_prices: Dict[symbol] = [list of prices]
        output_dir: Directory to save support_resistance_zones.txt
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "support_resistance_zones.txt"
    
    lines = []
    lines.append("=" * 80)
    lines.append("SUPPORT & RESISTANCE ZONES ANALYSIS")
    lines.append("=" * 80)
    lines.append(f"\nEvaluated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("Method:")
    lines.append("  - Identifies local highs and lows in price history")
    lines.append("  - Local minimum = support (price bounced upward)")
    lines.append("  - Local maximum = resistance (price bounced downward)")
    lines.append("  - Clusters nearby levels within 2% tolerance")
    lines.append("  - Sorts by strength (frequency of touches)")
    lines.append("")
    
    for symbol in sorted(symbol_prices.keys()):
        prices = symbol_prices[symbol]
        if not prices:
            continue
        
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"SYMBOL: {symbol}")
        lines.append("=" * 80)
        
        current_price = prices[-1] if prices else 0
        min_price = min(prices)
        max_price = max(prices)
        
        lines.append(f"Current Price: ${current_price:.2f}")
        lines.append(f"Price Range: ${min_price:.2f} - ${max_price:.2f}")
        lines.append(f"Total bars analyzed: {len(prices)}")
        
        # Find local extrema
        support_levels = []  # Local minima
        resistance_levels = []  # Local maxima
        
        if len(prices) >= 3:
            for i in range(1, len(prices) - 1):
                # Local minimum (support)
                if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                    support_levels.append(prices[i])
                # Local maximum (resistance)
                elif prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                    resistance_levels.append(prices[i])
        
        # Cluster levels within 2% tolerance
        def cluster_levels(levels, tolerance=0.02):
            if not levels:
                return []
            
            levels = sorted(set(levels))
            clusters = []
            current_cluster = [levels[0]]
            
            for level in levels[1:]:
                # Check if within 2% of first level in cluster
                pct_diff = abs(level - current_cluster[0]) / current_cluster[0]
                if pct_diff <= tolerance:
                    current_cluster.append(level)
                else:
                    # Start new cluster
                    clusters.append(current_cluster)
                    current_cluster = [level]
            
            if current_cluster:
                clusters.append(current_cluster)
            
            return clusters
        
        support_clusters = cluster_levels(support_levels)
        resistance_clusters = cluster_levels(resistance_levels)
        
        # Calculate average and strength for each cluster
        def get_cluster_stats(clusters):
            stats = []
            for cluster in clusters:
                avg_price = sum(cluster) / len(cluster)
                touches = len(cluster)
                stats.append({'price': avg_price, 'touches': touches})
            # Sort by touches (descending), then by price
            stats.sort(key=lambda x: (-x['touches'], x['price']))
            return stats
        
        support_stats = get_cluster_stats(support_clusters)
        resistance_stats = get_cluster_stats(resistance_clusters)
        
        # Output SUPPORT levels
        lines.append("")
        lines.append("SUPPORT LEVELS:")
        lines.append("-" * 80)
        if support_stats:
            for idx, stat in enumerate(support_stats[:10], 1):  # Top 10
                distance = (current_price - stat['price']) / current_price * 100
                lines.append(
                    f"  S{idx}: ${stat['price']:>8.2f}  "
                    f"(Touches: {stat['touches']:>3}  Distance: {distance:>+6.2f}%)"
                )
        else:
            lines.append("  (None found)")
        
        # Output RESISTANCE levels
        lines.append("")
        lines.append("RESISTANCE LEVELS:")
        lines.append("-" * 80)
        if resistance_stats:
            for idx, stat in enumerate(resistance_stats[:10], 1):  # Top 10
                distance = (stat['price'] - current_price) / current_price * 100
                lines.append(
                    f"  R{idx}: ${stat['price']:>8.2f}  "
                    f"(Touches: {stat['touches']:>3}  Distance: {distance:>+6.2f}%)"
                )
        else:
            lines.append("  (None found)")
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ S&R zones computed and saved to {output_file}")
