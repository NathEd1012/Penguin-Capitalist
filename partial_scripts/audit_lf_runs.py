"""Audit saved LF outputs offline; write review files without modifying run data."""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
TRADE = re.compile(r'^  (\w+): (BUY|SELL) ([\d.]+) (\w+) @ \$([\d.]+)$')


def audit(output):
    output.mkdir(parents=True, exist_ok=True)
    tables = {name: [] for name in ['runs', 'curves', 'jumps', 'reversals', 'terminal_positions',
                                    'quality', 'warnings', 'issues']}
    benchmarks, quality_hashes = defaultdict(set), defaultdict(set)
    for batch in sorted((PROJECT / 'run_log').glob('LF_*')):
        for run in sorted(batch.glob('Year*/*')):
            if not run.is_dir():
                continue
            relative = str(run.relative_to(PROJECT))
            year = int(re.search(r'MR_(\d{4})', run.name)[1])
            artifacts = run / 'artifacts'
            log = (artifacts / 'log.out').read_text(errors='replace')
            info = dict(run=relative, batch=batch.name, year=year,
                        completed='Backtest complete!' in log,
                        failed='Traceback (most recent call last)' in log,
                        session_extended='Trading Session:   extended' in log,
                        half_coverage='Minimum Signal Coverage: 50%' in log,
                        curves=0, snapshots=0)
            tables['runs'].append(info)
            for line in log.splitlines():
                if re.search(r'APIError:|ConnectionError:|RuntimeError:|kernel parameters failed|positive-definite|bin/activate:', line):
                    tables['warnings'].append(dict(run=relative, message=line))
            qp = artifacts / 'consistency_warnings.txt'
            if qp.exists():
                # Training repeats the same full loaded-data report. Count once.
                first = qp.read_text().split('TRAINING CONSISTENCY WARNINGS')[0]
                quality_hashes[year].add(hashlib.sha256(first.rstrip('=\n ').encode()).hexdigest())
                for symbol, fields in re.findall(r'^  ([\w.]+): (.*)$', first, re.M):
                    row = dict(run=relative, year=year, symbol=symbol)
                    row.update({k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', fields)})
                    tables['quality'].append(row)
            folder = artifacts / 'json'
            if not (folder / 'curves_data.json').exists():
                continue
            required = ['curves_data', 'curve_timestamps', 'metrics_summary', 'equity_jump_attribution',
                        'valuation_marks', 'validation_selection', 'trainable_penguin_training',
                        'trainable_penguin_parameter_log']
            data = {}
            for name in required:
                path = folder / (name + '.json')
                if not path.exists():
                    tables['issues'].append(dict(run=relative, check='missing_artifact', detail=name))
                else:
                    data[name] = json.loads(path.read_text())
            curves = data['curves_data']
            timestamps = data.get('curve_timestamps', {})
            metrics = data.get('metrics_summary', {})
            attribution = data.get('equity_jump_attribution', {})
            valuation = data.get('valuation_marks', {})
            info['curves'] = len(curves)
            for kind in ['curve_timestamps', 'metrics_summary', 'equity_jump_attribution', 'valuation_marks']:
                if set(data.get(kind, {})) != set(curves):
                    tables['issues'].append(dict(run=relative, check='strategy_keys', detail=kind))
            trade_counts, trade_times = Counter(), defaultdict(list)
            current_time = None
            liquidation = False
            liquidation_strategy = None
            for line in (artifacts / 'trades_log.txt').read_text().splitlines():
                if line.startswith('LIQUIDATION TRADES'):
                    liquidation = True
                    continue
                if line.startswith('STRATEGY SUMMARY'):
                    break
                if liquidation:
                    if re.fullmatch(r'\w+:', line):
                        liquidation_strategy = line[:-1]
                    match = re.match(r'^  SELL ([\d.]+) (\w+) @ \$([\d.]+) at (.+) \[final liquidation\]$', line)
                    if match and liquidation_strategy:
                        qty, symbol, price, time = match.groups()
                        trade_counts[liquidation_strategy] += 1
                        trade_times[liquidation_strategy].append(time.replace(' ', 'T'))
                    continue
                if line.startswith('At '):
                    current_time = line[3:-1]
                match = TRADE.match(line)
                if match:
                    name, side, qty, symbol, price = match.groups()
                    trade_counts[name] += 1
                    trade_times[name].append(current_time)
                    if float(qty) <= 0 or float(price) <= 0:
                        tables['issues'].append(dict(run=relative, check='invalid_trade', detail=line))
            for name, values in curves.items():
                def issue(check, detail):
                    tables['issues'].append(dict(run=relative, strategy=name, check=check, detail=detail))

                a = np.asarray(values, dtype=float)
                ts, m = timestamps.get(name, []), metrics.get(name, {})
                info['snapshots'] += len(a)
                if len(a) != len(ts):
                    issue('timestamp_length', f'{len(a)} != {len(ts)}')
                    continue
                if not len(a):
                    issue('empty_curve', '')
                    continue
                if not np.isfinite(a).all() or np.any(a <= 0):
                    issue('invalid_equity', '')
                backward = sum(left > right for left, right in zip(ts, ts[1:]))
                duplicates = [i + 1 for i, (left, right) in enumerate(zip(ts, ts[1:])) if left == right]
                if backward or any(i != len(ts) - 1 for i in duplicates):
                    issue('timestamp_order', f'backward={backward}; duplicates={duplicates[:10]}')
                if any(not x.endswith('+00:00') for x in ts):
                    issue('non_utc_timestamp', '')
                if abs(a[-1] - m.get('final_value', float('inf'))) > 0.011:
                    issue('final_value', f'{a[-1]} != {m.get("final_value")}')
                drawdown = float(np.min(a / np.maximum.accumulate(a) - 1) * 100)
                if abs(drawdown - m.get('max_drawdown', float('inf'))) > 0.011:
                    issue('max_drawdown', f'{drawdown} != {m.get("max_drawdown")}')
                if abs((a[-1] - 100000) - m.get('total_return', float('inf'))) > 0.011:
                    issue('total_return', '')
                if trade_counts[name] != m.get('total_trades'):
                    issue('trade_count', f'{trade_counts[name]} != {m.get("total_trades")}')
                for time in trade_times[name]:
                    i = bisect.bisect_left(ts, time)
                    if i >= len(ts) or ts[i] != time:
                        issue('trade_outside_curve', time)
                pct, by_index = np.diff(a) / a[:-1], {}
                for event in attribution.get(name, []):
                    i = bisect.bisect_left(ts, event['timestamp'])
                    candidates = [j for j in (i, i + 1) if 0 < j < len(ts) and ts[j] == event['timestamp']]
                    match = next((j for j in candidates if abs(a[j] - event['current_value']) <= 0.011
                                  and abs(a[j-1] - event['previous_value']) <= 0.011), None)
                    if match is None:
                        issue('attribution_curve', event['timestamp'])
                    else:
                        by_index[match] = event
                    accounted = event['cash_change'] + sum(p['contribution'] for p in event['positions'])
                    if abs(accounted - event['change']) > 1e-5:
                        issue('attribution_accounting', f'{event["timestamp"]}: {accounted} != {event["change"]}')
                for j in np.flatnonzero(abs(pct) >= 0.010001):
                    if int(j + 1) not in by_index:
                        issue('missing_attribution', ts[j + 1])
                for j in np.flatnonzero(abs(pct) >= 0.01):
                    i = int(j + 1)
                    event = by_index.get(i, {})
                    lead = max(event.get('positions', []), key=lambda p: abs(p['contribution']), default={})
                    row = dict(run=relative, strategy=name, index=i, timestamp=ts[i],
                               pct=float(pct[j] * 100), change=float(a[i] - a[j]),
                               before=float(a[j]), after=float(a[i]), cash_change=event.get('cash_change'),
                               symbol=lead.get('symbol'), contribution=lead.get('contribution'),
                               mark_status=lead.get('mark_status'), mark=lead.get('mark'),
                               quantity=lead.get('quantity'), mark_age_seconds=lead.get('mark_age_seconds'))
                    tables['jumps'].append(row)
                    if i + 1 < len(a) and abs(pct[j]) >= 0.02 and abs(a[i+1] / a[j] - 1) <= 0.003:
                        tables['reversals'].append({**row, 'next_timestamp': ts[i+1],
                            'next_value': float(a[i+1]), 'remaining_pct': float((a[i+1] / a[j] - 1) * 100)})
                positions = valuation.get(name, {}).get('positions', {})
                stale = sum(bool(p.get('mark_is_stale')) for p in positions.values())
                if stale != m.get('stale_position_count'):
                    issue('stale_count', f'{stale} != {m.get("stale_position_count")}')
                for symbol, position in positions.items():
                    tables['terminal_positions'].append(dict(run=relative, strategy=name, symbol=symbol,
                                                            final_value=float(a[-1]), **position))
                    if abs(position['quantity'] * position['mark'] - position['value']) > 0.011:
                        issue('holding_value', symbol)
                    if position['mark_age_seconds'] < 0:
                        issue('negative_mark_age', symbol)
                tables['curves'].append(dict(run=relative, strategy=name, snapshots=len(a), start=ts[0], end=ts[-1],
                    duplicate_terminal=bool(duplicates), final_value=float(a[-1]), minimum=float(a.min()),
                    maximum=float(a.max()), jumps_1pct=int(np.count_nonzero(abs(pct) >= 0.01)),
                    jumps_3pct=int(np.count_nonzero(abs(pct) >= 0.03)), jumps_5pct=int(np.count_nonzero(abs(pct) >= 0.05)),
                    largest_pct=float(pct[np.argmax(abs(pct))] * 100), open_positions=len(positions),
                    stale_positions=stale, blocked_decisions=m.get('coverage_blocked_decisions'),
                    blocked_orders=m.get('coverage_blocked_orders')))
                if name == 'SP500':
                    benchmarks[year].add(hashlib.sha256(a.tobytes() + '\n'.join(ts).encode()).hexdigest())
            print(f'{batch.name}/{run.name}: {len(curves)} curves checked', flush=True)
    runs, jumps, marks = (tables[k] for k in ['runs', 'jumps', 'terminal_positions'])
    summary = dict(reviewed_at=datetime.now(timezone.utc).isoformat(), runs=len(runs),
        completed=sum(r['completed'] for r in runs), failed=sum(r['failed'] for r in runs),
        curves=len(tables['curves']), snapshots=sum(r['snapshots'] for r in runs), issues=len(tables['issues']),
        jumps_1pct=len(jumps), jumps_3pct=sum(abs(r['pct']) >= 3 for r in jumps),
        jumps_5pct=sum(abs(r['pct']) >= 5 for r in jumps), reversals_2pct=len(tables['reversals']),
        terminal_positions=len(marks), stale_terminal_positions=sum(bool(r['mark_is_stale']) for r in marks),
        benchmark_variants_by_year={str(k): len(v) for k, v in benchmarks.items()},
        quality_variants_by_year={str(k): len(v) for k, v in quality_hashes.items()},
        batches={b: dict(runs=sum(r['batch'] == b for r in runs),
                         completed=sum(r['batch'] == b and r['completed'] for r in runs),
                         failed=sum(r['batch'] == b and r['failed'] for r in runs))
                 for b in sorted({r['batch'] for r in runs})})
    for name, rows in tables.items():
        if rows:
            fields = list(dict.fromkeys(k for row in rows for k in row))
            with (output / (name + '.csv')).open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (output / 'issues.json').write_text(json.dumps(tables['issues'], indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PROJECT / 'partial_scripts/output/lf_quality_audit')
    audit(parser.parse_args().output)
