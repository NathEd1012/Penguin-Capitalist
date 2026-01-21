from datetime import datetime, timedelta
import pytz
import random

from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from data_client import AlpacaClient


def get_minute_bars(
    symbols,
    minutes=180,
):
    client = AlpacaClient()
    end = datetime.now(pytz.UTC)
    start = end - timedelta(minutes=minutes)

    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end,
        feed=client.feed,
    )

    bars = client.data.get_stock_bars(req)

    # Normalize to {symbol: [close prices]}
    price_history = {
        symbol: [bar.close for bar in bars[symbol]]
        for symbol in symbols
        if symbol in bars
    }

    # If any symbols are missing from the API response, provide a synthetic
    # fallback so simulations can run locally without failing.
    missing = [s for s in symbols if s not in price_history]
    if missing:
        print(
            f"⚠️ API did not return bars for: {', '.join(missing)}; using synthetic data for them"
        )

        def synthetic_prices(length, start=100.0):
            prices = [start]
            for _ in range(length - 1):
                # small percent change noise
                change_pct = random.gauss(0, 0.5)
                prices.append(max(0.01, prices[-1] * (1 + change_pct / 100)))
            return prices

        for i, s in enumerate(missing):
            # use a different start price per symbol to vary behavior
            price_history[s] = synthetic_prices(minutes, start=100.0 + i * 10)

    return price_history
