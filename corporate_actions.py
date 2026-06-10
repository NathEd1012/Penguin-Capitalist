"""Hardcoded corporate action registry used by backtesting.

This module is intentionally explicit and human-readable so split-sensitive
symbols can be maintained in one place.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

# Forward splits (price scales down after event date)
SPLITS: Dict[str, List[Dict[str, str]]] = {
    "AAPL": [
        {
            "date": "2020-08-31",
            "type": "split",
            "ratio": "4:1",
            "comment": "4-for-1 stock split",
        }
    ],
    "BKNG": [
    {
        "date": "2026-04-06",
        "type": "split",
        "ratio": "25:1",
        "comment": "25-for-1 stock split",
    }
    ],
    "AMZN": [
        {
            "date": "2022-06-06",
            "type": "split",
            "ratio": "20:1",
            "comment": "20-for-1 stock split",
        }
    ],
    "GOOGL": [
        {
            "date": "2022-07-18",
            "type": "split",
            "ratio": "20:1",
            "comment": "20-for-1 stock split",
        }
    ],
    "NVDA": [
        {
            "date": "2024-06-10",
            "type": "split",
            "ratio": "10:1",
            "comment": "10-for-1 stock split",
        }
    ],
    "MSTR": [
        {
            "date": "2024-08-08",
            "type": "split",
            "ratio": "10:1",
            "comment": "10-for-1 stock split",
        }
    ],
    "SSO": [
        {
            "date": "2025-11-20",
            "type": "split",
            "ratio": "2:1",
            "comment": "Known split handling used by this backtest branch",
        }
    ],
    "WMT": [
        {
            "date": "2024-02-26",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split",
        }
    ],
    "TSLA": [
        {
            "date": "2020-08-31",
            "type": "split",
            "ratio": "5:1",
            "comment": "5-for-1 stock split",
        },
        {
            "date": "2022-08-25",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split",
        },
    ],
}

# Reverse splits (price scales up after event date)
REVERSE_SPLITS: Dict[str, List[Dict[str, str]]] = {
    "DNA": [
        {
            "date": "2024-08-20",
            "type": "reverse_split",
            "ratio": "1:40",
            "comment": "1-for-40 reverse split; split-adjusted trading began on NYSE",
        }
    ],
    "GE": [
        {
            "date": "2021-08-02",
            "type": "reverse_split",
            "ratio": "1:8",
            "comment": "1-for-8 reverse split",
        }
    ]
}

# Ticker symbol changes (no direct price scaling by default)
TICKER_CHANGES: Dict[str, List[Dict[str, str]]] = {
    "META": [
        {
            "date": "2022-06-09",
            "type": "ticker_change",
            "ratio": "1:1",
            "comment": "Ticker changed from FB to META",
        }
    ]
}

# Mergers / reorganizations (no direct price scaling by default)
MERGERS: Dict[str, List[Dict[str, str]]] = {}



def _ratio_to_factor(ratio: str) -> float:
    """Convert ratio string like '10:1' or '1:8' to multiplicative factor."""
    left, right = ratio.split(":", 1)
    numerator = float(left)
    denominator = float(right)
    if denominator == 0:
        raise ValueError(f"Invalid corporate action ratio (division by zero): {ratio}")
    return numerator / denominator


def _parse_event_datetime(date_str: str) -> datetime:
    """Parse YYYY-MM-DD to UTC midnight datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def build_corporate_actions_by_symbol() -> Dict[str, List[Dict[str, str]]]:
    """Return a merged symbol->events mapping across all action categories."""
    combined: Dict[str, List[Dict[str, str]]] = {}
    for source in (SPLITS, REVERSE_SPLITS, TICKER_CHANGES, MERGERS):
        for symbol, events in source.items():
            combined.setdefault(symbol, []).extend(events)

    for symbol in combined:
        combined[symbol].sort(key=lambda event: event["date"])
    return combined


CORPORATE_ACTIONS: Dict[str, List[Dict[str, str]]] = build_corporate_actions_by_symbol()


def get_price_adjustment_events(symbol: str) -> List[Tuple[datetime, float, Dict[str, str]]]:
    """Get split/reverse-split events as (effective_datetime, factor, event)."""
    normalized = symbol.strip().upper()
    out: List[Tuple[datetime, float, Dict[str, str]]] = []

    for event in CORPORATE_ACTIONS.get(normalized, []):
        event_type = event.get("type", "")
        if event_type not in {"split", "reverse_split"}:
            continue

        event_date = _parse_event_datetime(event["date"])
        factor = _ratio_to_factor(event["ratio"])
        out.append((event_date, factor, event))

    out.sort(key=lambda item: item[0])
    return out


def has_corporate_action_near(
    symbol: str,
    timestamp: Optional[datetime],
    window_days: int = 2,
    action_types: Optional[Set[str]] = None,
) -> bool:
    """Return True if timestamp is within +/- window_days of a known event."""
    if timestamp is None:
        return False

    normalized = symbol.strip().upper()
    ts = timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)

    allowed_types = action_types or {"split", "reverse_split"}
    half_window = timedelta(days=window_days)

    for event in CORPORATE_ACTIONS.get(normalized, []):
        event_type = event.get("type", "")
        if event_type not in allowed_types:
            continue

        event_ts = _parse_event_datetime(event["date"])
        if (event_ts - half_window) <= ts <= (event_ts + half_window):
            return True

    return False
