"""
Visualize current stocks with synthetic bid/ask spreads in one PDF.

Creates a multi-page PDF with one chart per stock showing:
- Close price line colored by spread width (red=wide, green=tight)
- Bid/Ask spread band (gray shaded region)
- Date/time x-axis

Usage:
    python plot_stocks_with_spreads.py [--symbols SYMBOL1 SYMBOL2 ...] [--output OUTPUT_FILE]
    python plot_stocks_with_spreads.py --all-symbols
    python plot_stocks_with_spreads.py  # Uses symbols from config
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from matplotlib.collections import LineCollection
from matplotlib.backends.backend_pdf import PdfPages
import pytz

from config import SYMBOLS, START_DATE, STOP_DATE, BINNING
from market_data.provider_router import ProviderRouter
from backtest.data_loader import DataLoader
from scripts.synthetic_spread_model import SyntheticSpreadModel


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Visualize stocks with synthetic bid/ask spreads"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to plot (e.g., AAPL MSFT NVDA)"
    )
    parser.add_argument(
        "--all-symbols",
        action="store_true",
        help="Plot all symbols from all categories"
    )
    parser.add_argument(
        "--output",
        default="run_current/stocks_with_spreads.pdf",
        help="Output PDF file path"
    )
    parser.add_argument(
        "--start",
        help="Start date (overrides config)"
    )
    parser.add_argument(
        "--end",
        help="End date (overrides config)"
    )
    return parser.parse_args()


def get_symbols_to_plot(args):
    """Get list of symbols to plot based on args."""
    if args.symbols:
        return args.symbols
    elif args.all_symbols:
        # Flatten all symbols from config
        all_symbols = []
        for category_symbols in SYMBOLS.values():
            all_symbols.extend(category_symbols)
        return all_symbols
    else:
        # Use configured symbols
        from config import SYMBOLS as CONFIG_SYMBOLS
        return CONFIG_SYMBOLS


def parse_date(date_str, default_offset_days=-30):
    """
    Parse date string or return default.
    
    Accepts:
    - ISO format: "2026-02-20 14:30:00" or "2026-02-20"
    - With timezone: "2026-02-20 14:30:00+00:00"
    - Special keyword: "TODAY" (resolves to yesterday at 23:50 UTC to avoid recent SIP data restrictions)
    
    Assumes UTC if no timezone specified.
    """
    if not date_str:
        return datetime.now(pytz.UTC) + timedelta(days=default_offset_days)
    
    date_str = date_str.strip()
    
    # Handle special keyword "TODAY" (same as backtest_runner.py)
    if date_str.upper() == "TODAY":
        # Use yesterday at 23:50 UTC to avoid Alpaca recent SIP data restrictions
        yesterday = datetime.now(pytz.UTC).replace(
            hour=23, minute=50, second=0, microsecond=0
        ) - timedelta(days=1)
        return yesterday
    
    try:
        return pd.to_datetime(date_str, utc=True)
    except Exception as e:
        print(f"Could not parse date {date_str}: {e}")
        return datetime.now(pytz.UTC) + timedelta(days=default_offset_days)


def load_market_data(symbol, start, end, timeframe="1m", data_loader=None):
    """Load market data for a symbol."""
    try:
        # Try backtest DataLoader first (what the backtest uses)
        if data_loader is None:
            data_loader = DataLoader()
        
        # load_bars returns (data_dict, warning_msg)
        all_data, warning = data_loader.load_bars([symbol], start, end, timeframe)
        
        if warning:
            print(f"  Warning for {symbol}: {warning}")
        
        if symbol in all_data and len(all_data[symbol]) > 0:
            # Convert from nested dict format to DataFrame
            bars_data = all_data[symbol]
            timestamps = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            
            for ts_key, bar in bars_data.items():
                timestamps.append(pd.to_datetime(ts_key, utc=True))
                opens.append(bar.get('open', bar.get('o', 0)))
                highs.append(bar.get('high', bar.get('h', 0)))
                lows.append(bar.get('low', bar.get('l', 0)))
                closes.append(bar.get('close', bar.get('c', 0)))
                volumes.append(int(bar.get('volume', bar.get('v', 0))))
            
            df = pd.DataFrame({
                'timestamp': timestamps,
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            })
            df = df.sort_values('timestamp').reset_index(drop=True)
            return df
    except Exception as e1:
        pass  # Fall back to ProviderRouter silently
    
    # Fall back to ProviderRouter
    try:
        router = ProviderRouter(use_cache=True)
        df = router.get_bars(symbol, start, end, timeframe)
        return df
    except Exception as e2:
        print(f"Error loading data for {symbol}: {e2}")
        return None


def calculate_spreads(df, spread_model):
    """
    Calculate bid/ask spreads for each bar in the dataframe.
    
    Returns dataframe with additional columns: bid, ask, spread_width
    """
    if df is None or len(df) == 0:
        return None
    
    df = df.copy()
    bids = []
    asks = []
    spreads = []
    
    for _, row in df.iterrows():
        try:
            mid = (row['high'] + row['low']) / 2  # Use mid of candle as proxy
            bid, ask, spread = spread_model.get_bid_ask(
                mid_price=mid,
                high=row['high'],
                low=row['low'],
                timestamp=row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
                volume=row['volume']
            )
            bids.append(bid)
            asks.append(ask)
            spreads.append(spread)
        except Exception as e:
            bids.append(None)
            asks.append(None)
            spreads.append(None)
    
    df['bid'] = bids
    df['ask'] = asks
    df['spread_width'] = spreads
    return df


def plot_stock_with_spreads(ax, df, symbol):
    """
    Plot a single stock with bid/ask spreads.
    
    Shows:
    - Close price as a colored line (red=wide spread, green=tight spread)
    - Color gradient indicates spread width at each point in time
    """
    if df is None or len(df) == 0:
        ax.text(0.5, 0.5, f"No data available for {symbol}",
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title(f"{symbol} - No Data")
        return
    
    # Use timestamps for x-axis
    x = df['timestamp']
    mid_price = df['close']
    spread_width = df['spread_width']
    
    # Remove NaN values for plotting
    mask = (mid_price.notna()) & (spread_width.notna())
    x_valid = x[mask]
    mid_valid = mid_price[mask]
    spread_valid = spread_width[mask]
    
    if len(x_valid) == 0:
        ax.text(0.5, 0.5, f"Invalid data for {symbol}",
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title(f"{symbol} - Invalid Data")
        return
    
    # Convert to numpy arrays
    x_numeric = mdates.date2num(x_valid.values)
    price_array = mid_valid.values
    spread_array = spread_valid.values
    
    # Create line segments for color mapping
    points = np.array([x_numeric, price_array]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    # Normalize spread values for coloring.
    # Use logarithmic scaling so small spreads are easier to distinguish.
    spread_min = spread_array.min()
    spread_max = spread_array.max()
    positive_spreads = spread_array[spread_array > 0]

    if len(positive_spreads) > 0 and spread_max > 0:
        log_vmin = max(positive_spreads.min(), spread_max * 1e-6)
        norm = mcolors.LogNorm(vmin=log_vmin, vmax=spread_max)
        spread_for_color = np.clip(spread_array[:-1], log_vmin, None)
    else:
        # Fallback for degenerate data (all spreads are zero/non-positive)
        norm = plt.Normalize(vmin=0, vmax=1)
        spread_for_color = np.zeros_like(spread_array[:-1])
    
    # Calculate variable line widths based on spread
    # Small spreads (green) get thin lines (1.0), large spreads (red) get thick lines (2.8)
    spread_normalized = (spread_array[:-1] - spread_min) / (spread_max - spread_min + 1e-10)
    linewidths = 1.0 + spread_normalized * 1.8  # Range from 1.0 to 2.8
    
    # Create colored line collection with variable widths
    lc = LineCollection(segments, cmap='RdYlGn_r', norm=norm, zorder=2)
    lc.set_array(spread_for_color)  # Color each segment by its starting spread
    lc.set_linewidths(linewidths)
    ax.add_collection(lc)
    
    # Add colorbar
    cbar = plt.colorbar(lc, ax=ax, pad=0.02)
    cbar.set_label('Spread Width ($, log scale)', rotation=270, labelpad=15, fontsize=10)
    cbar.ax.tick_params(labelsize=9)
    
    # Formatting
    ax.set_title(f"{symbol} - Price History (Colored by Spread)", fontsize=13, fontweight='bold')
    ax.set_xlabel("Date/Time (UTC)", fontsize=11)
    ax.set_ylabel("Price ($)", fontsize=11)
    ax.grid(True, alpha=0.3, zorder=0)
    
    # Format x-axis for dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Set axis limits
    ax.set_xlim(x_valid.min(), x_valid.max())
    y_range = price_array.max() - price_array.min()
    if y_range < 0.01:
        y_padding = 1.0
    else:
        y_padding = y_range * 0.05
    ax.set_ylim(price_array.min() - y_padding, price_array.max() + y_padding)
    
    # Add stats text with date range and spread info
    date_start = x_valid.iloc[0].strftime('%m-%d %H:%M') if hasattr(x_valid.iloc[0], 'strftime') else str(x_valid.iloc[0])
    date_end = x_valid.iloc[-1].strftime('%m-%d %H:%M') if hasattr(x_valid.iloc[-1], 'strftime') else str(x_valid.iloc[-1])
    stats_text = (
        f"Data Points: {len(price_array)}\n"
        f"Period: {date_start}\n"
        f"     to {date_end}\n"
        f"Price: ${price_array.min():.2f} - ${price_array.max():.2f}\n"
        f"Spread: ${spread_min:.4f} - ${spread_max:.4f}\n"
        f"Avg Spread: ${spread_array.mean():.4f}"
    )
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))


def create_pdf_report(symbols, start, end, output_file):
    """Create PDF with one chart per symbol."""
    
    print(f"Creating PDF report: {output_file}")
    print(f"Symbols: {symbols}")
    print(f"Date range: {start} to {end}")
    print()
    
    spread_model = SyntheticSpreadModel()
    
    # Initialize data loader once
    try:
        data_loader = DataLoader()
    except ValueError as e:
        print(f"Warning: Could not initialize DataLoader: {e}")
        data_loader = None
    
    pdf_path = Path(output_file)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    
    with PdfPages(str(pdf_path)) as pdf:
        for symbol in symbols:
            print(f"Processing {symbol}...", end=" ", flush=True)
            
            # Load data
            df = load_market_data(symbol, start, end, BINNING, data_loader)
            
            if df is None or len(df) == 0:
                print("❌ No data")
                continue
            
            # Calculate spreads
            df = calculate_spreads(df, spread_model)
            
            # Create figure
            fig, ax = plt.subplots(figsize=(14, 7))
            
            # Plot
            plot_stock_with_spreads(ax, df, symbol)
            
            # Add metadata
            fig.text(0.99, 0.01, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                    ha='right', va='bottom', fontsize=8, style='italic', color='gray')
            
            # Save to PDF
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            print("✓")
    
    print(f"\n✅ Report saved to: {output_file}")


def main():
    """Main execution."""
    args = parse_arguments()
    
    # Get symbols
    symbols = get_symbols_to_plot(args)
    
    # Parse dates - use config if not provided via args
    if args.start:
        start = parse_date(args.start, default_offset_days=-30)
    else:
        # Use START_DATE from config
        start = parse_date(START_DATE, default_offset_days=-30)
    
    if args.end:
        end = parse_date(args.end, default_offset_days=0)
    else:
        # Use STOP_DATE from config
        end = parse_date(STOP_DATE, default_offset_days=0)
    
    print("\n" + "="*70)
    print("STOCKS WITH SYNTHETIC SPREADS - PDF REPORT")
    print("="*70)
    
    # Create report
    create_pdf_report(symbols, start, end, args.output)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
