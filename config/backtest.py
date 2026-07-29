"""Backtest timing and execution configuration."""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ========== BACKTEST TIMING SETTINGS ==========

# Start date for backtest (ISO format: YYYY-MM-DD HH:MM:SS in UTC)
# Examples:
#   "2026-01-03 10:30:00"  - Specific datetime
#   "2026-01-03"           - Defaults to 00:00:00

def _parse_config_date(value):
    """Parse a configuration date value.

    Accepts:
    - integer/epoch seconds (int or numeric string)
    - ISO datetime string: "YYYY-MM-DD HH:MM:SS" (assumed UTC if no tz)
    - date-only string: "YYYY-MM-DD"
    - special keyword: "TODAY" (resolves to yesterday at 23:50 UTC)
    """
    if value is None:
        return None

    # If already a datetime, return as-is
    if isinstance(value, datetime):
        return value

    s = str(value).strip()
    # Special keyword
    if s.upper() == "TODAY":
        return (datetime.now(timezone.utc).replace(hour=23, minute=50, second=0, microsecond=0)
                - timedelta(days=1))

    # Try numeric epoch
    try:
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return datetime.fromtimestamp(int(s), tz=timezone.utc)
    except Exception:
        pass

    # Try parsing with common formats
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue

    raise ValueError(f"Cannot parse date from config value: {value!r}")


def _parse_config_float(value, setting_name: str) -> float:
    """Parse numeric config values provided via environment variables."""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Cannot parse float for {setting_name}: {value!r}") from exc


def _normalize_run_directory_name(name: str) -> str:
    run_name = str(name).strip()
    if not run_name:
        return "run"

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if any(ch not in allowed for ch in run_name):
        raise ValueError("RUN_LOG_NAME may only contain letters, numbers, '-' and '_'.")

    return run_name


def _next_available_run_name(run_log_dir: Path, directory_name: str) -> str:
    base_name = _normalize_run_directory_name(directory_name)

    if base_name == "run":
        counter = 1
        while (run_log_dir / f"run_{counter}").exists():
            counter += 1
        return f"run_{counter}"

    candidate = base_name
    suffix = 1
    while (run_log_dir / candidate).exists():
        candidate = f"{base_name}_{suffix}"
        suffix += 1
    return candidate


def get_run_output_dir(base_dir: Path, run_log_name: str) -> Path:
    """Return the directory where the current run should be written."""
    if str(run_log_name).strip() == "0":
        run_test_dir = base_dir / "run_test"
        run_test_dir.mkdir(parents=True, exist_ok=True)
        return run_test_dir

    run_log_dir = base_dir / "run_log"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    run_name = _next_available_run_name(run_log_dir, run_log_name)
    run_dir = run_log_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir

START_DATEx = "2024-01-01 00:00:00"
START_DATE = _parse_config_date(os.getenv("FIXED_START", START_DATEx))




# Stop date for backtest
# Special keyword "TODAY" resolves to yesterday at 23:50 UTC 
# (to avoid Alpaca recent SIP data restrictions)
# Examples:
#   "TODAY"                - Use yesterday's end-of-day
#   "2026-02-03 21:30:00"  - Specific end datetime
STOP_DATEx = "2026-07-01 00:00:00" #"TODAY"
STOP_DATE = _parse_config_date(os.getenv("FIXED_STOP", STOP_DATEx))

# ========== TIMEFRAME / BINNING ==========
# Candle interval for bars
# Supported values: "1m", "5m", "15m", "1h", "1d"
#   "1m"  - 1-minute bars (highest granularity, more data)
#   "5m"  - 5-minute bars
#   "15m" - 15-minute bars
#   "1h"  - 1-hour bars
#   "1d"  - Daily bars (lowest granularity, less data)
BINNING = "1m"

# ========== RUN ARCHIVING SETTINGS ==========
# Run output folder name.
# "0" - Only update run_test/
# Any other valid name - Archive each run to a dedicated run_log folder
RUN_LOG_NAMEx = "TestRun"
RUN_LOG_NAME = os.getenv("RUN_LOG_NAME", RUN_LOG_NAMEx)

# ========== ARTIFACT EXPORT SETTINGS ==========
# 0 - Do not save per-strategy CSV summaries
# 1 - Save per-strategy CSV summaries in artifacts/csv
SAVE_CSVx = 0
SAVE_CSV = int(os.getenv("SAVE_CSV", SAVE_CSVx))


# ========== PORTFOLIO SETTINGS ==========
# Initial capital to start backtesting with (USD)
INITIAL_CAPITAL = 100000.0

# Execution transaction cost per trade (USD)
EXEC_TRANSACTION_COSTx = 1.0
EXEC_TRANSACTION_COST = _parse_config_float(os.getenv("FIXED_EXEC_TC", EXEC_TRANSACTION_COSTx), "FIXED_EXEC_TC")


__all__ = [
    "START_DATE",
    "STOP_DATE",
    "BINNING",
    "RUN_LOG_NAME",
    "SAVE_CSV",
    "INITIAL_CAPITAL",
    "EXEC_TRANSACTION_COST",
    "get_run_output_dir",
]
