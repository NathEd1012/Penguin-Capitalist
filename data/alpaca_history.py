from datetime import datetime, timedelta
import pytz
import re

from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed


def _format_data_api_error(exc: Exception) -> str:
    """Return a concise, user-friendly data API error message."""
    text = str(exc).strip()
    lower = text.lower()

    if "401" in lower or "authorization required" in lower:
        return "401 Unauthorized (check ALPACA_API_KEY/ALPACA_SECRET_KEY and account access)."

    if "<html" in lower or "<body" in lower:
        cleaned = re.sub(r"<[^>]+>", " ", text)
        cleaned = " ".join(cleaned.split())
        return cleaned[:180] if cleaned else "Data provider returned an HTML error response."

    return text[:180] if text else "Unknown data API error."


def get_minute_bars(
    symbols,
    minutes=180,
):
    from data_client import AlpacaClient
    
    client = AlpacaClient()
    end = datetime.now(pytz.UTC)
    start = end - timedelta(minutes=minutes)
    min_start = end - timedelta(days=7)
    if start > min_start:
        start = min_start

    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    try:
        bars = client.data.get_stock_bars(req)
    except Exception as exc:
        raise RuntimeError(_format_data_api_error(exc)) from exc
    bars_map = _normalize_bars_map(_extract_bars_map(bars))

    # Normalize to {symbol: [close prices]}
    symbols_upper = [s.upper() for s in symbols]
    price_history = {
        symbol: [bar.close for bar in bars_map.get(symbol, [])]
        for symbol in symbols_upper
    }

    return price_history


def get_timeframe_bars(
    symbols,
    timeframe: TimeFrame,
    lookback_days: int,
):
    from data_client import AlpacaClient
    
    client = AlpacaClient()
    end = datetime.now(pytz.UTC)

    days = max(lookback_days, 7)
    start = end - timedelta(days=days)
    min_start = end - timedelta(days=7)
    if start > min_start:
        start = min_start

    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=timeframe,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    try:
        bars_resp = client.data.get_stock_bars(req)
    except Exception as exc:
        raise RuntimeError(_format_data_api_error(exc)) from exc
    bars_map = _normalize_bars_map(_extract_bars_map(bars_resp))

    symbols_upper = [s.upper() for s in symbols]
    price_history = {
        symbol: [bar.close for bar in bars_map.get(symbol, [])]
        for symbol in symbols_upper
    }

    missing = [s for s in symbols_upper if not price_history.get(s)]
    if missing:
        print(
            f"⚠️ API did not return bars for: {', '.join(missing)}; leaving them empty"
        )

    return price_history


def _extract_bars_map(bars_response) -> dict:
    if bars_response is None:
        return {}

    if hasattr(bars_response, "data") and bars_response.data is not None:
        data = bars_response.data
        if hasattr(data, "keys"):
            return data

    if hasattr(bars_response, "df"):
        df = bars_response.df
        try:
            if hasattr(df, "columns") and "symbol" in df.columns:
                grouped = {}
                for symbol, group in df.groupby("symbol"):
                    grouped[str(symbol)] = list(group.itertuples(index=False))
                return grouped
            if hasattr(df, "index") and hasattr(df.index, "names"):
                if "symbol" in df.index.names:
                    grouped = {}
                    for symbol, group in df.groupby(level="symbol"):
                        grouped[str(symbol)] = list(group.itertuples(index=False))
                    return grouped
        except Exception:
            return {}

    try:
        if hasattr(bars_response, "keys"):
            return bars_response
    except Exception:
        return {}

    return {}


def _normalize_bars_map(bars_map: dict) -> dict:
    if not bars_map:
        return {}
    return {str(symbol).upper(): values for symbol, values in bars_map.items()}
