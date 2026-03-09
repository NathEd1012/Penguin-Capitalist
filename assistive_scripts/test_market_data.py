#!/usr/bin/env python3
"""Test market data system and plot active trading stocks."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market_data import get_bars, init_router
from datetime import datetime, timedelta
import pytz
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_pdf import PdfPages
import logging
import math

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

# Date range: last 2 trading days of 2025
start = datetime(2025, 12, 29, tzinfo=pytz.UTC)
end = datetime(2025, 12, 31, tzinfo=pytz.UTC)

print(f"Date range: {start.date()} to {end.date()} (2 days of data)")
print()

try:
    init_router(use_cache=True, cache_dir="data_cache")
except ValueError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# Fetch data for all symbols
data = {}
successful = []
failed = []

print("Fetching historical data from Alpaca via provider router...")
for symbol in SYMBOLS:
    try:
        df = get_bars(symbol, start, end, "1m")
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

print(f"\nGenerating PDF with plots...")

# Create PDF file
pdf_path = plot_dir / "market_data_plots.pdf"

with PdfPages(pdf_path) as pdf:
    # === PAGE 1: Summary plot - all symbols on one page (grid) ===
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
        
        # Format x-axis (hourly for intraday data)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=7)
    
    # Hide unused subplots
    for idx in range(len(successful), len(axes)):
        axes[idx].set_visible(False)
    
    fig.suptitle(f'Market Data - {len(successful)} Symbols Overview', 
                 fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Added summary page")
    
    # === PAGES 2+: Individual plots for each symbol ===
    for symbol in successful:
        df = data[symbol]
        
        # Create figure with closing price and high/low
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # Plot closing price
        ax.plot(mdates.date2num(df['timestamp']), df['close'], 
                color='steelblue', linewidth=2.5, label='Close', zorder=3)
        
        # Add high/low as shaded area
        ax.fill_between(mdates.date2num(df['timestamp']), df['low'], df['high'],
                        alpha=0.2, color='gray', label='High-Low Range')
        
        # Format axes
        ax.set_title(f"{symbol} - Detailed View", fontsize=14, fontweight='bold')
        ax.set_ylabel('Price ($)', fontsize=12)
        ax.set_xlabel('Time', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11, loc='best')
        
        # Format x-axis (hourly for intraday data)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Add statistics
        stats_text = (
            f"Close: ${df['close'].iloc[-1]:.2f} | "
            f"High: ${df['high'].max():.2f} | "
            f"Low: ${df['low'].min():.2f} | "
            f"Avg Vol: {df['volume'].mean()/1e6:.1f}M"
        )
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10, style='italic')
        
        plt.tight_layout(rect=[0, 0.03, 1, 1])
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Added {symbol}")

print()
print("=" * 80)
print(f"✅ PDF generated successfully!")
print(f"   Location: {pdf_path.resolve()}")
print(f"   Symbols plotted: {len(successful)}/{len(SYMBOLS)}")
print("=" * 80)

