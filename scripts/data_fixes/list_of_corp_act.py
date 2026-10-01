"""Updated corporate action registry used by backtesting and validation.

This module keeps the maintained action tables in ``scripts`` while exposing the
same helper API that the rest of the codebase imports from ``corporate_actions``.

Important distinction:

- SPLITS / REVERSE_SPLITS:
    Events for which a direct price multiplier can be applied.

- TICKER_CHANGES:
    Symbol continuity events. These do not imply a price multiplier.

- REORGANIZATIONS:
    Spin-offs, mergers, distributions, and other events that can create a
    legitimate price discontinuity but should NOT be handled as a simple split.

- MERGERS:
    Events after which the old security ceases to represent an independent
    tradable company.

- LISTING_EVENTS:
    IPO / predecessor / first-trading events. These explain discontinuities
    at the beginning of a symbol's history but should NOT be treated as
    corporate-action price adjustments.

Disabled events are intentionally left commented when the cache has already
incorporated the adjustment.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Forward splits
# Price scales DOWN after the split-adjusted trading date.
# ---------------------------------------------------------------------------

SPLITS: Dict[str, List[Dict[str, str]]] = {
    "AAPL": [
        {
            "date": "2020-08-31",
            "type": "split",
            "ratio": "4:1",
            "comment": "4-for-1 stock split",
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

    "BALL": [
        {
            "date": "2017-05-17",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 stock split; split-adjusted trading began",
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

    "CSX": [
        {
            "date": "2021-06-29",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split",
        }
    ],

    "CVNA": [
        {
            "date": "2026-05-08",
            "type": "split",
            "ratio": "5:1",
            "comment": "5-for-1 stock split; split-adjusted trading began",
        }
    ],

    "FAST": [
        {
            "date": "2019-05-23",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 stock split; split-adjusted trading began",
        },
        {
            "date": "2025-05-22",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 stock split; ex/split-adjusted trading began",
        },
    ],

    "FISV": [
        {
            "date": "2018-03-20",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 stock split; split-adjusted trading began",
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

    "ICE": [
        {
            "date": "2016-11-04",
            "type": "split",
            "ratio": "5:1",
            "comment": "5-for-1 stock split; split-adjusted trading began",
        }
    ],

    "ISRG": [
        {
            "date": "2017-10-06",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split; split-adjusted trading began",
        },
        {
            "date": "2021-10-05",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split",
        },
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

    "MNST": [
        {
            "date": "2023-03-28",
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

    "NFLX": [
        {
            "date": "2025-11-17",
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
            "date": "2021-07-20",
            "type": "split",
            "ratio": "4:1",
            "comment": "4-for-1 stock split",
        },
        {
            "date": "2024-06-10",
            "type": "split",
            "ratio": "10:1",
            "comment": "10-for-1 stock split",
        },
    ],

    "NVO": [
        {
            "date": "2023-09-20",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 ADR split",
        }
    ],

    # Disabled: the cache is already adjusted for this event.
    # "NOW": [
    #     {
    #         "date": "2025-12-18",
    #         "type": "split",
    #         "ratio": "5:1",
    #         "comment": "5-for-1 stock split",
    #     }
    # ],

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

    "SHW": [
        {
            "date": "2021-04-01",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split; split-adjusted trading began",
        }
    ],

    "SRE": [
        {
            "date": "2023-08-22",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 stock split",
        }
    ],

    "SSO": [
        {
            "date": "2020-08-18",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 ETF share split",
        },

        # Disabled: the cache is already adjusted for this event.
        # {
        #     "date": "2022-01-13",
        #     "type": "split",
        #     "ratio": "2:1",
        #     "comment": "2-for-1 ETF share split",
        # },
        # {
        #     "date": "2025-11-20",
        #     "type": "split",
        #     "ratio": "2:1",
        #     "comment": "2-for-1 ETF share split",
        # },
    ],

    "TJX": [
        {
            "date": "2018-11-07",
            "type": "split",
            "ratio": "2:1",
            "comment": "2-for-1 stock split; split-adjusted trading began",
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

    "WMT": [
        {
            "date": "2024-02-26",
            "type": "split",
            "ratio": "3:1",
            "comment": "3-for-1 stock split",
        }
    ],
}


# ---------------------------------------------------------------------------
# Reverse splits
# Price scales UP after the split-adjusted trading date.
# ---------------------------------------------------------------------------

REVERSE_SPLITS: Dict[str, List[Dict[str, str]]] = {
    # Disabled: the cache is already adjusted for this event.
    # "BLUE": [
    #     {
    #         "date": "2024-12-13",
    #         "type": "reverse_split",
    #         "ratio": "1:20",
    #         "comment": "1-for-20 reverse split; split-adjusted trading began on Nasdaq",
    #     }
    # ],

    "ARCT": [
        {
            "date": "2017-11-16",
            "type": "reverse_split",
            "ratio": "1:7",
            "comment": (
                "1-for-7 reverse split; Alcobra/ADHD business combination "
                "became effective with ARCT trading"
            ),
        }
    ],

    "DD": [
        {
            "date": "2019-06-03",
            "type": "reverse_split",
            "ratio": "1:3",
            "comment": (
                "1-for-3 reverse split associated with the DowDuPont "
                "reorganization; split-adjusted DD trading began"
            ),
        },
        {
            "date": "2026-06-24",
            "type": "reverse_split",
            "ratio": "1:3",
            "comment": "1-for-3 reverse stock split; split-adjusted trading began",
        },
    ],

    "DNA": [
        {
            "date": "2024-08-20",
            "type": "reverse_split",
            "ratio": "1:40",
            "comment": "1-for-40 reverse split; split-adjusted trading began on NYSE",
        }
    ],

    "FCEL": [
        {
            "date": "2019-05-09",
            "type": "reverse_split",
            "ratio": "1:12",
            "comment": "1-for-12 reverse stock split; post-split trading began",
        },
        {
            "date": "2024-11-11",
            "type": "reverse_split",
            "ratio": "1:30",
            "comment": "1-for-30 reverse stock split",
        },
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

    "HLT": [
        {
            "date": "2017-01-04",
            "type": "reverse_split",
            "ratio": "1:3",
            "comment": (
                "1-for-3 reverse stock split; split-adjusted trading began "
                "after Hilton spin-offs"
            ),
        }
    ],

    "MARA": [
        {
            "date": "2017-10-30",
            "type": "reverse_split",
            "ratio": "1:4",
            "comment": "1-for-4 reverse stock split; post-split trading began",
        },
        {
            "date": "2019-04-08",
            "type": "reverse_split",
            "ratio": "1:4",
            "comment": "1-for-4 reverse stock split; post-split trading began",
        },
    ],

    "RIOT": [
        {
            "date": "2016-03-31",
            "type": "reverse_split",
            "ratio": "1:8",
            "comment": (
                "1-for-8 reverse split by predecessor Venaxis; "
                "effective March 31, 2016"
            ),
        }
    ],

    # Disabled: the cache is already adjusted for this event.
    # "LCID": [
    #     {
    #         "date": "2025-08-29",
    #         "type": "reverse_split",
    #         "ratio": "1:10",
    #         "comment": (
    #             "1-for-10 reverse split; split-adjusted trading began "
    #             "on the next trading day"
    #         ),
    #     }
    # ],

    "SPCE": [
        {
            "date": "2024-06-17",
            "type": "reverse_split",
            "ratio": "1:20",
            "comment": "1-for-20 reverse split; split-adjusted trading began on NYSE",
        }
    ],
}


# ---------------------------------------------------------------------------
# Ticker symbol changes
# No direct price scaling by default.
# ---------------------------------------------------------------------------

TICKER_CHANGES: Dict[str, List[Dict[str, str]]] = {
    "ADHD": [
        {
            "date": "2017-11-16",
            "type": "ticker_change",
            "ratio": "1:1",
            "from_symbol": "ADHD",
            "to_symbol": "ARCT",
            "comment": (
                "Alcobra changed name and ticker to Arcturus Therapeutics "
                "following the business combination"
            ),
        }
    ],

    "DD": [
        {
            "date": "2019-06-03",
            "type": "ticker_change",
            "ratio": "1:1",
            "from_symbol": "DWDP",
            "to_symbol": "DD",
            "comment": (
                "DowDuPont changed name to DuPont de Nemours and began "
                "regular-way trading under DD after the Corteva separation"
            ),
        }
    ],

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
            "comment": (
                "United Technologies renamed Raytheon Technologies and "
                "began trading as RTX after Raytheon merger"
            ),
        }
    ],
}


# ---------------------------------------------------------------------------
# Reorganizations / spin-offs / distributions
#
# These can cause large legitimate price discontinuities but should NOT
# receive a simple price multiplier.
# ---------------------------------------------------------------------------

REORGANIZATIONS: Dict[str, List[Dict[str, str]]] = {
    "DD": [
        {
            "date": "2019-04-02",
            "type": "spin_off",
            "ratio": "1 DOW:3 DWDP",
            "comment": (
                "Dow separation from DowDuPont; shareholders received "
                "1 Dow share for every 3 DowDuPont shares. "
                "Dow began regular-way trading on April 2, 2019."
            ),
        },
        {
            "date": "2019-06-03",
            "type": "spin_off",
            "ratio": "1 CTVA:3 DWDP",
            "comment": (
                "Corteva separation from DowDuPont; shareholders received "
                "1 Corteva share for every 3 DowDuPont shares. "
                "DuPont began regular-way trading under DD."
            ),
        },
        {
            "date": "2025-11-03",
            "type": "spin_off",
            "ratio": "1 Q:2 DD",
            "comment": (
                "Qnity spin-off; DD holders received 1 Qnity share "
                "for every 2 DuPont shares. Distribution date was "
                "2025-11-01; first regular trading day was 2025-11-03."
            ),
        },
    ],

    "GE": [
        {
            "date": "2023-01-04",
            "type": "spin_off",
            "ratio": "1 GEHC:3 GE",
            "comment": (
                "GE HealthCare spin-off; GE holders received "
                "1 GEHC share for every 3 GE shares"
            ),
        },
        {
            "date": "2024-04-02",
            "type": "spin_off",
            "ratio": "1 GEV:4 GE",
            "comment": (
                "GE Vernova spin-off; GE holders received "
                "1 GEV share for every 4 GE shares"
            ),
        },
    ],

    "HLT": [
        {
            "date": "2017-01-04",
            "type": "spin_off",
            "ratio": "2 PK + 1 HGV:10 HLT",
            "comment": (
                "Hilton completed Park Hotels & Resorts and Hilton Grand "
                "Vacations spin-offs; regular-way trading began January 4, "
                "2017 alongside the HLT 1-for-3 reverse split."
            ),
        }
    ],

    "CTRA": [
        {
            "date": "2021-10-04",
            "type": "merger",
            "ratio": "stock",
            "comment": (
                "Cabot Oil & Gas and Cimarex merger; "
                "Coterra Energy began regular-way trading"
            ),
        }
    ],

    "LAC": [
        {
            "date": "2023-10-04",
            "type": "spin_off",
            "ratio": "reorganization",
            "comment": (
                "Lithium Americas separated into Lithium Americas (LAC) "
                "and Lithium Argentina (LAAC); both began regular-way trading"
            ),
        }
    ],

    "MTCH": [
        {
            "date": "2020-07-01",
            "type": "spin_off",
            "ratio": "reorganization",
            "comment": (
                "IAC separated Match Group in a complex "
                "merger/reorganization; no simple price multiplier applied"
            ),
        }
    ],

    "RTX": [
        {
            "date": "2020-04-03",
            "type": "spin_off",
            "ratio": "0.5 OTIS + 1 CARR:1 UTX",
            "comment": (
                "UTC separated Otis and Carrier immediately before "
                "the Raytheon merger / RTX ticker change"
            ),
        }
    ],
}


# ---------------------------------------------------------------------------
# Mergers / delistings
#
# No direct price scaling by default.
# These symbols should usually be removed from live universes after the event.
# ---------------------------------------------------------------------------

MERGERS: Dict[str, List[Dict[str, str]]] = {
    "ARCT": [
        {
            "date": "2017-11-16",
            "type": "merger",
            "ratio": "ADHD -> ARCT",
            "comment": (
                "Alcobra / Arcturus business combination; new ARCT security "
                "and ticker became effective for Nasdaq trading"
            ),
        }
    ],

    "BLUE": [
        {
            "date": "2025-06-02",
            "type": "merger",
            "ratio": "cash",
            "comment": (
                "bluebird bio sale completed; common stock ceased trading "
                "and is no longer publicly listed"
            ),
        }
    ],

    "HES": [
        {
            "date": "2025-07-18",
            "type": "merger",
            "ratio": "1.0250 CVX:1 HES",
            "comment": (
                "Hess acquired by Chevron; each HES share converted into "
                "1.0250 CVX shares plus cash in lieu of fractional shares"
            ),
        }
    ],

    "RDFN": [
        {
            "date": "2025-07-01",
            "type": "merger",
            "ratio": "stock",
            "comment": (
                "Redfin acquired by Rocket Companies; "
                "RDFN no longer independent"
            ),
        }
    ],

    "SGEN": [
        {
            "date": "2023-12-14",
            "type": "merger",
            "ratio": "cash",
            "comment": (
                "Seagen acquired by Pfizer for $229 cash per share"
            ),
        }
    ],

    "SPLK": [
        {
            "date": "2024-03-18",
            "type": "merger",
            "ratio": "cash",
            "comment": (
                "Splunk acquired by Cisco for $157 cash per share; "
                "SPLK ceased trading on Nasdaq"
            ),
        }
    ],
}


# ---------------------------------------------------------------------------
# Listing / IPO / predecessor events
#
# These explain discontinuities but must NOT be treated as splits.
# ---------------------------------------------------------------------------

LISTING_EVENTS: Dict[str, List[Dict[str, str]]] = {
    "NIO": [
        {
            "date": "2018-09-12",
            "type": "ipo",
            "ratio": "1:1",
            "comment": (
                "NIO began NYSE trading following its initial public offering; "
                "historical discontinuity is a listing boundary, not a split"
            ),
        }
    ],

    "SNOW": [
        {
            "date": "2020-09-16",
            "type": "ipo",
            "ratio": "1:1",
            "comment": (
                "Snowflake began NYSE trading following its IPO; "
                "historical discontinuity is a listing boundary, not a split"
            ),
        }
    ],
}


# ---------------------------------------------------------------------------
# Combined lookup used by the helper module.
# ---------------------------------------------------------------------------

CORPORATE_ACTIONS: Dict[str, List[Dict[str, str]]] = {}

for action_table in (
    SPLITS,
    REVERSE_SPLITS,
    TICKER_CHANGES,
    REORGANIZATIONS,
    MERGERS,
    LISTING_EVENTS,
):
    for symbol, events in action_table.items():
        CORPORATE_ACTIONS.setdefault(symbol, []).extend(events)


# Events for which a direct price multiplier is appropriate.
PRICE_ADJUSTMENT_ACTION_TYPES = {
    "split",
    "reverse_split",
}


# Events which can legitimately explain a price discontinuity.
DISLOCATION_ACTION_TYPES = {
    "split",
    "reverse_split",
    "ticker_change",
    "spin_off",
    "merger",
    "ipo",
}


# Events which explain why the historical price series may not be continuous,
# but which should NOT be passed to the price-adjustment multiplier.
NON_PRICE_ADJUSTMENT_ACTION_TYPES = {
    "ticker_change",
    "spin_off",
    "merger",
    "ipo",
}