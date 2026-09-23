"""
check_corporate_actions.py

Compare registered corporate actions with the actual behavior of the
historical price cache.

Output:
    1. All known/real corporate actions from corporate_actions.py
    2. Which splits/reverse splits actually need adjustment in the cache
    3. Suspicious unexplained price jumps that may indicate missing actions

Expected cache layouts supported:
    - pickle containing:
        {symbol: pandas.DataFrame}
    - CSV
    - Parquet

The DataFrame should contain:
    timestamp/date/datetime
and preferably:
    open, close

If "open" does not exist, the first available close of the day is used.
"""

from __future__ import annotations

import math
import pickle
from pathlib import Path

import pandas as pd

from corporate_actions import CORPORATE_ACTIONS


# ============================================================
# CONFIG
# ============================================================

CACHE_FILE = Path("YOUR_BIG_DATA_CACHE.pkl")

# How far observed split ratio may deviate from expected ratio.
# 0.15 means 15%.
SPLIT_TOLERANCE = 0.15

# Price changes larger than this are printed as suspicious
# if no registered corporate action exists nearby.
UNEXPLAINED_JUMP_THRESHOLD = 0.25

# Ignore suspicious jumps if a registered action is this many
# calendar days away.
ACTION_DATE_TOLERANCE_DAYS = 3


# ============================================================
# CACHE LOADING
# ============================================================

def load_cache(path: Path):
    suffix = path.suffix.lower()

    if suffix in {".pkl", ".pickle"}:
        with open(path, "rb") as f:
            return pickle.load(f)

    if suffix == ".parquet":
        return pd.read_parquet(path)

    if suffix == ".csv":
        return pd.read_csv(path)

    raise ValueError(f"Unsupported cache format: {suffix}")


# ============================================================
# CACHE -> PER SYMBOL DATAFRAME
# ============================================================

def extract_symbol_frames(cache) -> dict[str, pd.DataFrame]:
    """
    Convert the cache into:

        {
            "AAPL": dataframe,
            "NVDA": dataframe,
            ...
        }

    Supports the most common layouts.
    """

    # --------------------------------------------------------
    # Case 1:
    # cache = {
    #     "AAPL": dataframe,
    #     "NVDA": dataframe,
    # }
    # --------------------------------------------------------
    if isinstance(cache, dict):
        frames = {}

        for symbol, value in cache.items():
            if isinstance(value, pd.DataFrame):
                frames[str(symbol).upper()] = value.copy()

        if frames:
            return frames

    # --------------------------------------------------------
    # Case 2:
    # One large DataFrame with a symbol column
    # --------------------------------------------------------
    if isinstance(cache, pd.DataFrame):

        symbol_column = find_column(
            cache,
            ["symbol", "ticker", "asset"]
        )

        if symbol_column is None:
            raise ValueError(
                "Cache is a single DataFrame, but no "
                "'symbol'/'ticker' column was found."
            )

        return {
            str(symbol).upper(): group.copy()
            for symbol, group in cache.groupby(symbol_column)
        }

    raise ValueError(
        "Could not understand cache structure. "
        "Adjust extract_symbol_frames() for your cache format."
    )


# ============================================================
# COLUMN HELPERS
# ============================================================

def find_column(df: pd.DataFrame, candidates):
    lookup = {str(c).lower(): c for c in df.columns}

    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]

    return None


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    timestamp_col = find_column(
        df,
        [
            "timestamp",
            "datetime",
            "date",
            "time",
            "ts",
        ],
    )

    close_col = find_column(
        df,
        [
            "close",
            "c",
            "price",
        ],
    )

    open_col = find_column(
        df,
        [
            "open",
            "o",
        ],
    )

    if timestamp_col is None:
        # Sometimes timestamp is the index
        if isinstance(df.index, pd.DatetimeIndex):
            df["__timestamp"] = df.index
            timestamp_col = "__timestamp"
        else:
            raise ValueError("No timestamp/date column found.")

    if close_col is None:
        raise ValueError("No close/price column found.")

    df["timestamp"] = pd.to_datetime(
        df[timestamp_col],
        utc=True,
        errors="coerce",
    )

    df["close"] = pd.to_numeric(
        df[close_col],
        errors="coerce",
    )

    if open_col is not None:
        df["open"] = pd.to_numeric(
            df[open_col],
            errors="coerce",
        )
    else:
        # First close of the trading day will be used as open proxy.
        df["open"] = df["close"]

    df = df.dropna(
        subset=["timestamp", "close"]
    )

    df = df.sort_values("timestamp")

    return df[
        ["timestamp", "open", "close"]
    ]


# ============================================================
# DAILY PRICES
# ============================================================

