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
        
        # Track last seen prices to detect stale data
        self._last_prices = {}  # {symbol: (bid, ask, timestamp)}
        self._no_update_count = {}  # {symbol: consecutive_no_update_minutes}

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
        
        bid, ask = q.bid_price, q.ask_price
        now = datetime.now(pytz.UTC)
        quote_time = q.timestamp if hasattr(q, 'timestamp') else now
        
        # Check if quote is stale (older than 5 minutes)
        age_seconds = (now - quote_time).total_seconds()
        if age_seconds > 300:  # 5 minutes
            print(f"  ⚠️ Stale quote for {symbol}: {age_seconds:.0f}s old")
            return None, None
        
        # Check if price hasn't changed for multiple consecutive minutes
        # This catches IEX feed issues where quotes stop updating
        if symbol in self._last_prices:
            last_bid, last_ask, last_time = self._last_prices[symbol]
            
            # If bid/ask are identical to last check, increment counter
            if bid == last_bid and ask == last_ask:
                self._no_update_count[symbol] = self._no_update_count.get(symbol, 0) + 1
                
                # After 3 minutes of no updates during market hours, flag as stale
                if self._no_update_count[symbol] >= 3:
                    if self.market_is_open():
                        print(f"  ⚠️ No price update for {symbol} ({self._no_update_count[symbol]} min): ${bid:.2f} / ${ask:.2f}")
                        # Don't reject yet, but warn
            else:
                # Price changed, reset counter
                self._no_update_count[symbol] = 0
        
        # Store this quote for next comparison
        self._last_prices[symbol] = (bid, ask, now)
        
        return bid, ask

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
