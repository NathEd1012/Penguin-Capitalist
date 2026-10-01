# Set these values before running the script.
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import os
from pathlib import Path
import sys

import pandas as pd
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = Path(
	os.environ.get(
		"REVIEW_CHANGES_PATH",
		str(PROJECT_ROOT.parent / "slurm_scripts" / "logs" / "review_datacache_changes.txt"),
	)
)
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from config.symbols import SYMBOL_LISTS
from backtest.data_loader import DataLoader

SYMBOLS_LIST = os.environ.get("REVIEW_SYMBOLS_LIST", "LIST_5")
LIST_5 = SYMBOL_LISTS.get(SYMBOLS_LIST.upper(), [])
START_TIME = os.environ.get("REVIEW_START_TIME", "2023-01-01T00:00:00+00:00")
END_TIME = os.environ.get("REVIEW_END_TIME", "2026-06-30T23:59:00+00:00")
BINNING = os.environ.get("REVIEW_BINNING", "1m")


def parse_time(value: str) -> datetime:
	parsed = pd.Timestamp(value)
	if parsed.tzinfo is None:
		parsed = parsed.tz_localize(timezone.utc)
	return parsed.to_pydatetime()


def cached_rows(loader: DataLoader, symbol: str) -> int:
	cached = loader.cache.get_cached_slice(
		symbol,
		BINNING,
		parse_time(START_TIME),
		parse_time(END_TIME),
	)
	return 0 if cached is None else len(cached)


def main() -> None:
	symbols = list(dict.fromkeys(symbol.strip().upper() for symbol in LIST_5 if symbol.strip()))
	if not symbols:
		raise ValueError(
			f"Unknown or empty symbol list '{SYMBOLS_LIST}'. "
			f"Choose one of: {', '.join(SYMBOL_LISTS)}"
		)

	start_time = parse_time(START_TIME)
	end_time = parse_time(END_TIME)
	if start_time >= end_time:
		raise ValueError("START_TIME must be earlier than END_TIME")

	loader = DataLoader()
	results = []
	warnings = []
	for symbol in tqdm(
		symbols,
		desc="Reviewing tickers",
		unit="ticker",
		file=sys.stdout,
	):
		before_rows = cached_rows(loader, symbol)
		with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
			data, warning = loader.load_bars(
				[symbol],
				start_time,
				end_time,
				binning=BINNING,
				prefilter_stale_symbols=False,
				refresh_cache=True,
			)
		after = cached_rows(loader, symbol)
		fetched = len(data.get(symbol, {}))
		delta = after - before_rows
		results.append((symbol, before_rows, after, fetched, delta))
		if warning:
			warnings.append(f"{symbol}: {warning}")

	added_total = sum(max(delta, 0) for *_values, delta in results)
	output_lines = [
		"# Data Cache Review Results",
		"",
		f"- Range: `{start_time.isoformat()}` to `{end_time.isoformat()}`",
		f"- Timeframe: `{BINNING}`",
		f"- Symbols reviewed: {len(symbols)}",
		f"- Rows added to cache: **{added_total:,}**",
		"",
		"| Symbol | Rows before | Rows after | Rows loaded | Cache change |",
		"|---|---:|---:|---:|---:|",
	]
	output_lines.extend(
		f"| {symbol} | {before_rows:,} | {after_rows:,} | {loaded_rows:,} | {delta:+,} |"
		for symbol, before_rows, after_rows, loaded_rows, delta in results
	)
	if warnings:
		output_lines.extend(["", "Loader warnings:", *warnings])
	OUTPUT_PATH.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
	main()