def create_daily_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert minute/intraday data into daily data.

    Daily open  = first available price
    Daily close = last available price
    """

    df = normalize_dataframe(df)

    df["date"] = df["timestamp"].dt.date

    daily = (
        df.groupby("date")
        .agg(
            open=("open", "first"),
            close=("close", "last"),
        )
        .reset_index()
    )

    daily["date"] = pd.to_datetime(
        daily["date"],
        utc=True,
    )

    return daily.sort_values("date")


# ============================================================
# SPLIT RATIO
# ============================================================

def parse_ratio(ratio: str) -> float:
    """
    Examples:

        4:1   -> 4.0
        10:1  -> 10.0
        3:2   -> 1.5
        1:20  -> 0.05

    Returned value corresponds to:

        expected pre_split_price / post_split_price
    """

    left, right = ratio.split(":")

    return float(left) / float(right)


def relative_error(observed: float, expected: float) -> float:
    if expected == 0:
        return math.inf

    return abs(observed - expected) / abs(expected)


# ============================================================
# CHECK ONE ACTION
# ============================================================

def inspect_price_action(
    daily: pd.DataFrame,
    action_date: str,
    expected_ratio: float,
):
    event_date = pd.Timestamp(
        action_date,
        tz="UTC",
    )

    before = daily[
        daily["date"] < event_date
    ]

    after = daily[
        daily["date"] >= event_date
    ]

    if before.empty or after.empty:
        return {
            "status": "NO_DATA",
            "before_date": None,
            "after_date": None,
            "before_price": None,
            "after_price": None,
            "observed_ratio": None,
        }

    previous_day = before.iloc[-1]
    next_day = after.iloc[0]

    before_price = float(previous_day["close"])
    after_price = float(next_day["open"])

    if after_price <= 0:
        return {
            "status": "INVALID_PRICE",
        }

    observed_ratio = before_price / after_price

    split_error = relative_error(
        observed_ratio,
        expected_ratio,
    )

    adjusted_error = relative_error(
        observed_ratio,
        1.0,
    )

    # --------------------------------------------------------
    # Raw/unadjusted price series:
    #
    # Example:
    # AAPL 4:1
    #
    # before = $500
    # after  = $125
    #
    # observed_ratio ~= 4
    # --------------------------------------------------------

    if (
        split_error <= SPLIT_TOLERANCE
        and split_error < adjusted_error
    ):
        status = "NEEDS_ADJUSTMENT"

    # --------------------------------------------------------
    # Adjusted series:
    #
    # before = $125
    # after  = $125
    #
    # observed_ratio ~= 1
    # --------------------------------------------------------

    elif (
        adjusted_error <= SPLIT_TOLERANCE
        and adjusted_error < split_error
    ):
        status = "ALREADY_ADJUSTED"

    else:
        status = "UNCERTAIN"

    return {
        "status": status,
        "before_date": previous_day["date"],
        "after_date": next_day["date"],
        "before_price": before_price,
        "after_price": after_price,
        "observed_ratio": observed_ratio,
        "split_error": split_error,
        "adjusted_error": adjusted_error,
    }


# ============================================================
# CORPORATE ACTION CHECK
# ============================================================

def check_registered_actions(symbol_frames):

    results = []

    for symbol, actions in CORPORATE_ACTIONS.items():

        if symbol not in symbol_frames:
            for action in actions:
                results.append({
                    "symbol": symbol,
                    "date": action["date"],
                    "type": action["type"],
                    "ratio": action.get("ratio"),
                    "status": "SYMBOL_NOT_IN_CACHE",
                })

            continue

        try:
            daily = create_daily_prices(
                symbol_frames[symbol]
            )

        except Exception as exc:
            print(
                f"Could not process {symbol}: {exc}"
            )
            continue

        for action in actions:

            action_type = action["type"]

            # Ticker changes, mergers, spinoffs cannot be
            # identified simply from the price ratio.
            if action_type not in {
                "split",
                "reverse_split",
            }:

                results.append({
                    "symbol": symbol,
                    "date": action["date"],
                    "type": action_type,
                    "ratio": action.get("ratio"),
                    "status": "NON_PRICE_ACTION",
                })

                continue

            expected_ratio = parse_ratio(
                action["ratio"]
            )

            observation = inspect_price_action(
                daily,
                action["date"],
                expected_ratio,
            )

            results.append({
                "symbol": symbol,
                "date": action["date"],
                "type": action_type,
                "ratio": action["ratio"],
                "expected_ratio": expected_ratio,
                **observation,
            })

    return pd.DataFrame(results)


# ============================================================
# FIND UNEXPLAINED JUMPS
# ============================================================

def known_action_dates(symbol):
    dates = []

    for action in CORPORATE_ACTIONS.get(symbol, []):
        dates.append(
            pd.Timestamp(
                action["date"],
                tz="UTC",
            )
        )

    return dates


def close_to_known_action(symbol, date):

    for action_date in known_action_dates(symbol):

        difference = abs(
            (date - action_date).days
        )

        if difference <= ACTION_DATE_TOLERANCE_DAYS:
            return True

    return False


def find_unexplained_jumps(symbol_frames):

    suspicious = []

    for symbol, raw_df in symbol_frames.items():

        try:
            daily = create_daily_prices(raw_df)
        except Exception:
            continue

        daily = daily.copy()

        daily["previous_close"] = (
            daily["close"].shift(1)
        )

        daily["overnight_change"] = (
            daily["open"]
            / daily["previous_close"]
            - 1.0
        )

        jumps = daily[
            daily["overnight_change"].abs()
            >= UNEXPLAINED_JUMP_THRESHOLD
        ]

        for _, row in jumps.iterrows():

            date = row["date"]

            if close_to_known_action(
                symbol,
                date,
            ):
                continue

            suspicious.append({
                "symbol": symbol,
                "date": date.date(),
                "previous_close": row[
                    "previous_close"
                ],
                "next_open": row["open"],
                "change_pct": (
                    row["overnight_change"] * 100
                ),
            })

    return pd.DataFrame(suspicious)


# ============================================================
# OUTPUT
# ============================================================

def print_registered_actions():

    print("\n")
    print("=" * 90)
    print("REAL / REGISTERED CORPORATE ACTIONS")
    print("=" * 90)

    for symbol in sorted(CORPORATE_ACTIONS):

        for action in CORPORATE_ACTIONS[symbol]:

            print(
                f"{symbol:6} "
                f"{action['date']}  "
                f"{action['type']:15} "
                f"{action.get('ratio', '')}"
            )


def print_adjustment_results(results):

    print("\n")
    print("=" * 90)
    print("CORPORATE ACTIONS REQUIRED BY CACHE")
    print("=" * 90)

    needed = results[
        results["status"]
        == "NEEDS_ADJUSTMENT"
    ]

    if needed.empty:
        print("None.")
    else:
        for _, row in needed.iterrows():

            print(
                f"{row['symbol']:6} "
                f"{row['date']}  "
                f"{row['type']:14} "
                f"{row['ratio']:8} "
                f"observed={row['observed_ratio']:.3f}"
            )

    print("\n")
    print("=" * 90)
    print("ALREADY ADJUSTED IN CACHE")
    print("=" * 90)

    adjusted = results[
        results["status"]
        == "ALREADY_ADJUSTED"
    ]

    for _, row in adjusted.iterrows():

        print(
            f"{row['symbol']:6} "
            f"{row['date']}  "
            f"{row['type']:14} "
            f"{row['ratio']:8} "
            f"observed={row['observed_ratio']:.3f}"
        )

    print("\n")
    print("=" * 90)
    print("UNCERTAIN / MANUAL CHECK")
    print("=" * 90)

    uncertain = results[
        ~results["status"].isin(
            [
                "NEEDS_ADJUSTMENT",
                "ALREADY_ADJUSTED",
                "NON_PRICE_ACTION",
            ]
        )
    ]

    if uncertain.empty:
        print("None.")
    else:
        print(
            uncertain.to_string(
                index=False
            )
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        f"Loading cache: {CACHE_FILE}"
    )

    cache = load_cache(CACHE_FILE)

    symbol_frames = extract_symbol_frames(
        cache
    )

    print(
        f"Found {len(symbol_frames)} symbols."
    )

    # --------------------------------------------------------
    # List 1:
    # Actual registered corporate actions
    # --------------------------------------------------------

    print_registered_actions()

    # --------------------------------------------------------
    # List 2:
    # Actions that the cache actually requires
    # --------------------------------------------------------

    results = check_registered_actions(
        symbol_frames
    )

    print_adjustment_results(results)

    # Save complete result
    results.to_csv(
        "corporate_action_cache_check.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Bonus:
    # Find big jumps that have NO registered action
    # --------------------------------------------------------

    suspicious = find_unexplained_jumps(
        symbol_frames
    )

    print("\n")
    print("=" * 90)
    print("UNEXPLAINED LARGE PRICE JUMPS")
    print("=" * 90)

    if suspicious.empty:
        print("None.")
    else:
        suspicious = suspicious.sort_values(
            "change_pct",
            key=lambda x: x.abs(),
            ascending=False,
        )

        print(
            suspicious.to_string(
                index=False
            )
        )

        suspicious.to_csv(
            "unexplained_price_jumps.csv",
            index=False,
        )


if __name__ == "__main__":
    main()