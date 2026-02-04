# data_client.py
from __future__ import annotations

import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.enums import DataFeed


class AlpacaClient:
    def __init__(self, env_file: str = ".env", paper: bool = True):
        load_dotenv(env_file)

        self.trading = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
            paper=paper,
        )

        self.data = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
        )

        self.feed = DataFeed.IEX
        self.tz = pytz.timezone("US/Eastern")

    # ---------- Time ----------
    def now_et(self) -> datetime:
        return datetime.now(self.tz)

    # ---------- Market ----------
    def market_is_open(self) -> bool:
        return self.trading.get_clock().is_open

    # ---------- Price ----------
    def get_quote(self, symbol: str):
        """Get bid and ask prices."""
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=self.feed)
        return self.data.get_stock_latest_quote(req).get(symbol)

    def get_bid_ask(self, symbol: str):
        """Return (bid, ask) tuple or (None, None) if unavailable."""
        q = self.get_quote(symbol)
        if not q or q.bid_price is None or q.ask_price is None:
            return None, None
        return q.bid_price, q.ask_price

    def get_mid_price(self, symbol: str) -> Optional[float]:
        bid, ask = self.get_bid_ask(symbol)
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2

    # ---------- Orders ----------
    def buy_market(self, symbol: str, qty: int):
        return self.trading.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
        )

    def sell_market(self, symbol: str, qty: int):
        return self.trading.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        )
