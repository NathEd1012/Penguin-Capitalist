"""Validation and consistency checking utilities for detecting data quality issues."""


def check_consistency(results, max_jump_pct=0.15, bar_timestamps=None):
    """
    Validate backtesting results for data quality issues and suspicious patterns.
    
    Args:
        results: Dict[penguin_name] = (Portfolio, metrics_dict)
        max_jump_pct: Maximum allowed jump percentage (default 15%)
        bar_timestamps: List of datetime objects for each bar (optional)
    
    Returns:
        List of warning strings
    """
    warnings = []
    
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
            suspicious_jumps = []
            
            for i in range(1, len(trade_prices)):
                prev_price = trade_prices[i-1]
                curr_price = trade_prices[i]
                
                if prev_price > 0:
                    price_pct = (curr_price - prev_price) / prev_price
                    
                    if abs(price_pct) > max_jump_pct:
                        suspicious_jumps.append({
                            'trade_idx': i,
                            'symbol': portfolio.trades[i].symbol,
                            'pct': price_pct,
                            'prev': prev_price,
                            'curr': curr_price,
                        })
            
            if suspicious_jumps:
                warnings.append(
                    f"[{penguin_name}] Detected {len(suspicious_jumps)} "
                    f"suspicious price jumps > {max_jump_pct*100:.0f}%"
                )
                for jump in suspicious_jumps[:3]:  # Show first 3
                    trade = portfolio.trades[jump['trade_idx']]
                    date_str = trade.timestamp.strftime('%Y-%m-%d %H:%M:%S') if trade.timestamp else 'N/A'
                    warnings.append(
                        f"  Trade #{jump['trade_idx']} ({jump['symbol']}) @ {date_str}: "
                        f"{jump['pct']:+.2%} (${jump['prev']:.2f} → ${jump['curr']:.2f})"
                    )
        
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
                for jump in value_jumps[:3]:  # Show first 3
                    bar_idx = jump['bar']
                    date_str = bar_timestamps[bar_idx].strftime('%Y-%m-%d %H:%M:%S') if bar_timestamps and bar_idx < len(bar_timestamps) else 'N/A'
                    warnings.append(
                        f"  Bar {bar_idx} @ {date_str}: "
                        f"{jump['pct']:+.2%} (${jump['prev']:,.2f} → ${jump['curr']:,.2f})"
                    )
    
    return warnings
