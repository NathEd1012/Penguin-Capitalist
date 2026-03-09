#!/usr/bin/env python3
"""
Quick convenience script to generate common spread visualization reports.

Usage examples:
    ./quick_spreads.py                    # Current backtest config
    ./quick_spreads.py recent             # Last 7 days
    ./quick_spreads.py all                # All-symbols, last month
    ./quick_spreads.py tech               # Tech symbols only
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subprocess
from datetime import datetime, timedelta
from config import SYMBOLS

def run_plot(symbols, start=None, end=None, output=None, all_symbols=False):
    """Run the plot_stocks_with_spreads.py script with given parameters."""
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "plot_stocks_with_spreads.py")
    ]
    
    if all_symbols:
        cmd.append("--all-symbols")
    elif symbols:
        cmd.extend(["--symbols"] + symbols)
    
    if start:
        cmd.extend(["--start", start])
    
    if end:
        cmd.extend(["--end", end])
    
    if output:
        cmd.extend(["--output", output])
    
    print(f"\nRunning: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    """Main entry point."""
    preset = sys.argv[1].lower() if len(sys.argv) > 1 else "config"
    
    today = datetime.now()
    
    if preset == "config":
        # Use config.py symbols and date range
        print("📊 Generating report using config.py settings...")
        run_plot(SYMBOLS, output="run_current/spreads_config.pdf")
    
    elif preset == "recent":
        # Last 7 days
        end = today.strftime("%Y-%m-%d")
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"📊 Generating report for last 7 days ({start} to {end})...")
        run_plot(SYMBOLS, start=start, end=end, output="run_current/spreads_recent.pdf")
    
    elif preset == "all":
        # All symbols, last month
        end = today.strftime("%Y-%m-%d")
        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        print(f"📊 Generating all-symbols report for ({start} to {end})...")
        run_plot(None, start=start, end=end, all_symbols=True, output="run_current/spreads_all.pdf")
    
    elif preset == "tech":
        # Tech symbols only
        from config.symbols import SYMBOLS as SYMBOL_DICT
        tech_symbols = SYMBOL_DICT.get("tech", [])
        end = today.strftime("%Y-%m-%d")
        start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        print(f"📊 Generating tech symbols report ({start} to {end})...")
        run_plot(tech_symbols, start=start, end=end, output="run_current/spreads_tech.pdf")
    
    elif preset == "commodities":
        # Commodity ETFs only
        from config.symbols import SYMBOLS as SYMBOL_DICT
        commodity_symbols = SYMBOL_DICT.get("commodities", [])
        end = today.strftime("%Y-%m-%d")
        start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        print(f"📊 Generating commodities report ({start} to {end})...")
        run_plot(commodity_symbols, start=start, end=end, output="run_current/spreads_commodities.pdf")
    
    elif preset == "miners":
        # Mining/metals only
        from config.symbols import SYMBOLS as SYMBOL_DICT
        miners_symbols = SYMBOL_DICT.get("miners", [])
        end = today.strftime("%Y-%m-%d")
        start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        print(f"📊 Generating miners report ({start} to {end})...")
        run_plot(miners_symbols, start=start, end=end, output="run_current/spreads_miners.pdf")
    
    else:
        print(f"Unknown preset: {preset}")
        print("\nAvailable presets:")
        print("  config      - Use config.py symbols and date range (default)")
        print("  recent      - Last 7 days of config symbols")
        print("  all         - All symbols, last month")
        print("  tech        - Tech sector, last 2 weeks")
        print("  commodities - Commodity ETFs, last 2 weeks")
        print("  miners      - Mining/metals ETFs, last 2 weeks")
        print("\nUsage: ./quick_spreads.py [preset]")
        sys.exit(1)


if __name__ == "__main__":
    main()
