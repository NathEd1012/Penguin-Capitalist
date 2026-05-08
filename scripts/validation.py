"""Validation and consistency checking utilities for detecting data quality issues."""
import os
from typing import Dict, List, Tuple, Set

# Provide a no-op `has_corporate_action_near` when corporate-action handling is disabled.
if os.environ.get("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
    def has_corporate_action_near(symbol, timestamp, window_days=2, action_types=None):
        return False
else:
    from corporate_actions import has_corporate_action_near  # type: ignore


def classify_price_jump(
    trade_idx: int,
    price_pct: float,
    prev_price: float,
    curr_price: float,
    trade_prices: List[float],
    is_first_trade: bool = False,
) -> str:
    """
    Classify a price jump into categories.
    
    Returns: "first_trade_artifact", "data_tick_anomaly", "real_event", or "unknown"
    """
    if is_first_trade:
        # First trade comparisons are often initialization artifacts
        return "first_trade_artifact"
    
    # Check if this is a single-tick anomaly (reverts in next trade)
    if trade_idx + 1 < len(trade_prices):
        next_price = trade_prices[trade_idx + 1]
        if next_price > 0:
            # If next price is closer to the previous price, likely a data blip
            dist_to_prev = abs(prev_price - next_price) / prev_price if prev_price > 0 else float('inf')
            dist_to_curr = abs(curr_price - next_price) / next_price if next_price > 0 else float('inf')
            if dist_to_prev < dist_to_curr and dist_to_prev < 0.05:  # Reverts within 5%
                return "data_tick_anomaly"
    
    return "real_event"


def check_consistency(results, max_jump_pct=0.15, bar_timestamps=None) -> Tuple[List[str], Dict[str, Set[int]]]:
    """
    Validate backtesting results for data quality issues and suspicious patterns.
    
    Separates warnings into two categories:
    1. Real issues (missing corporate actions, sustained price anomalies)
    2. Faulty data ticks (single-bar anomalies, initialization artifacts)
    
    Args:
        results: Dict[penguin_name] = (Portfolio, metrics_dict)
        max_jump_pct: Maximum allowed jump percentage (default 15%)
        bar_timestamps: List of datetime objects for each bar (optional)
    
    Returns:
        Tuple of (warning_strings_list, bad_bar_indices_dict)
        - warning_strings: All warnings to display
        - bad_bar_indices: Dict[penguin_name] = Set[bar_indices] with faulty data
    """
    warnings = []
    bad_bar_indices_by_penguin: Dict[str, Set[int]] = {}
    
    # Check each strategy's portfolio
    for penguin_name, (portfolio, metrics) in results.items():
        if not portfolio.trades:
            continue
        
        # 1) Positions vs trade history verification
        expected_qty = {}
        for trade in portfolio.trades:
            symbol = trade.symbol
            qty_change = trade.quantity if trade.action == "BUY" else -trade.quantity
            expected_qty[symbol] = expected_qty.get(symbol, 0) + qty_change
        
        for symbol, qty in portfolio.positions.items():
            expected = expected_qty.get(symbol, 0)
            if expected != qty:
                warnings.append(
                    f"[{penguin_name}] Position mismatch {symbol}: "
                    f"positions={qty}, trade_history={expected}"
                )
        
        for symbol, qty in expected_qty.items():
            if qty != 0 and symbol not in portfolio.positions:
                warnings.append(
                    f"[{penguin_name}] Missing position {symbol}: "
                    f"trades imply qty={qty}, positions=0"
                )
        
        # 2) Curve value consistency
        if portfolio.value_history and len(portfolio.value_history) > 0:
            final_value = portfolio.value_history[-1]
            computed_value = metrics.get('final_value', final_value)
            
            if final_value > 0:
                discrepancy = abs(computed_value - final_value) / final_value
                if discrepancy > 0.01:  # 1% tolerance
                    warnings.append(
                        f"[{penguin_name}] Curve mismatch: "
                        f"computed={computed_value:.2f}, final={final_value:.2f}, "
                        f"delta={discrepancy:+.2%}"
                    )
        
        # 3) Suspicious price jumps detection in trade history
        if len(portfolio.trades) > 1:
            trade_prices = [trade.price for trade in portfolio.trades]
            real_jumps = []           # Missing corporate actions, sustained anomalies
            faulty_data_jumps = []    # Single-tick anomalies, first-trade artifacts
            skipped_corporate_action_jumps = 0
            
            for i in range(1, len(trade_prices)):
                prev_price = trade_prices[i-1]
                curr_price = trade_prices[i]
                
                if prev_price > 0:
                    price_pct = (curr_price - prev_price) / prev_price
                    
                    if abs(price_pct) > max_jump_pct:
                        trade = portfolio.trades[i]
                        
                        # Check for known corporate actions
                        if has_corporate_action_near(
                            symbol=trade.symbol,
                            timestamp=trade.timestamp,
                            window_days=2,
                            action_types={"split", "reverse_split"},
                        ):
                            skipped_corporate_action_jumps += 1
                            continue

                        # Classify the jump
                        jump_type = classify_price_jump(
                            trade_idx=i,
                            price_pct=price_pct,
                            prev_price=prev_price,
                            curr_price=curr_price,
                            trade_prices=trade_prices,
                            is_first_trade=(i == 1),
                        )
                        
                        # Detect synthetic/stubbed bars at dataset boundaries
                        synthetic_flag = False
                        try:
                            if bar_timestamps and trade.timestamp is not None:
                                if trade.timestamp == bar_timestamps[0] or trade.timestamp == bar_timestamps[-1]:
                                    synthetic_flag = True
                        except Exception:
                            synthetic_flag = False

                        jump_data = {
                            'trade_idx': i,
                            'symbol': trade.symbol,
                            'pct': price_pct,
                            'prev': prev_price,
                            'curr': curr_price,
                            'type': jump_type,
                            'synthetic': synthetic_flag,
                        }
                        
                        if jump_type in ("first_trade_artifact", "data_tick_anomaly"):
                            faulty_data_jumps.append(jump_data)
                        else:
                            real_jumps.append(jump_data)

            if skipped_corporate_action_jumps:
                warnings.append(
                    f"[{penguin_name}] Ignored {skipped_corporate_action_jumps} "
                    "jump(s) near known corporate-action dates"
                )
            
            # Real warnings section
            if real_jumps:
                warnings.append(
                    f"[{penguin_name}] ⚠️  REAL ISSUES: Detected {len(real_jumps)} "
                    f"suspicious price jumps > {max_jump_pct*100:.0f}% (possible missing corporate actions)"
                )
                for jump in real_jumps:
                    trade = portfolio.trades[jump['trade_idx']]
                    date_str = trade.timestamp.strftime('%Y-%m-%d %H:%M:%S') if trade.timestamp else 'N/A'
                    synth_tag = ' [synthetic_jump]' if jump.get('synthetic') else ''
                    warnings.append(
                        f"  Trade #{jump['trade_idx']} ({jump['symbol']}) @ {date_str}: "
                        f"{jump['pct']:+.2%} (${jump['prev']:.2f} → ${jump['curr']:.2f}){synth_tag}"
                    )
                    # Mark bad bars for trading restrictions
                    if penguin_name not in bad_bar_indices_by_penguin:
                        bad_bar_indices_by_penguin[penguin_name] = set()
                    if hasattr(trade, 'bar_index'):
                        bad_bar_indices_by_penguin[penguin_name].add(trade.bar_index)
            
            # Faulty data section (separate table)
            if faulty_data_jumps:
                warnings.append(
                    f"[{penguin_name}] 📊 FAULTY DATA: {len(faulty_data_jumps)} single-tick anomalies "
                    f"(no trading should occur on these bars)"
                )
                for jump in faulty_data_jumps:
                    trade = portfolio.trades[jump['trade_idx']]
                    date_str = trade.timestamp.strftime('%Y-%m-%d %H:%M:%S') if trade.timestamp else 'N/A'
                    synth_tag = ' | synthetic_jump' if jump.get('synthetic') else ''
                    warnings.append(
                        f"  Trade #{jump['trade_idx']} ({jump['symbol']}) @ {date_str}: "
                        f"{jump['pct']:+.2%} (${jump['prev']:.2f} → ${jump['curr']:.2f}) [{jump['type']}{synth_tag}]"
                    )
                    # Mark bad bars so trades are reverted
                    if penguin_name not in bad_bar_indices_by_penguin:
                        bad_bar_indices_by_penguin[penguin_name] = set()
                    if hasattr(trade, 'bar_index'):
                        bad_bar_indices_by_penguin[penguin_name].add(trade.bar_index)
        
        # 4) Curve value jumps detection
        if len(portfolio.value_history) > 1:
            value_jumps = []
            
            for i in range(1, len(portfolio.value_history)):
                prev_val = portfolio.value_history[i-1]
                curr_val = portfolio.value_history[i]
                
                if prev_val > 0:
                    val_pct = (curr_val - prev_val) / prev_val
                    
                    if abs(val_pct) > max_jump_pct:
                        value_jumps.append({
                            'bar': i,
                            'pct': val_pct,
                            'prev': prev_val,
                            'curr': curr_val,
                        })
            
            if value_jumps:
                warnings.append(
                    f"[{penguin_name}] Detected {len(value_jumps)} "
                    f"suspicious portfolio value jumps > {max_jump_pct*100:.0f}%"
                )
                for jump in value_jumps:
                    bar_idx = jump['bar']
                    date_str = bar_timestamps[bar_idx].strftime('%Y-%m-%d %H:%M:%S') if bar_timestamps and bar_idx < len(bar_timestamps) else 'N/A'
                    warnings.append(
                        f"  Bar {bar_idx} @ {date_str}: "
                        f"{jump['pct']:+.2%} (${jump['prev']:,.2f} → ${jump['curr']:,.2f})"
                    )
    
    return warnings, bad_bar_indices_by_penguin
