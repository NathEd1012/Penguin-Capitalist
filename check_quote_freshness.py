#!/usr/bin/env python3
"""
Check the freshness of quotes from Alpaca API and detect stale symbols.
This helps diagnose stale price data issues.

NOTE: This check is most useful during market hours (9:30 AM - 4:00 PM ET).
      Outside these hours, all quotes will appear stale.

Usage:
    python check_quote_freshness.py              # Single snapshot
    python check_quote_freshness.py --monitor    # Monitor for 5 minutes, checking every 30 seconds
"""

import sys
import time
from datetime import datetime
import pytz
from data_client import AlpacaClient
from config import SYMBOLS


def single_check(client, now_et):
    """Do a single quote check."""
    now = datetime.now(pytz.UTC)
    
    print(f"\n{'Symbol':<10} {'Bid':<12} {'Ask':<12} {'Spread':<10} {'Age (sec)':<12} {'Status'}")
    print("=" * 80)
    
    stale_symbols = []
    missing_symbols = []
    unchanged_symbols = []
    
    for symbol in SYMBOLS:
        try:
            quote = client.get_quote(symbol)
            
            if not quote or quote.bid_price is None or quote.ask_price is None:
                print(f"{symbol:<10} {'N/A':<12} {'N/A':<12} {'N/A':<10} {'N/A':<12} ❌ NO QUOTE")
                missing_symbols.append(symbol)
                continue
            
            bid, ask = quote.bid_price, quote.ask_price
            spread = ask - bid
            spread_pct = (spread / ((bid + ask) / 2) * 100) if (bid + ask) > 0 else 0
            
            # Get quote timestamp
            quote_time = quote.timestamp if hasattr(quote, 'timestamp') else None
            
            if not quote_time:
                age_str = "UNKNOWN"
                status = "⚠️  NO TIMESTAMP"
                stale_symbols.append(symbol)
            else:
                age_seconds = (now - quote_time).total_seconds()
                age_str = f"{age_seconds:.1f}"
                
                if age_seconds > 300:  # 5 minutes
                    status = f"❌ STALE ({age_seconds/60:.1f} min)"
                    stale_symbols.append(symbol)
                elif age_seconds > 60:  # 1 minute
                    status = f"⚠️  OLD ({age_seconds:.0f} sec)"
                else:
                    status = "✓ FRESH"
            
            print(f"{symbol:<10} ${bid:<11.2f} ${ask:<11.2f} ${spread:<9.2f} {age_str:<12} {status}")
            
        except Exception as e:
            print(f"{symbol:<10} {'ERROR':<12} {'ERROR':<12} {'ERROR':<10} {'N/A':<12} ❌ {type(e).__name__}")
            missing_symbols.append(symbol)
    
    return stale_symbols, missing_symbols


def monitor_prices(client, duration_minutes=5, interval_seconds=30):
    """Monitor price changes over time to detect stuck quotes."""
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    
    print(f"\n📊 Monitoring prices for {duration_minutes} minutes (every {interval_seconds} seconds)...\n")
    
    price_history = {}  # {symbol: [(timestamp, bid, ask), ...]}
    no_change_count = {}  # {symbol: consecutive_checks_with_no_change}
    
    start_time = time.time()
    check_count = 0
    
    while time.time() - start_time < duration_minutes * 60:
        check_count += 1
        now = datetime.now(pytz.UTC)
        now_et = datetime.now(pytz.timezone("US/Eastern"))
        
        print(f"\n[Check {check_count}] {now_et.strftime('%H:%M:%S')}")
        print("-" * 80)
        
        for symbol in SYMBOLS:
            try:
                quote = client.get_quote(symbol)
                
                if not quote or quote.bid_price is None or quote.ask_price is None:
                    continue
                
                bid, ask = quote.bid_price, quote.ask_price
                
                if symbol not in price_history:
                    price_history[symbol] = []
                    no_change_count[symbol] = 0
                
                # Check if price changed from last check
                if price_history[symbol]:
                    last_bid, last_ask = price_history[symbol][-1][1:]
                    if bid == last_bid and ask == last_ask:
                        no_change_count[symbol] += 1
                        status = f"❌ NO CHANGE ({no_change_count[symbol]} checks) ${bid:.2f} / ${ask:.2f}"
                    else:
                        no_change_count[symbol] = 0
                        status = f"✓ Updated: ${bid:.2f} / ${ask:.2f}"
                else:
                    status = f"  Initial: ${bid:.2f} / ${ask:.2f}"
                
                price_history[symbol].append((now, bid, ask))
                print(f"  {symbol:<10} {status}")
                
            except Exception as e:
                pass
        
        # Wait before next check
        if time.time() - start_time < duration_minutes * 60:
            time.sleep(interval_seconds)
    
    # Summary
    print("\n" + "=" * 80)
    print("MONITORING SUMMARY")
    print("=" * 80)
    
    stuck_symbols = {s: no_change_count[s] for s in no_change_count if no_change_count[s] > 0}
    
    if stuck_symbols:
        print(f"\n❌ Symbols with stuck quotes (no change for multiple checks):")
        for symbol, count in sorted(stuck_symbols.items(), key=lambda x: -x[1]):
            print(f"   {symbol}: No price change for {count} consecutive checks")
    else:
        print(f"\n✓ All symbols updated at least once during monitoring period")


def check_quote_freshness():
    """Main diagnostic function."""
    client = AlpacaClient(paper=True)
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    
    # Check if market is open
    try:
        market_open = client.market_is_open()
        clock = client.trading.get_clock()
    except Exception as e:
        print(f"⚠️  Could not check market status: {e}\n")
        market_open = None
        clock = None
    
    if market_open is False:
        print("⚠️  MARKET IS CURRENTLY CLOSED")
        if clock:
            next_open = clock.next_open
            time_to_open = (next_open - now_et).total_seconds()
            hours = time_to_open / 3600
            print(f"📅 Next market open: {next_open.strftime('%Y-%m-%d %H:%M:%S %Z')} ({hours:.1f} hours from now)")
        print("\n💡 This diagnostic is most useful during market hours (9:30 AM - 4:00 PM ET)")
        print("   Current quotes will be from market close and appear stale.\n")
    elif market_open:
        print("✓ Market is OPEN - quotes should be fresh\n")
    
    print(f"Checking quote freshness at {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    stale_symbols, missing_symbols = single_check(client, now_et)
    
    print("\n" + "=" * 80)
    print(f"\nSummary:")
    print(f"  Fresh quotes:   {len(SYMBOLS) - len(stale_symbols) - len(missing_symbols)}")
    print(f"  Stale quotes:   {len(stale_symbols)}")
    print(f"  Missing quotes: {len(missing_symbols)}")
    
    if stale_symbols:
        print(f"\n⚠️  Stale symbols: {', '.join(stale_symbols)}")
    if missing_symbols:
        print(f"❌ Missing symbols: {', '.join(missing_symbols)}")
    
    # Offer to run monitoring if market is open
    if market_open and len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        monitor_prices(client, duration_minutes=5, interval_seconds=30)
    elif market_open:
        print(f"\n💡 Run with --monitor flag to track price changes over 5 minutes:")
        print(f"   python check_quote_freshness.py --monitor")


if __name__ == "__main__":
    check_quote_freshness()
