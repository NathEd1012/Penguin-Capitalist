"""Corporate action helpers used by backtesting and validation.

This module is the canonical import location for the project.
"""

from __future__ import annotations

import os
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from .list_of_corp_act import _default_price_effective_at
from .list_of_corp_act import (
    CORPORATE_ACTIONS,
    DISLOCATION_ACTION_TYPES,
    PRICE_ADJUSTMENT_ACTION_TYPES,
    REORGANIZATIONS,
    REVERSE_SPLITS,
    SPLITS,
    TICKER_CHANGES,
)


PRICE_ADJUSTMENT_POLICY_VERSION = "canonical-price-volume-v3"


def _parse_event_datetime(date_str: str) -> datetime:
    """Parse date-only registry labels for proximity descriptions."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def price_effective_at(event: Dict[str, str]) -> datetime:
    """Resolve a split price boundary and require an aware timestamp."""
    value = event.get("price_effective_at")
    if not value:
        raise ValueError(
            f"Missing price_effective_at for {event.get('type', 'corporate action')} "
            f"on {event.get('date', '<missing date>')}"
        )
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"Naive price_effective_at is not allowed: {value}")
    return timestamp.astimezone(timezone.utc)


def corporate_action_registry_fingerprint() -> str:
    """Return a stable fingerprint for actions and split timing policy."""
    payload = {
        "policy": PRICE_ADJUSTMENT_POLICY_VERSION,
        "registry": CORPORATE_ACTIONS,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _ratio_to_factor(ratio: str) -> float:
    """Convert a ratio string like 10:1 or 1:20 into a price factor."""
    left, right = ratio.split(":", 1)
    numerator = float(left)
    denominator = float(right)

    if not all(math.isfinite(v) and v > 0 for v in (numerator, denominator)):
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

    if os.getenv("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
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

        event_ts = (
            price_effective_at(event)
            if event_type in PRICE_ADJUSTMENT_ACTION_TYPES
            else _parse_event_datetime(event["date"])
        )

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

    if os.getenv("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
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

        event_ts = (
            price_effective_at(event)
            if event_type in PRICE_ADJUSTMENT_ACTION_TYPES
            else _parse_event_datetime(event["date"])
        )
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
    if os.getenv("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
        return []
    normalized = symbol.strip().upper()
    out: List[Tuple[datetime, float, Dict[str, str]]] = []

    for event in CORPORATE_ACTIONS.get(normalized, []):
        event_type = event.get("type", "")
        if event_type not in PRICE_ADJUSTMENT_ACTION_TYPES:
            continue

        event_date = price_effective_at(event)
        factor = _ratio_to_factor(event["ratio"])
        out.append((event_date, factor, event))

    out.sort(key=lambda item: item[0])
    return out


def distribution_effective_at(event: Dict[str, str]) -> datetime:
    """Ex-distribution price boundary; legal payment dates are separate metadata."""
    value = event.get("distribution_effective_at") or _default_price_effective_at(event["date"])
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"Naive distribution_effective_at is not allowed: {value}")
    return timestamp.astimezone(timezone.utc)


def get_distribution_events(
    symbol: str,
) -> List[Tuple[datetime, Dict[str, str], str, str, float]]:
    """Return registered share distributions affecting ``symbol``."""
    if os.getenv("IGNORE_CORPORATE_ACTIONS", "").lower() in ("1", "true", "yes"):
        return []
    normalized = symbol.strip().upper()
    out: List[Tuple[datetime, Dict[str, str], str, str, float]] = []

    for registry_symbol, events in CORPORATE_ACTIONS.items():
        for event in events:
            distribution = event.get("distribution")
            source = event.get("source_symbol", registry_symbol)
            target = event.get("target_symbol")
            if not distribution or normalized not in {registry_symbol, source, target}:
                continue
            for item in distribution.split(";"):
                child, ratio = item.split(":", 1)
                if "/" in ratio:
                    numerator, denominator = ratio.split("/", 1)
                else:
                    numerator, denominator = ratio, "1"
                value = float(numerator) / float(denominator)
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f"Invalid distribution ratio: {ratio}")
                out.append(
                    (
                        distribution_effective_at(event),
                        event,
                        source,
                        child,
                        value,
                    )
                )

    out.sort(key=lambda item: item[0])
    return out
