"""Audit cached price discontinuities against the corporate-action registry."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.data_fixes.list_of_corp_act import (
    CORPORATE_ACTIONS,
    PRICE_ADJUSTMENT_ACTION_TYPES,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data_cache"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
REPORT_PATH = OUTPUT_DIR / "corporate_action_audit.md"
JUMP_THRESHOLD_PERCENT = 10.0
ACTION_TOLERANCE_DAYS = 3
DISABLED_CACHE_ADJUSTED_EVENTS = [
    {
        "symbol": "NOW",
        "date": "2025-12-18",
        "type": "split",
        "ratio": "5:1",
        "comment": "Cache already contains split-adjusted prices; registry entry intentionally commented out.",
    },
    {
        "symbol": "SSO",
        "date": "2022-01-13",
        "type": "split",
        "ratio": "2:1",
        "comment": "Cache already contains split-adjusted prices; registry entry intentionally commented out.",
    },
    {
        "symbol": "SSO",
        "date": "2025-11-20",
        "type": "split",
        "ratio": "2:1",
        "comment": "Cache already contains split-adjusted prices; registry entry intentionally commented out.",
    },
    {
        "symbol": "BLUE",
        "date": "2024-12-13",
        "type": "reverse_split",
        "ratio": "1:20",
        "comment": "Cache already contains split-adjusted prices; registry entry intentionally commented out.",
    },
    {
        "symbol": "LCID",
        "date": "2025-08-29",
        "type": "reverse_split",
        "ratio": "1:10",
        "comment": "Cache already contains split-adjusted prices; registry entry intentionally commented out.",
    },
]


def load_daily_prices(path: Path) -> pd.DataFrame:
    data = pd.read_parquet(path, columns=["timestamp", "open", "close"])
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    data["open"] = pd.to_numeric(data["open"], errors="coerce")
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    data = data.dropna(subset=["timestamp", "open", "close"])
    data["date"] = data["timestamp"].dt.floor("D")
    return (
        data.groupby("date", as_index=False)
        .agg(
            open=("open", "first"),
            close=("close", "last"),
            first_bar=("timestamp", "first"),
            last_bar=("timestamp", "last"),
        )
        .sort_values("date")
    )


def parse_ratio(value: str) -> float:
    left, right = value.split(":", 1)
    return float(left) / float(right)


def action_dates(symbol: str) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(event["date"], tz="UTC")
        for event in CORPORATE_ACTIONS.get(symbol, [])
    ] + [
        pd.Timestamp(event["date"], tz="UTC")
        for event in DISABLED_CACHE_ADJUSTED_EVENTS
        if event["symbol"] == symbol
    ]


def has_nearby_action(symbol: str, date: pd.Timestamp) -> bool:
    return any(
        abs((date - event_date).days) <= ACTION_TOLERANCE_DAYS
        for event_date in action_dates(symbol)
    )


def inspect_split(daily: pd.DataFrame, event: dict[str, str]) -> dict[str, object]:
    event_date = pd.Timestamp(event["date"], tz="UTC")
    before = daily[daily["date"] < event_date]
    after = daily[daily["date"] >= event_date]
    if before.empty or after.empty:
        return {"status": "NO_DATA", "observed_ratio": None}

    before_price = float(before.iloc[-1]["close"])
    after_price = float(after.iloc[0]["open"])
    if before_price <= 0 or after_price <= 0:
        return {"status": "INVALID_PRICE", "observed_ratio": None}

    observed_ratio = before_price / after_price
    expected_ratio = parse_ratio(event["ratio"])
    split_error = abs(observed_ratio - expected_ratio) / abs(expected_ratio)
    adjusted_error = abs(observed_ratio - 1.0)
    if split_error <= 0.15 and split_error < adjusted_error:
        status = "ACCOUNTED_RAW_ADJUSTMENT"
    elif adjusted_error <= 0.15 and adjusted_error < split_error:
        status = "ALREADY_ADJUSTED_CACHE"
    else:
        status = "UNCERTAIN"
    return {
        "status": status,
        "observed_ratio": observed_ratio,
        "expected_ratio": expected_ratio,
        "before_date": before.iloc[-1]["date"].date(),
        "after_date": after.iloc[0]["date"].date(),
    }


def markdown_table(rows: list[dict[str, object]], columns: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return lines


def format_duration(value: pd.Timedelta) -> str:
    total_minutes = int(value.total_seconds() // 60)
    days, minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"


def main() -> None:
    frames: dict[str, pd.DataFrame] = {}
    read_errors: list[tuple[str, str]] = []
    paths = sorted(CACHE_DIR.glob("*_1m.parquet"))
    for path in paths:
        symbol = path.name.removesuffix("_1m.parquet").upper()
        try:
            frames[symbol] = load_daily_prices(path)
        except Exception as exc:
            read_errors.append((symbol, f"{type(exc).__name__}: {exc}"))

    split_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    for symbol, events in CORPORATE_ACTIONS.items():
        daily = frames.get(symbol)
        for event in events:
            base = {
                "Symbol": symbol,
                "Date": event["date"],
                "Type": event["type"],
                "Ratio": event.get("ratio", ""),
                "Comment": event.get("comment", ""),
            }
            if event["type"] in PRICE_ADJUSTMENT_ACTION_TYPES:
                if daily is None:
                    result = {"status": "SYMBOL_NOT_IN_CACHE"}
                else:
                    result = inspect_split(daily, event)
                split_rows.append(
                    {
                        **base,
                        "Status": result.pop("status"),
                        **result,
                    }
                )
            else:
                event_rows.append({**base, "Status": "REGISTERED_NON_PRICE_EVENT"})

    for event in DISABLED_CACHE_ADJUSTED_EVENTS:
        split_rows.append(
            {
                "Symbol": event["symbol"],
                "Date": event["date"],
                "Type": event["type"],
                "Ratio": event["ratio"],
                "Status": "ALREADY_ADJUSTED_CACHE",
                "observed_ratio": "",
                "Comment": event["comment"],
            }
        )

    jump_rows: list[dict[str, object]] = []
    for symbol, daily in frames.items():
        daily = daily.copy()
        daily["previous_close"] = daily["close"].shift(1)
        daily["previous_bar"] = daily["last_bar"].shift(1)
        daily["change_percent"] = (daily["open"] / daily["previous_close"] - 1.0) * 100
        for _, row in daily[daily["change_percent"].abs() >= JUMP_THRESHOLD_PERCENT].dropna(
            subset=["previous_close"]
        ).iterrows():
            date = row["date"]
            if has_nearby_action(symbol, date):
                status = "ACCOUNTED_NEARBY_REGISTERED_EVENT"
            else:
                status = "UNACCOUNTED"
            jump_rows.append(
                {
                    "Symbol": symbol,
                    "Date": date.date(),
                    "Change": f"{row['change_percent']:+.2f}%",
                    "Implied ratio": f"{row['previous_close'] / row['open']:.4f}",
                    "Previous bar": row["previous_bar"].isoformat(),
                    "Gap since previous bar": format_duration(
                        row["first_bar"] - row["previous_bar"]
                    ),
                    "Status": status,
                }
            )

    jump_rows.sort(key=lambda row: abs(float(str(row["Change"]).rstrip("%"))), reverse=True)
    unaccounted = [row for row in jump_rows if row["Status"] == "UNACCOUNTED"]
    accounted = [row for row in jump_rows if row["Status"] != "UNACCOUNTED"]
    unaccounted_over_25 = [
        row
        for row in unaccounted
        if abs(float(str(row["Change"]).rstrip("%"))) > 25
    ]
    unaccounted_10_to_25 = [
        row
        for row in unaccounted
        if 10 <= abs(float(str(row["Change"]).rstrip("%"))) <= 25
    ]
    split_rows.sort(key=lambda row: (str(row["Status"]), str(row["Symbol"]), str(row["Date"])))
    event_rows.sort(key=lambda row: (str(row["Symbol"]), str(row["Date"])))

    lines = [
        "# Corporate-Action Cache Audit",
        "",
        "Generated from the current `scripts/data_fixes/list_of_corp_act.py` and all readable `data_cache/*_1m.parquet` files.",
        "",
        "## Scope",
        "",
        f"- Parquet files found: **{len(paths)}**",
        f"- Symbols read successfully: **{len(frames)}**",
        f"- Overnight jump threshold: **{JUMP_THRESHOLD_PERCENT:.0f}%** absolute change",
        f"- Registered-event matching window: **+/-{ACTION_TOLERANCE_DAYS} calendar days**",
        f"- Direct price-adjustment events reviewed: **{len(split_rows)}**",
        f"- Registered non-price events: **{len(event_rows)}**",
        "",
        "A split is `ACCOUNTED_RAW_ADJUSTMENT` when the observed close-to-open ratio matches its registered ratio within 15%. `ALREADY_ADJUSTED_CACHE` means the event is intentionally disabled in the active registry because the cache already contains the adjustment. Unaccounted jumps are candidates for further corporate-action or data-quality review; they are not automatically confirmed actions.",
        "",
        "## Registered Splits",
        "",
    ]
    lines.extend(
        markdown_table(
            split_rows,
            ["Symbol", "Date", "Type", "Ratio", "Status", "observed_ratio", "Comment"],
        )
    )
    lines += ["", "## Registered Non-Price Events", ""]
    lines.extend(markdown_table(event_rows, ["Symbol", "Date", "Type", "Ratio", "Status", "Comment"]))
    lines += ["", "## Jumps Explained by a Nearby Registered Event", ""]
    jump_columns = [
        "Symbol",
        "Date",
        "Change",
        "Implied ratio",
        "Previous bar",
        "Gap since previous bar",
        "Status",
    ]
    lines.extend(markdown_table(accounted, jump_columns))
    lines += [
        "",
        "## Unaccounted Jumps Above 25%",
        "",
        "Jumps with an absolute overnight change greater than 25% and no registered event within the matching window.",
        "",
    ]
    lines.extend(
        markdown_table(
            unaccounted_over_25,
            jump_columns,
        )
    )
    lines += [
        "",
        "## Unaccounted Jumps From 10% To 25%",
        "",
        "Jumps with an absolute overnight change from 10% through 25% and no registered event within the matching window.",
        "",
    ]
    lines.extend(
        markdown_table(
            unaccounted_10_to_25,
            jump_columns,
        )
    )
    if read_errors:
        lines += ["", "## Files Not Read", ""]
        lines.extend(markdown_table([{"Symbol": symbol, "Error": error} for symbol, error in read_errors], ["Symbol", "Error"]))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH} ({len(split_rows)} splits, {len(unaccounted)} unaccounted jumps)")


if __name__ == "__main__":
    main()