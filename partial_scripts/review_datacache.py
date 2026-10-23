"""Streaming raw-cache review; inspect by default, fetch only in explicit modes."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from config.symbols import SYMBOL_LISTS
from backtest.data_loader import DataLoader
from backtest.data_cleaning import (
    CleaningPolicy, _session_counts, prepare_market_data, pricing_symbols,
)
from backtest.history import binning_to_minutes


def main():
    list_name = os.getenv('REVIEW_SYMBOLS_LIST', 'LIST_5').upper()
    if list_name not in SYMBOL_LISTS:
        raise ValueError(f'Unknown symbol list: {list_name}')
    symbols = pricing_symbols(SYMBOL_LISTS[list_name])
    start = datetime.fromisoformat(os.getenv('REVIEW_START_TIME', '2016-01-01T00:00:00+00:00'))
    end = datetime.fromisoformat(os.getenv('REVIEW_END_TIME', '2026-06-30T23:59:00+00:00'))
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError('Provide aware timestamps with start < end')
    binning = os.getenv('REVIEW_BINNING', '1m')
    mode = os.getenv('REVIEW_MODE', 'inspect')
    if mode not in ('inspect', 'fill', 'refresh'):
        raise ValueError('REVIEW_MODE must be inspect, fill, or refresh')
    output = Path(os.getenv('REVIEW_CHANGES_PATH', str(PROJECT_ROOT / 'data_cache_review.md')))
    output.parent.mkdir(parents=True, exist_ok=True)
    policy = CleaningPolicy.from_environment()
    minutes = binning_to_minutes(binning)
    loader = DataLoader()

    def load(symbol):
        data, warning = loader.load_bars(
            [symbol], start, end, binning, prefilter_stale_symbols=False,
            cache_only=mode == 'inspect', refresh_cache=mode == 'refresh',
            include_dependencies=False,
        )
        return data[symbol], warning

    spy, _ = load('SPY')
    reference = _session_counts(spy, minutes)
    del spy
    lines = [
        '# Data cache review', '', f'Mode: **{mode}**. Range: {start.isoformat()} to {end.isoformat()}. Binning: {binning}.',
        'Includes distribution children and SPY. Raw prices are never rewritten by cleaning.',
        'Coverage uses observed regular-session SPY bars; a populated file does not prove complete source coverage.', '',
        '| Symbol | Raw rows in range | Accepted | Invalid | Outliers | Ineligible bars | Eligible sessions | First / last accepted |',
        '|---|---:|---:|---:|---:|---:|---:|---|',
    ]
    for index, symbol in enumerate(symbols, 1):
        print(f'Review {index}/{len(symbols)}: {symbol}', flush=True)
        rows, warning = load(symbol)
        prepare_market_data({symbol: rows}, end, minutes, policy, reference=reference)
        valid = [t for t, row in rows.items() if row.get('data_quality') == 'OK']
        c = rows.summary
        bounds = f'{min(valid).isoformat()} / {max(valid).isoformat()}' if valid else '**MISSING**'
        lines.append(f'| {symbol} | {len(rows):,} | {c.get("OK", 0):,} | {c.get("INVALID", 0):,} | {c.get("OUTLIER", 0):,} | {c.get("ineligible_bars", 0):,} | {c.get("eligible_sessions", 0)}/{c.get("reference_sessions", 0)} | {bounds} |')
        output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        del rows, valid
    lines.extend(['', 'Modes: inspect reads cached data only; fill fetches missing outer ranges and missing securities; refresh refetches the full range, including potential interior holes.',
                  'Missing intervals may be listing boundaries, market closures, or genuine no-trade periods. Inspect suspicious coverage before treating it as complete.'])
    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Report: {output}', flush=True)


if __name__ == '__main__':
    main()
