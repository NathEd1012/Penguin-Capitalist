# Plot Stocks with Synthetic Spreads

This script generates a PDF report visualizing your trading symbols with realistic bid/ask spreads calculated using the synthetic spread model.

## Overview

The script creates one chart per stock showing:
- **Close price** (as the mid-price line)
- **Bid/Ask band** (shaded blue region)
- **Spread width coloring** (red = wide spreads, green = tight spreads)
- **Statistics** (average spread, price range, number of bars)

## Usage

### Basic Usage (From Config)
Uses the symbols configured in `config.py` and the backtest date range:
```bash
python assistive_scripts/plot_stocks_with_spreads.py
```

### Specific Symbols
```bash
python assistive_scripts/plot_stocks_with_spreads.py --symbols AAPL MSFT NVDA
```

### All Available Symbols
```bash
python assistive_scripts/plot_stocks_with_spreads.py --all-symbols
```

### Custom Date Range
```bash
python assistive_scripts/plot_stocks_with_spreads.py \
  --symbols AAPL MSFT \
  --start "2026-02-20" \
  --end "2026-02-28"
```

### Custom Output Path
```bash
python assistive_scripts/plot_stocks_with_spreads.py \
  --symbols AAPL \
  --output "my_reports/spreads_report.pdf"
```

## Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--symbols` | Symbols to plot | `--symbols AAPL MSFT NVDA` |
| `--all-symbols` | Plot all symbols from config | (no argument) |
| `--start` | Start date | `--start "2026-02-20"` |
| `--end` | End date | `--end "2026-02-28"` |
| `--output` | Output PDF path | `--output "report.pdf"` |

## Examples

### View recent activity for your configured penguins:
```bash
python assistive_scripts/plot_stocks_with_spreads.py --output run_current/spreads_recent.pdf
```

### Deep dive into spreads for specific trading pairs:
```bash
python assistive_scripts/plot_stocks_with_spreads.py \
  --symbols LMT GLD AMD \
  --start "2026-02-01" \
  --end "2026-03-01" \
  --output run_current/spreads_analysis.pdf
```

### Generate full market overview:
```bash
python assistive_scripts/plot_stocks_with_spreads.py \
  --all-symbols \
  --start "2026-01-15" \
  --end "2026-03-09" \
  --output run_current/full_market_spreads.pdf
```

## Output Details

Each page in the PDF contains:
- **Title**: Symbol and description
- **Chart**: 
  - Blue shaded region = bid/ask spread band
  - Colored scatter points = close price (colored by spread width)
  - Red dashed line = bid price
  - Green dashed line = ask price
- **Colorbar**: Shows spread width intensity (USD)
- **Statistics box**: 
  - Number of bars
  - Price range
  - Average spread
  - Maximum spread
- **Timestamp**: Report generation time

## Data Caching

The script uses disk caching to speed up subsequent runs. Data is cached in `data_cache/`.

## Troubleshooting

**No data available for a symbol:**
- Check that the symbol is valid
- Ensure the date range has trading data
- Check that Alpaca API keys are configured (if using live data)

**Memory issues with many symbols:**
- Run separately with `--symbols SYMBOL1 SYMBOL2` for subsets
- Use shorter date ranges
- Combine PDFs manually

**Slow execution:**
- Data is cached after first run, so subsequent runs are much faster
- Use shorter date ranges for initial testing

## Integration with Backtesting

To analyze spreads for your recent backtest:
```bash
# Uses config.py symbols and date range
python assistive_scripts/plot_stocks_with_spreads.py
```

The visualization helps you understand:
- Which symbols have tight vs. wide spreads
- How spreads vary throughout the day
- Volume impact on spreads
- Cost impact on your trading
