"""Create a multi-page PDF with one cached stock chart per page."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data_cache"
OUTPUT_PATH = PROJECT_ROOT / "data_cache_all_stocks_2016_2026-07.pdf"
START = pd.Timestamp("2016-01-01", tz="UTC")
END = pd.Timestamp("2026-07-01", tz="UTC")


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def add_error_page(pdf: PdfPages, symbol: str, start: datetime, end: datetime, error: Exception) -> None:
    figure, axis = plt.subplots(figsize=(11, 7))
    axis.axis("off")
    axis.text(0.02, 0.90, symbol, fontsize=22, fontweight="bold", transform=axis.transAxes)
    axis.text(0.02, 0.82, "Data could not be plotted", fontsize=15, color="#a33", transform=axis.transAxes)
    axis.text(
        0.02,
        0.72,
        f"Metadata range: {format_timestamp(start)} to {format_timestamp(end)}",
        fontsize=11,
        transform=axis.transAxes,
    )
    axis.text(0.02, 0.64, f"Error: {type(error).__name__}: {error}", wrap=True, transform=axis.transAxes)
    figure.tight_layout()
    pdf.savefig(figure)
    plt.close(figure)


def add_stock_page(pdf: PdfPages, symbol: str, metadata: dict[str, object], parquet_path: Path) -> str:
    start = parse_timestamp(str(metadata["start"]))
    end = parse_timestamp(str(metadata["end"]))
    try:
        data = pd.read_parquet(parquet_path, columns=["timestamp", "close"])
        data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
        data["close"] = pd.to_numeric(data["close"], errors="coerce")
        data = data.dropna(subset=["timestamp", "close"])
        data = data[(data["timestamp"] >= START) & (data["timestamp"] < END)]
        if data.empty:
            raise ValueError("no valid close data in the requested 2016-01-01 to 2026-07-01 range")

        daily = (
            data.set_index("timestamp")["close"]
            .sort_index()
            .resample("1D")
            .last()
            .dropna()
        )
        if daily.empty:
            raise ValueError("no daily close values after resampling")

        figure, axis = plt.subplots(figsize=(11, 7))
        axis.plot(daily.index, daily.values, color="#1769aa", linewidth=1.0)
        axis.set_title(f"{symbol} | 1-minute cache, daily last close", loc="left", fontsize=16, fontweight="bold")
        axis.set_xlabel("Date")
        axis.set_ylabel("Close")
        axis.grid(True, alpha=0.25)
        axis.xaxis.set_major_locator(mdates.YearLocator())
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        axis.set_xlim(START.to_pydatetime(), END.to_pydatetime())
        axis.text(
            1.0,
            1.02,
            f"{format_timestamp(start)} to {format_timestamp(end)} | {len(data):,} bars | {len(daily):,} daily points",
            ha="right",
            va="bottom",
            fontsize=8,
            transform=axis.transAxes,
        )
        figure.tight_layout()
        pdf.savefig(figure)
        plt.close(figure)
        return "plotted"
    except Exception as error:
        add_error_page(pdf, symbol, start, end, error)
        return "unreadable"


def main() -> None:
    meta_paths = sorted(CACHE_DIR.glob("*_1m.meta.json"))
    plotted = 0
    unreadable = 0
    with PdfPages(OUTPUT_PATH) as pdf:
        for meta_path in meta_paths:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            parquet_path = meta_path.with_suffix("").with_suffix(".parquet")
            status = add_stock_page(pdf, str(metadata["symbol"]), metadata, parquet_path)
            if status == "plotted":
                plotted += 1
            else:
                unreadable += 1

    print(f"Wrote {OUTPUT_PATH} with {len(meta_paths)} pages")
    print(f"Plotted: {plotted}; unreadable/error pages: {unreadable}")


if __name__ == "__main__":
    main()
