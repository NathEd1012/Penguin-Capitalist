"""Execute prepared accounting events without re-cleaning market data."""


def event_schedule(data):
    schedule = {}
    for rows in data.values():
        for event in getattr(rows, 'events', ()):
            schedule.setdefault(event[0], []).append(event)
    return schedule


def apply_events(events, portfolios, price_history, volume_history, timestamp, benchmark_history=None):
    """Return symbols whose pre-event pending orders must be cancelled."""
    affected = set()
    for _, kind, symbol, payload in events:
        affected.add(symbol)
        if kind == 'stale':
            price_history[symbol].clear()
            volume_history[symbol].clear()
            if benchmark_history is not None:
                benchmark_history[symbol].clear()
            for portfolio in portfolios.values():
                quantity = portfolio.get_position(symbol)
                if quantity > 0:
                    portfolio.sell(symbol, quantity, payload, timestamp, reason="data gap >72h")
            continue
        effective_at, children, parent_mark = payload
        for portfolio in portfolios.values():
            quantity = portfolio.get_position(symbol)
            opened = portfolio.position_opened_at.get(symbol)
            if quantity <= 0 or opened is None or opened >= effective_at:
                continue
            if any(mark is None for _, _, mark, _ in children):
                # Missing distributed assets must never silently disappear from
                # equity. Conservative backtest fallback: exit the parent at its
                # last accepted pre-event mark, before the ex-distribution quote.
                portfolio.sell(symbol, quantity, portfolio.last_known_prices[symbol], timestamp, reason="unpriced distribution protection")
                continue
            keys = {(f"{event.get('source_symbol', symbol)}:{event['date']}:{child}", effective_at)
                    for child, _, _, event in children}
            if keys <= portfolio._applied_distributions:
                continue
            book_cost = quantity * portfolio.cost_basis.get(symbol, 0.0)
            child_book = {child: portfolio.get_position(child) * portfolio.cost_basis.get(child, 0.0)
                          for child, _, _, _ in children}
            distribution = {symbol: [
                (effective_at, event, event.get("source_symbol", symbol), child, ratio)
                for child, ratio, _, event in children
            ]}
            portfolio.apply_distributions(timestamp, distribution)
            total_market = quantity * (parent_mark + sum(ratio * mark for _, ratio, mark, _ in children))
            parent = children[0][3].get('target_symbol', symbol)
            if total_market > 0:
                portfolio.cost_basis[parent] = book_cost * quantity * parent_mark / total_market / portfolio.get_position(parent)
            for child, ratio, mark, _ in children:
                portfolio.last_known_prices[child] = mark
                if total_market > 0:
                    allocated = book_cost * quantity * ratio * mark / total_market
                    portfolio.cost_basis[child] = (child_book[child] + allocated) / portfolio.get_position(child)
    return affected
