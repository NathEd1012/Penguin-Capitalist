"""Updated corporate action registry used by backtesting and validation.

This module keeps the maintained action tables in ``scripts`` while exposing the
same helper API that the rest of the codebase imports from ``corporate_actions``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple


# Forward splits: price scales down after event date
SPLITS: Dict[str, List[Dict[str, str]]] = {
    "AAPL": [
        {
            "date": "2020-08-31",
            "type": "split",
            "ratio": "4:1",
            "comment": "4-for-1 stock split",
        }
    ],

    "ADYEY": [
        {
            "date": "2021-08-24",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 ADR split",
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

    "AVGO": [
        {
            "date": "2024-07-15",
            "type": "split",
            "ratio": "10:1",
            "comment": "10-for-1 stock split; split-adjusted trading began",
        }
    ],

    "BKNG": [
        {
            "date": "2026-04-06",
            "type": "split",
            "ratio": "25:1",
            "comment": "25-for-1 stock split; split-adjusted trading began",
        }
    ],

    "CMG": [
        {
            "date": "2024-06-26",
            "type": "split",
            "ratio": "50:1",
            "comment": "50-for-1 stock split",
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

    "ISRG": [
        {
            "date": "2021-10-05",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split",
        }
    ],

    "KLAC": [
        {
            "date": "2026-06-12",
            "type": "split",
            "ratio": "10:1",
            "comment": "10-for-1 stock split; split-adjusted trading began",
        }
    ],

    "LRCX": [
        {
            "date": "2024-10-03",
            "type": "split",
            "ratio": "10:1",
            "comment": "10-for-1 stock split; split-adjusted trading began",
        }
    ],

    "MCHP": [
        {
            "date": "2021-10-13",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 stock split",
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

    "NEE": [
        {
            "date": "2020-10-27",
            "type": "split",
            "ratio": "4:1",
            "comment": "4-for-1 stock split; ex-distribution / split-adjusted date",
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

    "NVO": [
        {
            "date": "2023-09-20",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 ADR split",
        }
    ],

    "ODFL": [
        {
            "date": "2020-03-25",
            "type": "split",
            "ratio": "3:2",
            "comment": "3-for-2 stock split; split-adjusted trading date",
        },
        {
            "date": "2024-03-28",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 stock split; split-adjusted trading date",
        },
    ],

    "SHOP": [
        {
            "date": "2022-06-29",
            "type": "split",
            "ratio": "10:1",
            "comment": "10-for-1 stock split",
        }
    ],

    "SSO": [
        {
            "date": "2020-08-18",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 ETF share split",
        },
        {
            "date": "2022-01-13",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 ETF share split",
        },
        {
            "date": "2025-11-20",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 ETF share split",
        },
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

    "WMT": [
        {
            "date": "2024-02-26",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split",
        }
    ],
}

# Reverse splits: price scales up after event date
REVERSE_SPLITS: Dict[str, List[Dict[str, str]]] = {
    "BLUE": [
        {
            "date": "2024-12-13",
            "type": "reverse_split",
            "ratio": "1:20",
            "comment": "1-for-20 reverse split; split-adjusted trading began on Nasdaq",
        }
    ],

    "DD": [
        {
            "date": "2026-06-24",
            "type": "reverse_split",
            "ratio": "1:3",
            "comment": "Planned 1-for-3 reverse stock split; split-adjusted trading expected on NYSE",
        }
    ],

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
    ],

    "GREE": [
        {
            "date": "2023-05-16",
            "type": "reverse_split",
            "ratio": "1:10",
            "comment": "1-for-10 reverse split; split-adjusted trading began on Nasdaq",
        }
    ],

    "SPCE": [
        {
            "date": "2024-06-17",
            "type": "reverse_split",
            "ratio": "1:20",
            "comment": "1-for-20 reverse split; split-adjusted trading began on NYSE",
        }
    ],
}

# Ticker symbol changes: no direct price scaling by default
TICKER_CHANGES: Dict[str, List[Dict[str, str]]] = {
    "META": [
        {
            "date": "2022-06-09",
            "type": "ticker_change",
            "ratio": "1:1",
            "from_symbol": "FB",
            "to_symbol": "META",
            "comment": "Ticker changed from FB to META",
        }
    ],

    # Important: your symbol list still has SQ, but current Block ticker is XYZ.
    "SQ": [
        {
            "date": "2025-01-21",
            "type": "ticker_change",
            "ratio": "1:1",
            "from_symbol": "SQ",
            "to_symbol": "XYZ",
            "comment": "Block changed ticker from SQ to XYZ on NYSE",
        }
    ],

    # FISV changed to FI, then later changed back to FISV.
    "FISV": [
        {
            "date": "2023-06-07",
            "type": "ticker_change",
            "ratio": "1:1",
            "from_symbol": "FISV",
            "to_symbol": "FI",
            "comment": "Fiserv changed ticker from FISV to FI",
        },
        {
            "date": "2025-11-11",
            "type": "ticker_change",
            "ratio": "1:1",
            "from_symbol": "FI",
            "to_symbol": "FISV",
            "comment": "Fiserv changed ticker from FI back to FISV",
        },
    ],

    "RTX": [
        {
            "date": "2020-04-03",
            "type": "ticker_change",
            "ratio": "1:1",
            "from_symbol": "UTX",
            "to_symbol": "RTX",
            "comment": "United Technologies renamed Raytheon Technologies and began trading as RTX after Raytheon merger",
        }
    ],
}

# Reorganizations / spin-offs: usually do NOT apply a simple price multiplier.
# Use these to avoid/filter windows around discontinuities.
REORGANIZATIONS: Dict[str, List[Dict[str, str]]] = {
    "DD": [
        {
            "date": "2025-11-03",
            "type": "spin_off",
            "ratio": "1 Q:2 DD",
            "comment": "Qnity spin-off; DD holders received 1 Qnity share for every 2 DuPont shares. Distribution date was 2025-11-01; first regular trading day was 2025-11-03.",
        }
    ],

    "GE": [
        {
            "date": "2023-01-04",
            "type": "spin_off",
            "ratio": "1 GEHC:3 GE",
            "comment": "GE HealthCare spin-off; GE holders received 1 GEHC share for every 3 GE shares",
        },
        {
            "date": "2024-04-02",
            "type": "spin_off",
            "ratio": "1 GEV:4 GE",
            "comment": "GE Vernova spin-off; GE holders received 1 GEV share for every 4 GE shares",
        },
    ],

    "LAC": [
        {
            "date": "2023-10-04",
            "type": "spin_off",
            "ratio": "reorganization",
            "comment": "Lithium Americas separated into Lithium Americas (LAC) and Lithium Argentina (LAAC); both began regular-way trading",
        }
    ],

    "RTX": [
        {
            "date": "2020-04-03",
            "type": "spin_off",
            "ratio": "0.5 OTIS + 1 CARR:1 UTX",
            "comment": "UTC separated Otis and Carrier immediately before the Raytheon merger / RTX ticker change",
        }
    ],
}

# Mergers / delistings: no direct price scaling by default.
# These symbols should usually be removed from live universes after the event.
MERGERS: Dict[str, List[Dict[str, str]]] = {
    "BLUE": [
        {
            "date": "2025-06-02",
            "type": "merger",
            "ratio": "cash",
            "comment": "bluebird bio sale completed; common stock ceased trading and is no longer publicly listed",
        }
    ],

    "HES": [
        {
            "date": "2025-07-18",
            "type": "merger",
            "ratio": "1.0250 CVX:1 HES",
            "comment": "Hess acquired by Chevron; each HES share converted into 1.0250 CVX shares plus cash in lieu of fractional shares",
        }
    ],

    "RDFN": [
        {
            "date": "2025-07-01",
            "type": "merger",
            "ratio": "stock",
            "comment": "Redfin acquired by Rocket Companies; RDFN no longer independent",
        }
    ],

    "SGEN": [
        {
            "date": "2023-12-14",
            "type": "merger",
            "ratio": "cash",
            "comment": "Seagen acquired by Pfizer for $229 cash per share",
        }
    ],

    "SPLK": [
        {
            "date": "2024-03-18",
            "type": "merger",
            "ratio": "cash",
            "comment": "Splunk acquired by Cisco for $157 cash per share; SPLK ceased trading on Nasdaq",
        }
    ],
}

def _ratio_to_share_factor(ratio: str) -> float:
    """
    Convert ratio string like '10:1' or '1:20' to share-count factor.

    10:1 forward split -> 10.0
    1:20 reverse split -> 0.05
    """
    left, right = ratio.split(":", 1)
    numerator = float(left)
    denominator = float(right)

    if numerator == 0 or denominator == 0:
        raise ValueError(f"Invalid corporate action ratio: {ratio}")

    return numerator / denominator


def _ratio_to_price_factor(ratio: str) -> float:
    """
    Convert ratio string to price adjustment factor for prices BEFORE the event.

    This factor normalizes old raw prices to the post-event price scale.

    10:1 forward split:
        pre-split price 1000 -> 100
        factor = 0.1

    1:20 reverse split:
        pre-split price 1 -> 20
        factor = 20.0
    """
    return 1.0 / _ratio_to_share_factor(ratio)

def build_corporate_actions_by_symbol() -> Dict[str, List[Dict[str, str]]]:
    """Return a merged symbol->events mapping across all action categories."""
    combined: Dict[str, List[Dict[str, str]]] = {}

    for source in (
        SPLITS,
        REVERSE_SPLITS,
        TICKER_CHANGES,
        REORGANIZATIONS,
        MERGERS,
    ):
        for symbol, events in source.items():
            combined.setdefault(symbol, []).extend(events)

    for symbol in combined:
        combined[symbol].sort(key=lambda event: event["date"])

    return combined

PRICE_ADJUSTMENT_ACTION_TYPES: Set[str] = {"split", "reverse_split"}

DISLOCATION_ACTION_TYPES: Set[str] = {
    "split",
    "reverse_split",
    "ticker_change",
    "spin_off",
    "merger",
}


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


def _parse_event_datetime(date_str: str) -> datetime:
    """Parse YYYY-MM-DD to UTC midnight datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _ratio_to_factor(ratio: str) -> float:
    """Compatibility wrapper for the price-adjustment factor calculation."""
    return _ratio_to_price_factor(ratio)


CORPORATE_ACTIONS: Dict[str, List[Dict[str, str]]] = build_corporate_actions_by_symbol()


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