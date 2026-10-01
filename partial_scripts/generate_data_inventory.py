"""Generate a markdown inventory of cached market-data coverage."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data_cache"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
REPORT_PATH = OUTPUT_DIR / "data_cache_inventory1.md"
EXPECTED_MINUTE_BARS_PER_WEEKDAY = 390
def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def weekday_count(start: datetime, end: datetime) -> int:
    start_date = start.date()
    end_date = end.date()
    days = (end_date - start_date).days + 1
    return sum(
        (start_date + timedelta(days=offset)).weekday() < 5
        for offset in range(max(0, days))
    )


def status_for(rows: int, density: float) -> str:
    if rows < 100:
        return "NEAR-EMPTY / CHECK"
    if density < 0.10:
        return "VERY SPARSE"
    if density < 0.50:
        return "SPARSE"
    return "OK"


def density_for_timestamps(timestamps: pd.Series, start: datetime, end: datetime) -> tuple[int, int, float | None]:
    window_start = max(start, timestamps.min().to_pydatetime())
    window_end = min(end, timestamps.max().to_pydatetime())
    if window_start > window_end:
        return 0, 0, None

    window_rows = int(((timestamps >= window_start) & (timestamps <= window_end)).sum())
    expected = weekday_count(window_start, window_end) * EXPECTED_MINUTE_BARS_PER_WEEKDAY
    density = window_rows / expected if expected else None
    return window_rows, expected, density


def load_inventory() -> tuple[list[dict[str, object]], list[int]]:
    inventory = []
    metadata_rows = []
    for meta_path in sorted(CACHE_DIR.glob("*_1m.meta.json")):
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        start = parse_timestamp(metadata["start"])
        end = parse_timestamp(metadata["end"])
        rows = int(metadata.get("rows", 0))
        parquet_path = meta_path.with_suffix("").with_suffix(".parquet")
        try:
            timestamps = pd.read_parquet(parquet_path, columns=["timestamp"])["timestamp"]
            timestamps = pd.to_datetime(timestamps, utc=True)
        except Exception:
            timestamps = None
        metadata_rows.append((start, end))
        inventory.append(
            {
                "symbol": str(metadata["symbol"]),
                "binning": str(metadata.get("timeframe", "1m")),
                "start": start,
                "end": end,
                "rows": rows,
                "timestamps": timestamps,
            }
        )
    first_year = min(start.year for start, _ in metadata_rows)
    last_year = max(end.year for _, end in metadata_rows)
    years = list(range(first_year, last_year + 1))
    for item in inventory:
        year_data = {}
        for year in years:
            if item["timestamps"] is None:
                year_rows, year_expected, year_density = 0, 0, None
            else:
                year_start = datetime(year, 1, 1, tzinfo=timezone.utc)
                year_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)
                year_rows, year_expected, year_density = density_for_timestamps(
                    item["timestamps"], year_start, year_end
                )
            year_data[year] = {
                "rows": year_rows,
                "expected": year_expected,
                "density": year_density,
            }
        item["years"] = year_data
        item["status"] = (
            "UNREADABLE / CHECK"
            if item["timestamps"] is None
            else status_for(item["rows"], year_data[item["end"].year]["density"])
        )
        del item["timestamps"]
    return inventory, years


def format_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def generate_report(inventory: list[dict[str, object]], years: list[int]) -> str:
    near_empty = sum(item["status"] == "NEAR-EMPTY / CHECK" for item in inventory)
    very_sparse = sum(item["status"] == "VERY SPARSE" for item in inventory)
    sparse = sum(item["status"] == "SPARSE" for item in inventory)
    unreadable = sum(item["status"] == "UNREADABLE / CHECK" for item in inventory)
    earliest = min(item["start"] for item in inventory)
    latest = max(item["end"] for item in inventory)
    common_end = min(item["end"] for item in inventory)

    lines = [
        "# Cached Market Data Inventory",
        "",
        "Generated from `data_cache/*.meta.json`; parquet row counts are taken from the metadata sidecars.",
        "",
        "## Summary",
        "",
        f"- Cache files: **{len(inventory)}**",
        f"- Cache-wide earliest timestamp: **{format_timestamp(earliest)}**",
        f"- Latest timestamp in any file: **{format_timestamp(latest)}**",
        f"- Latest timestamp common to every metadata file: **{format_timestamp(common_end)}**",
        f"- Near-empty files with fewer than 100 rows: **{near_empty}**",
        f"- Sparse files between 10% and 50% of the estimated weekday 1-minute baseline: **{sparse}**",
        f"- Very sparse files below 10% of the estimated weekday 1-minute baseline: **{very_sparse}**",
        f"- Unreadable parquet files requiring repair: **{unreadable}**",
        "",
        "Each yearly density uses actual parquet timestamps and the US regular-session baseline of 390 one-minute bars per weekday (09:30-16:00 Eastern). The denominator covers only the part of that calendar year where the symbol has available data. Values above 100% indicate that extended-hours or additional off-session bars are present.",
        "",
        "## Interpretation",
        "",
        "- `OK`: substantial coverage relative to the estimated one-minute baseline.",
        "- `SPARSE` / `VERY SPARSE`: fewer rows than expected for the metadata date span; inspect before using in a broad run.",
        "- `NEAR-EMPTY / CHECK`: metadata claims a broad range but the file contains almost no bars; these should not be treated as usable history.",
        "- `UNREADABLE / CHECK`: parquet timestamps could not be decoded, so yearly density is shown as `n/a`.",
        "",
        "## Per-Symbol Coverage",
        "",
        "| Symbol | Binning | Available from (UTC) | Available to (UTC) | Rows | "
        + " | ".join(f"{year} density" for year in years)
        + " | Status |",
        "|---|---|---|---|---:|"
        + "---:|" * len(years)
        + "---|",
    ]
    for item in inventory:
        yearly_densities = " | ".join(
            "n/a"
            if item["years"][year]["density"] is None
            else f"{item['years'][year]['density']:.1%}"
            for year in years
        )
        lines.append(
            "| {symbol} | {binning} | {start} | {end} | {rows:,} | {yearly_densities} | {status} |".format(
                symbol=item["symbol"],
                binning=item["binning"],
                start=format_timestamp(item["start"]),
                end=format_timestamp(item["end"]),
                rows=item["rows"],
                yearly_densities=yearly_densities,
                status=item["status"],
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    inventory, years = load_inventory()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(generate_report(inventory, years), encoding="utf-8")
    print(f"Wrote {REPORT_PATH} ({len(inventory)} symbols, years {years[0]}-{years[-1]})")


if __name__ == "__main__":
    main()