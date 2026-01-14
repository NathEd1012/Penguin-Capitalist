def evaluate(portfolio, price_history):
    final_prices = {s: prices[-1] for s, prices in price_history.items()}

    final_value = portfolio.value(final_prices)

    oracle = 0
    for s, prices in price_history.items():
        if prices:
            oracle += max(prices) - min(prices)

    return {
        "final_value": round(final_value, 2),
        "trades": portfolio.trades,
        "cash": round(portfolio.cash, 2),
        "oracle_edge": round(oracle, 2),
    }
