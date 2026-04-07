# Bug Analysis: Duplicate Trade Prices

## Problem
Trades 20 and 66 in the BreakoutPenguin log show identical prices for BE stock:
- Trade 20: BUY 1 BE @ $158.46
- Trade 66: BUY 1 BE @ $158.46

Despite:
- 46 trades elapsed between them
- Trade 41 showing BE sold at $119.34 (indicating significant price movement)

## Root Cause
**Stale Quote Data from Alpaca IEX Feed**

The system uses Alpaca's IEX data feed (free tier), which has several limitations:

1. **Limited Coverage**: IEX only provides quotes for stocks actively traded on the IEX exchange
2. **Stale Data**: For illiquid or less-traded symbols, IEX may return quotes that are minutes or hours old
3. **No Timestamp Validation**: The code wasn't checking quote timestamps to detect stale data

### Code Flow:
1. `run_simulation.py` calls `client.get_bid_ask(symbol)` each minute
2. `data_client.py` fetches the latest quote from Alpaca's IEX feed
3. If the quote is stale (but still has valid bid/ask values), it's accepted
4. All penguins trade using the same stale price for that minute
5. When the quote updates, prices can jump dramatically (e.g., $158.46 → $119.34 → $158.46)

## Fixes Applied

### 1. Stale Quote Detection (data_client.py)
Added timestamp validation to reject quotes older than 5 minutes:

```python
def get_bid_ask(self, symbol: str):
    """Return (bid, ask) tuple or (None, None) if unavailable."""
    q = self.get_quote(symbol)
    if not q or q.bid_price is None or q.ask_price is None:
        return None, None
    
    # Check if quote is stale (older than 5 minutes)
    now = datetime.now(pytz.UTC)
    quote_time = q.timestamp if hasattr(q, 'timestamp') else None
    if quote_time:
        age_seconds = (now - quote_time).total_seconds()
        if age_seconds > 300:  # 5 minutes
            print(f"  ⚠️ Stale quote for {symbol}: {age_seconds:.0f}s old")
            return None, None
    
    return q.bid_price, q.ask_price
```

### 2. Enhanced Trade Logging (run_simulation.py)
Added markers to identify when synthetic prices are used:

```python
source_marker = " [synthetic]" if price_source.get(s) == "synthetic" else ""
trades_log[penguin.name].append((minute, f"BUY {qty} {s} @ ${ask:.2f}{source_marker}"))
```

### 3. Diagnostic Tool (check_quote_freshness.py)
Created a script to check quote freshness for all symbols before running simulations.

## Recommended Actions

### Immediate:
1. Run `python check_quote_freshness.py` to identify problematic symbols
2. Remove symbols with consistently stale data from SYMBOLS list
3. Monitor logs for `[synthetic]` markers during simulation runs

### Short-term:
1. Consider using only highly liquid stocks (e.g., SPY, QQQ, AAPL, MSFT, NVDA)
2. Adjust synthetic data generation to be more realistic for low-volume periods
3. Add quote age reporting in simulation output

### Long-term:
1. **Upgrade to Alpaca SIP feed** (requires paid subscription) for better quote coverage
2. Implement multiple data source fallback (e.g., IEX → SIP → Yahoo Finance)
3. Add quote quality metrics to portfolio evaluation

## Testing the Fix

Run the freshness check **during US market hours (9:30 AM - 4:00 PM ET)**:
```bash
python check_quote_freshness.py
```

⚠️ **Important**: Outside market hours, all quotes will appear stale since they're from the previous market close. The diagnostic is only meaningful during active trading.

Expected output during market hours will show which symbols have fresh vs stale quotes.

Symbols likely to have issues:
- BE (Bloom Energy) - showed exact duplicate prices
- Less liquid ETFs (COPX, PICK, REMX, etc.)
- Small-cap stocks

Symbols likely to be fine:
- NVDA, AAPL, MSFT (mega-cap tech)
- SPY, QQQ (high-volume ETFs)
- Major commodity ETFs (GLD, SLV)

## Impact

After these fixes:
- ✓ Stale quotes will be rejected (fallback to synthetic data)
- ✓ Logs will clearly show when synthetic vs real prices are used
- ✓ You can identify and remove problematic symbols
- ✓ More realistic backtesting with accurate price data
