"""Corporate action helpers used by backtesting and validation.

This module is the canonical import location for the project.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from .list_of_corp_act import (
    CORPORATE_ACTIONS,
    DISLOCATION_ACTION_TYPES,
    PRICE_ADJUSTMENT_ACTION_TYPES,
    REORGANIZATIONS,
    REVERSE_SPLITS,
    SPLITS,
    TICKER_CHANGES,
)


def _parse_event_datetime(date_str: str) -> datetime:
    """Parse YYYY-MM-DD to UTC midnight datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _ratio_to_factor(ratio: str) -> float:
    """Convert a ratio string like 10:1 or 1:20 into a price factor."""
    left, right = ratio.split(":", 1)
    numerator = float(left)
    denominator = float(right)

    if numerator == 0 or denominator == 0:
        raise ValueError(f"Invalid corporate action ratio: {ratio}")

    return denominator / numerator


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

    allowed_types = action_types or DISLOCATION_ACTION_TYPES
    half_window = timedelta(days=window_days)

    for event in CORPORATE_ACTIONS.get(normalized, []):
        event_type = event.get("type", "")

        if event_type not in allowed_types:
            continue

        event_ts = _parse_event_datetime(event["date"])

        if (event_ts - half_window) <= ts <= (event_ts + half_window):
            return True

    return False


def describe_corporate_action_near(
    symbol: str,
    timestamp: Optional[datetime],
    window_days: int = 2,
    action_types: Optional[Set[str]] = None,
) -> Optional[str]:
    """Return a short human-readable description for nearby corporate actions."""
    if timestamp is None:
        return None

    normalized = symbol.strip().upper()

    ts = timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)

    allowed_types = action_types or DISLOCATION_ACTION_TYPES
    half_window = timedelta(days=window_days)
    matches: List[str] = []

    for event in CORPORATE_ACTIONS.get(normalized, []):
        event_type = event.get("type", "")
        if event_type not in allowed_types:
            continue

        event_ts = _parse_event_datetime(event["date"])
        if not ((event_ts - half_window) <= ts <= (event_ts + half_window)):
            continue

        event_label = event_type.replace("_", " ")
        event_comment = event.get("comment") or event.get("ratio") or "corporate action"
        matches.append(f"{event_label} on {event['date']} ({event_comment})")

    if not matches:
        return None

    return "; ".join(matches)


def get_price_adjustment_events(symbol: str) -> List[Tuple[datetime, float, Dict[str, str]]]:
    """Return split and reverse-split events as (effective_datetime, factor, event)."""
    normalized = symbol.strip().upper()
    out: List[Tuple[datetime, float, Dict[str, str]]] = []

    for event in CORPORATE_ACTIONS.get(normalized, []):
        event_type = event.get("type", "")
        if event_type not in PRICE_ADJUSTMENT_ACTION_TYPES:
            continue

        event_date = _parse_event_datetime(event["date"])
        factor = _ratio_to_factor(event["ratio"])
        out.append((event_date, factor, event))

    out.sort(key=lambda item: item[0])
    return out
