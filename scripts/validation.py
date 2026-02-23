"""Validation and consistency checking utilities."""


def check_consistency(portfolio, latest_prices, curve_values, max_jump_pct=0.15):
    """Validate positions vs trade history and detect suspicious curve jumps."""
    warnings = []

    # 1) Positions vs trade history
    expected_qty = {}
    for t in portfolio.trade_history:
        expected_qty[t.symbol] = expected_qty.get(t.symbol, 0) + (
            t.qty if t.side == "BUY" else -t.qty
        )

    for symbol, pos in portfolio.positions.items():
        expected = expected_qty.get(symbol, 0)
        if expected != pos.qty:
            warnings.append(
                f"Position mismatch for {symbol}: positions={pos.qty}, trades={expected}"
            )

    for symbol, qty in expected_qty.items():
        if qty != 0 and symbol not in portfolio.positions:
            warnings.append(
                f"Missing position for {symbol}: trades imply qty={qty}, positions=0"
            )

    # 2) Curve vs portfolio value
    if curve_values:
        computed_value = portfolio.value(latest_prices)
        curve_value = curve_values[-1]

        if curve_value > 0:
            discrepancy = abs(computed_value - curve_value) / curve_value
            if discrepancy > 0.01:
                warnings.append(
                    f"Curve mismatch: computed={computed_value:.2f}, curve={curve_value:.2f}, delta={discrepancy:+.2%}"
                )

    # 3) Suspicious jumps
    if len(curve_values) > 1:
        for i in range(1, len(curve_values)):
            prev = curve_values[i - 1]
            curr = curve_values[i]
            if prev > 0:
                pct = (curr - prev) / prev
                if abs(pct) > max_jump_pct:
                    warnings.append(
                        f"Large jump at minute {i + 1}: {pct:+.2%} (from ${prev:,.2f} to ${curr:,.2f})"
                    )

    return warnings
