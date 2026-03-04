#!/usr/bin/env python3
"""
Test market data system and plot all active trading stocks.
Fetches 1 year of historical data and generates yearly candlestick + volume charts.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market_data import get_bars
from datetime import datetime, timedelta
import pytz
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import logging

logging.basicConfig(level=logging.WARNING)

print("=" * 80)
print("MARKET DATA VISUALIZATION - ACTIVE TRADING SYMBOLS")
print("=" * 80)

# Load symbols and active penguins from root config.py
root_config = {}
with open("config.py") as f:
    exec(f.read(), root_config)

SYMBOLS = root_config.get("SYMBOLS", [])
ACTIVE_PENGUINS = root_config.get("ACTIVE_PENGUINS", [])

active_penguin_names = [p.__name__ for p in ACTIVE_PENGUINS]
print(f"\nActive Penguins: {', '.join(active_penguin_names)}\n")
print(f"Trading {len(SYMBOLS)} symbols")

# Date range: use historical data (2025 full year - confirmed available)
start = datetime(2025, 1, 1, tzinfo=pytz.UTC)
end = datetime(2025, 12, 31, tzinfo=pytz.UTC)

print(f"Date range: {start.date()} to {end.date()} (historical data)")
print()

# Fetch data for all symbols
data = {}
successful = []
failed = []

print("Fetching historical data...")
for symbol in SYMBOLS:
    try:
        df = get_bars(symbol, start, end, "1d")
        if len(df) > 0:
            data[symbol] = df
            successful.append(symbol)
            print(f"  ✓ {symbol}: {len(df)} bars")
        else:
            failed.append(symbol)
            print(f"  ⚠ {symbol}: No data")
    except Exception as e:
        failed.append(symbol)
        print(f"  ✗ {symbol}: {str(e)[:50]}")

print(f"\nSummary: {len(successful)} successful, {len(failed)} failed")

if not successful:
    print("ERROR: No data fetched. Cannot generate plots.")
    sys.exit(1)

# Create visualization directory
plot_dir = Path("assistive_scripts/market_data_plots")
plot_dir.mkdir(exist_ok=True)

print(f"\nGenerating plots in {plot_dir}/...")

# Generate individual plots for each successful symbol
for symbol in successful:
    df = data[symbol]
    
    # Create figure with 2 subplots: candlestick + volume
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), 
                                    gridspec_kw={'height_ratios': [3, 1]},
                                    sharex=True)
    
    # Plot candlestick chart
    width = 0.6
    width2 = 0.1
    
    for idx, row in df.iterrows():
        ts = mdates.date2num(row['timestamp'])
        open_price = row['open']
        close_price = row['close']
        high_price = row['high']
        low_price = row['low']
        
        # Color: green for up, red for down
        color = 'green' if close_price >= open_price else 'red'
        
        # Wick (high-low line)
        ax1.plot([ts, ts], [low_price, high_price], color=color, linewidth=0.5)
        
        # Body (open-close rectangle)
        height = abs(close_price - open_price)
        bottom = min(open_price, close_price)
        rect = Rectangle((ts - width/2, bottom), width, height, 
                         facecolor=color, edgecolor=color, alpha=0.8)
        ax1.add_patch(rect)
    
    # Volume bars
    colors_vol = ['green' if df.iloc[i]['close'] >= df.iloc[i]['open'] else 'red' 
                  for i in range(len(df))]
    ax2.bar(mdates.date2num(df['timestamp']), df['volume'], 
            width=width2, color=colors_vol, alpha=0.6)
    
    # Format axes
    ax1.set_ylabel('Price ($)', fontsize=10)
    ax1.set_title(f"{symbol} - Yearly Candlestick Chart", fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.label.set_color('black')
    
    ax2.set_ylabel('Volume', fontsize=10)
    ax2.set_xlabel('Date', fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Format x-axis dates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add statistics
    stats_text = (
        f"Close: ${df['close'].iloc[-1]:.2f} | "
        f"High: ${df['high'].max():.2f} | "
        f"Low: ${df['low'].min():.2f} | "
        f"Avg Vol: {df['volume'].mean()/1e6:.1f}M"
    )
    fig.text(0.5, 0.02, stats_text, ha='center', fontsize=9, style='italic')
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    
    # Save plot
    plot_file = plot_dir / f"{symbol}_yearly.png"
    plt.savefig(plot_file, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved {plot_file.name}")

# Generate summary plot - all symbols on one page (grid)
if len(successful) > 0:
    import math
    cols = 3
    rows = math.ceil(len(successful) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(16, 4*rows))
    axes = axes.flatten() if len(successful) > 1 else [axes]
    
    for idx, symbol in enumerate(successful):
        ax = axes[idx]
        df = data[symbol]
        
        # Plot closing price
        ax.plot(mdates.date2num(df['timestamp']), df['close'], 
                color='steelblue', linewidth=1.5, label='Close')
        
        # Add high/low as shaded area
        ax.fill_between(mdates.date2num(df['timestamp']), df['low'], df['high'],
                        alpha=0.2, color='gray', label='High-Low Range')
        
        ax.set_title(f"{symbol}", fontsize=10, fontweight='bold')
        ax.set_ylabel('Price ($)', fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc='best')
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=7)
    
    # Hide unused subplots
    for idx in range(len(successful), len(axes)):
        axes[idx].set_visible(False)
    
    fig.suptitle(f'Yearly Performance - {len(successful)} Symbols', 
                 fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    summary_file = plot_dir / "summary_all_symbols.png"
    plt.savefig(summary_file, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved {summary_file.name}")

print()
print("=" * 80)
print(f"✅ Plots generated successfully!")
print(f"   Location: {plot_dir.resolve()}")
print(f"   Symbols plotted: {len(successful)}/{len(SYMBOLS)}")
print("=" * 80)

