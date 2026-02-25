"""Main entry point for historical backtesting simulation."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.backtest_runner import main


if __name__ == "__main__":
    main()
