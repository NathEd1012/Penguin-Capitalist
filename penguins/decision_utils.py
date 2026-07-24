from __future__ import annotations

import inspect
from typing import Any, List, Optional

from backtest.portfolio import Portfolio


def call_penguin_decide(
    penguin: Any,
    symbol: str,
    mid_prices: List[float],
    bid: float,
    ask: float,
    portfolio: Portfolio,
    spy_prices: Optional[List[float]] = None,
    volumes: Optional[List[float]] = None,
) -> tuple[str, int]:
    """Call a penguin's decide method while remaining compatible with both legacy and context-aware signatures."""
    try:
        signature = inspect.signature(penguin.decide)
    except (TypeError, ValueError):
        signature = None

    if signature is not None:
        parameters = list(signature.parameters.values())
        has_spy_and_volumes = any(
            parameter.name in {"spy_prices", "volumes"} for parameter in parameters
        )
        if has_spy_and_volumes:
            return penguin.decide(
                symbol,
                mid_prices,
                bid,
                ask,
                portfolio,
                spy_prices=spy_prices,
                volumes=volumes,
            )

    return penguin.decide(symbol, mid_prices, bid, ask, portfolio)
