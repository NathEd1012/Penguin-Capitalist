from datetime import datetime, timedelta
import pytz

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

    return price_history
