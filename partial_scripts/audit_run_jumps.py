"""Audit saved ALL_Year equity curves and reconstruct positions from execution logs.

Uses local artifacts only; does not fetch prices or rerun/modify simulations.
"""
from __future__ import annotations
import argparse
import bisect
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
BAR_RE = re.compile(r'^Bar (\d+) @ (.+):$')
TRADE_RE = re.compile(r'^  (\w+): (BUY|SELL) ([\d.]+) (\w+) @ \$([\d.]+)$')


def scan(root, threshold):
    runs, anchors = [], defaultdict(dict)
    for group in sorted(root.glob('ALL_Year*')):
        for run in sorted(p for p in group.iterdir() if p.is_dir()):
            cp = run/'artifacts/json/curves_data.json'
            info = dict(run=str(run.relative_to(PROJECT)), completed=cp.exists())
            runs.append(info)
            if not cp.exists():
                continue
            year = int(re.search(r'MR_(\d{4})', run.name)[1])
            info['anchor_year'] = year
            curves = json.loads(cp.read_text())
            info['curve_count'] = len(curves)
            info['curve_length'] = len(next(iter(curves.values())))
            events = []
            for name, values in curves.items():
                a = np.asarray(values, dtype=float)
                returns = np.divide(np.diff(a), a[:-1], out=np.zeros(len(a)-1), where=a[:-1]!=0)
                for j in np.flatnonzero(abs(returns) >= threshold):
                    i = int(j+1)
                    events.append(dict(run=info['run'], anchor_year=year, strategy=name, bar=i,
                                       pct=float(returns[j]*100), delta=float(a[i]-a[j]),
                                       before=float(a[j]), after=float(a[i]), terminal=i==len(a)-1))
            by_bar = defaultdict(list)
            for e in events:
                by_bar[e['bar']].append(e)
            positions = defaultdict(lambda: defaultdict(float))
            event_ids = sorted(by_bar)
            cursor = 0
            bar, trades = None, []
            def finish_bar():
                nonlocal cursor
                if bar is None:
                    return
                while cursor < len(event_ids) and event_ids[cursor] <= bar:
                    event_bar = event_ids[cursor]
                    for e in by_bar[event_bar]:
                        e['positions_before'] = {s:q for s,q in positions[e['strategy']].items() if q>1e-8}
                        e['trades'] = [t for t in trades if t['strategy']==e['strategy']] if event_bar==bar else []
                    cursor += 1
                for t in trades:
                    positions[t['strategy']][t['symbol']] += t['quantity'] * (1 if t['action']=='BUY' else -1)
            for line in (run/'artifacts/trades_log.txt').read_text().splitlines():
                m = BAR_RE.match(line)
                if m:
                    finish_bar()
                    bar=int(m[1]); trades=[]
                    dt=datetime.fromisoformat(m[2]).replace(tzinfo=timezone.utc)
                    old = anchors[year].get(bar)
                    if old and old != dt:
                        raise ValueError(f'Inconsistent bar anchors for {year}, bar {bar}')
                    anchors[year][bar] = dt
                elif line.startswith('LIQUIDATION TRADES'):
                    break
                else:
                    m = TRADE_RE.match(line)
                    if m:
                        trades.append(dict(strategy=m[1],action=m[2],quantity=float(m[3]),symbol=m[4],price=float(m[5])))
            finish_bar()
            while cursor < len(event_ids):
                for e in by_bar[event_ids[cursor]]:
                    e['positions_before'] = {s:q for s,q in positions[e['strategy']].items() if q>1e-8}
                    e['trades'] = []
                cursor += 1
            info['events'] = events
            print(f'{run.name}: {len(events)} jumps', flush=True)
    keys = {y: sorted(a) for y,a in anchors.items()}
    for run in runs:
        for e in run.get('events', []):
            y=e['anchor_year']; i=e['bar']; a=anchors[y]; ids=keys[y]; p=bisect.bisect_left(ids,i)
            if i in a:
                e['timestamp']=a[i].isoformat(); e['timestamp_method']='logged'
            elif 0 < p < len(ids) and (a[ids[p]]-a[ids[p-1]]).total_seconds()==(ids[p]-ids[p-1])*60:
                e['timestamp']=(a[ids[p-1]]+timedelta(minutes=i-ids[p-1])).isoformat()
                e['timestamp_method']='contiguous minute anchors'
            else:
                e['timestamp']=None; e['timestamp_method']='unresolved'
                e['timestamp_lower']=a[ids[max(0,p-1)]].isoformat()
                e['timestamp_upper']=a[ids[min(len(ids)-1,p)]].isoformat()
    return runs


def attribute(runs, output):
    import pyarrow.parquet as pq
    from scripts.data_fixes.corporate_actions import get_price_adjustment_events
    from scripts.data_fixes.list_of_corp_act import CORPORATE_ACTIONS
    events=[e for r in runs for e in r.get('events',[]) if e.get('timestamp') and not e['terminal']]
    requests=defaultdict(list)
    for e in events:
        e['components']=[]
        for symbol in set(e['positions_before']) | {t['symbol'] for t in e['trades']}:
            requests[symbol].append(e)
    for n,(symbol, symbol_events) in enumerate(sorted(requests.items()),1):
        path=PROJECT/'data_cache'/f'{symbol}_1m.parquet'
        if not path.exists():
            continue
        table=pq.read_table(path, columns=['timestamp','close','high','low','volume'])
        ts=table['timestamp'].cast('int64').to_numpy()
        raw=table['close'].to_numpy()
        high=table['high'].to_numpy(); low=table['low'].to_numpy(); volume=table['volume'].to_numpy()
        adjustments=get_price_adjustment_events(symbol)
        adj=raw.copy()
        for dt,factor,_ in adjustments:
            adj[ts < int(dt.timestamp()*1e6)] *= factor
        # Reproduce the loader's one global raw/adjusted decision per load window.
        bases={}
        for year in {e['anchor_year'] for e in symbol_events}:
            start=int(datetime(year-1,12,31,tzinfo=timezone.utc).timestamp()*1e6)
            stop=int(datetime(year+2,7,1,tzinfo=timezone.utc).timestamp()*1e6)
            raw_score=adj_score=0.
            for dt,_,_ in adjustments:
                boundary=int(dt.timestamp()*1e6)
                k=int(np.searchsorted(ts,boundary))
                if 0<k<len(ts) and start<=ts[k-1] and ts[k]<stop:
                    raw_score+=abs(raw[k]/raw[k-1]-1)
                    adj_score+=abs(adj[k]/adj[k-1]-1)
            chosen=bool(adj_score+1e-9<raw_score)
            prices=adj if chosen else raw
            valid=np.isfinite(prices) & (prices>0)
            ratios=np.ones(len(prices)); ratios[1:]=prices[1:]/prices[:-1]
            valid[1:] &= abs(ratios[1:]-1)<=.08
            valid[0]=False
            ids=np.flatnonzero(valid)
            bases[year]=(chosen,prices,ids,ratios)
        for e in symbol_events:
            chosen,prices,ids,ratios=bases[e['anchor_year']]
            dt=datetime.fromisoformat(e['timestamp']); timestamp=int(dt.timestamp()*1e6)
            p=int(np.searchsorted(ts[ids],timestamp,side='left'))-1
            c=int(np.searchsorted(ts[ids],timestamp,side='right'))-1
            if min(p,c)<0:
                continue
            pi=int(ids[p]); ci=int(ids[c]); prev=float(prices[pi]); current=float(prices[ci])
            qty=e['positions_before'].get(symbol,0)
            holding_pnl=qty*(current-prev)
            trade_pnl=sum((1 if t['action']=='BUY' else -1)*t['quantity']*(current-t['price'])-1
                          for t in e['trades'] if t['symbol']==symbol)
            pnl=holding_pnl+trade_pnl
            if abs(pnl)<.01:
                continue
            def iso(t):
                return datetime.fromtimestamp(int(t)/1e6,timezone.utc).isoformat()
            action_events=[a for a in CORPORATE_ACTIONS.get(symbol,[]) if abs((datetime.fromisoformat(a['date']).date()-dt.date()).days)<=3]
            comp=dict(symbol=symbol,quantity=qty,pnl=pnl,holding_pnl=holding_pnl,trade_pnl=trade_pnl,
                      previous_price=prev,current_price=current,raw_previous_close=float(raw[pi]),raw_current_close=float(raw[ci]),
                      previous_timestamp=iso(ts[pi]),current_timestamp=iso(ts[ci]),
                      current_raw_one_bar_pct=float((ratios[ci]-1)*100), skipped_rows=ci-pi-1,
                      gap_minutes=float((ts[ci]-ts[pi])/60e6), basis_adjusted=chosen,
                      volume=int(volume[ci]),high=float(high[ci]),low=float(low[ci]),
                      nearby_actions=action_events)
            if ci+1<len(ts):
                comp['next_raw_close']=float(raw[ci+1]); comp['next_timestamp']=iso(ts[ci+1])
            if abs(pnl)>500:
                comp['context']=[dict(timestamp=iso(ts[j]),raw_close=float(raw[j]),price=float(prices[j]),
                                      raw_one_bar_pct=float((ratios[j]-1)*100),volume=int(volume[j]),
                                      accepted=bool(j in ids[max(0,c-7):c+9]))
                                 for j in range(max(0,ci-5), min(len(ts),ci+6))]
            e['components'].append(comp)
        if n%25==0:
            print(f'Attributed {n}/{len(requests)} symbols',flush=True)
    for e in events:
        e['components'].sort(key=lambda c:-abs(c['pnl']))
        e['explained_delta']=sum(c['pnl'] for c in e['components'])
        e['residual']=e['delta']-e['explained_delta']
    (output/'attribution.json').write_text(json.dumps(dict(runs=runs),indent=2)+'\n')
    print('Residual > $50:', sum(abs(e['residual'])>50 for e in events),'of',len(events),flush=True)
    for e in sorted(events,key=lambda e:-abs(e['pct']))[:30]:
        print(e['run'],e['strategy'],e['timestamp'],round(e['pct'],2),'residual',round(e['residual'],2),
              [(c['symbol'],round(c['pnl'],2),c['previous_price'],c['current_price'],c['skipped_rows']) for c in e['components'][:3]],flush=True)


def summarize(runs, output):
    """Write an event ledger, run inventory, and reproducible summary counts."""
    import pytz
    from datetime import time
    eastern=pytz.timezone('America/New_York')
    rows=[]
    for run in runs:
        for e in run.get('events',[]):
            c=e['components'][0]
            transient=(c.get('next_timestamp')
                       and (datetime.fromisoformat(c['next_timestamp'])-datetime.fromisoformat(c['current_timestamp'])).total_seconds()<=600
                       and abs(c['next_raw_close']/c['raw_previous_close']-1)<=.01
                       and abs(c['raw_current_close']/c['raw_previous_close']-1)>=.03)
            if c['symbol']=='LCID' and e['timestamp'].startswith('2025-09-02'):
                category='missing_split'
            elif c['symbol']=='GE' and e['timestamp'].startswith('2023-01-04'):
                category='unmodeled_spin_off'
            elif c['skipped_rows']:
                category='reentry_after_rejected_bars'
            elif transient:
                category='transient_reversal_candidate'
            elif c['gap_minutes']>=5:
                category='sparse_or_session_repricing'
            else:
                category='other_accepted_movement'
            session='regular' if time(9,30)<=datetime.fromisoformat(e['timestamp']).astimezone(eastern).time()<time(16) else 'extended'
            rounding_bound=.03+sum(t['quantity']*.005 for t in e['trades'])
            rows.append(dict(run=e['run'],strategy=e['strategy'],bar=e['bar'],timestamp_utc=e['timestamp'],
                             timestamp_method=e['timestamp_method'],category=category,session=session,
                             portfolio_change_pct=round(e['pct'],6),portfolio_change_dollars=round(e['delta'],2),
                             dominant_symbol=c['symbol'],dominant_pnl=round(c['pnl'],4),quantity=c['quantity'],
                             previous_price=c['previous_price'],current_price=c['current_price'],
                             dominant_exposure_before_pct=round(100*c['quantity']*c['previous_price']/e['before'],4),
                             rejected_rows_between_marks=c['skipped_rows'],minutes_between_marks=c['gap_minutes'],
                             current_bar_volume=c['volume'],position_to_bar_volume=round(c['quantity']/max(1,c['volume']),4),
                             attribution_residual=round(e['residual'],6),rounding_bound=round(rounding_bound,6),
                             within_rounding_bound=abs(e['residual'])<=rounding_bound))
    rows.sort(key=lambda r:-abs(r['portfolio_change_pct']))
    with (output/'jumps.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    run_rows=[dict(run=r['run'],saved_curves=r['completed'],curve_count=r.get('curve_count',0),
                   curve_length=r.get('curve_length',0),jump_count=len(r.get('events',[]))) for r in runs]
    with (output/'runs.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(run_rows[0])); writer.writeheader(); writer.writerows(run_rows)
    summary=dict(run_directories=len(runs),runs_with_curves=sum(r['completed'] for r in runs),
                 curves=sum(r.get('curve_count',0) for r in runs),
                 adjacent_comparisons=sum(r.get('curve_count',0)*(r.get('curve_length',1)-1) for r in runs),
                 jump_events=len(rows),unique_timestamps=len({r['timestamp_utc'] for r in rows}),
                 categories=dict(Counter(r['category'] for r in rows)),
                 dominant_symbols=dict(Counter(r['dominant_symbol'] for r in rows)),
                 session_counts=dict(Counter(r['session'] for r in rows)),
                 all_reconciled=all(r['within_rounding_bound'] for r in rows))
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


def plot_examples(runs, output):
    """Plot the cached price and the mark implied by the current quality filter."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases=[('SOUN','2022-05-02T09:30:00+00:00','SOUN: rejected rally returns as +85% equity jump'),
           ('BBAI','2023-01-12T13:05:00+00:00','BBAI: news rally accepted in large steps'),
           ('LCID','2025-09-02T13:01:00+00:00','LCID: missing reverse split creates false profit'),
           ('GE','2023-01-04T09:02:00+00:00','GE: spin-off shares are never credited'),
           ('GREE','2025-05-09T13:37:00+00:00','GREE: 7.67% tick passes the 8% filter'),
           ('GREE','2026-06-09T09:32:00+00:00','GREE: rejected move returns on a 404-share bar')]
    es=[e for r in runs for e in r.get('events',[])]
    fig,axes=plt.subplots(3,2,figsize=(15,12),layout='constrained')
    for ax,(symbol,timestamp,title) in zip(axes.flat,cases):
        e=max((e for e in es if e['timestamp']==timestamp and e['components'][0]['symbol']==symbol),key=lambda e:abs(e['pct']))
        c=e['components'][0]; context=c['context']; x=np.arange(len(context))
        prices=[r['price'] for r in context]; mark=[]; last=None
        for r in context:
            if r['accepted']:
                last=r['price']
            mark.append(last if last is not None else float('nan'))
        ax.plot(x,prices,'o-',color='#9ca3af',label='Cached close',lw=1.4,markersize=4)
        ax.step(x,mark,where='post',color='#2563eb',label='Valuation mark after filtering',lw=2)
        rejected=[j for j,r in enumerate(context) if not r['accepted']]
        ax.scatter(rejected,[prices[j] for j in rejected],marker='x',s=60,color='#dc2626',label='Rejected close',zorder=4)
        labels=[r['timestamp'][5:10]+'\n'+r['timestamp'][11:16] for r in context]
        ax.set_xticks(x[::2],labels[::2],fontsize=8)
        ax.set_title(title,fontsize=11,loc='left'); ax.set_ylabel('Price ($)'); ax.grid(alpha=.18)
        ax.set_xlabel('Observed symbol bars (UTC; gaps have equal visual spacing)',fontsize=8)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('ALL_Year jump audit — local cached prices and current filter behavior',fontsize=16)
    fig.savefig(output/'jump_examples.png',dpi=170)
    fig.savefig(output/'jump_examples.pdf')
    plt.close(fig)
    print('Saved jump_examples.png and jump_examples.pdf')


def corporate_exposures(runs, output):
    """List holdings at the two reviewed boundaries, including small equity effects."""
    rows=[]
    for run in runs:
        if not run['completed'] or run['anchor_year'] not in (2021,2024):
            continue
        symbol,bar,event=(('LCID',158588,'2025-09-02 reverse split') if run['anchor_year']==2024
                          else ('GE',235797,'2023-01-04 GEHC spin-off'))
        positions=defaultdict(float)
        for line in (PROJECT/run['run']/'artifacts/trades_log.txt').read_text().splitlines():
            m=BAR_RE.match(line)
            if m and int(m[1])>=bar:
                break
            m=TRADE_RE.match(line)
            if m and m[4]==symbol:
                positions[m[1]]+=float(m[3])*(1 if m[2]=='BUY' else -1)
        for strategy,quantity in positions.items():
            if quantity<=0:
                continue
            rows.append(dict(run=run['run'],strategy=strategy,symbol=symbol,event=event,bar=bar,
                             quantity_before=quantity,corrected_quantity=quantity/10 if symbol=='LCID' else quantity,
                             post_event_value_overstatement=round(quantity*.9*18.68,2) if symbol=='LCID' else '',
                             missing_child_quantity=quantity/3 if symbol=='GE' else ''))
    with (output/'corporate_action_exposures.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print('Exposed strategy portfolios:', dict(Counter(r['symbol'] for r in rows)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--threshold', type=float, default=.03)
    parser.add_argument('--output',type=Path, default=PROJECT/'partial_scripts/output/all_year_jump_audit')
    parser.add_argument('--attribute', action='store_true', help='Attribute an existing scan using cached prices')
    parser.add_argument('--summarize', action='store_true', help='Export the attributed event ledger and summary')
    parser.add_argument('--plot', action='store_true', help='Plot six representative attributed events')
    parser.add_argument('--corporate-exposures', action='store_true', help='List all LCID/GE holdings at reviewed boundaries')
    args=parser.parse_args()
    if args.corporate_exposures:
        corporate_exposures(json.loads((args.output/'scan.json').read_text())['runs'], args.output)
        return
    if args.plot:
        plot_examples(json.loads((args.output/'attribution.json').read_text())['runs'], args.output)
        return
    if args.summarize:
        summarize(json.loads((args.output/'attribution.json').read_text())['runs'], args.output)
        return
    if args.attribute:
        attribute(json.loads((args.output/'scan.json').read_text())['runs'], args.output)
        return
    runs=scan(PROJECT/'run_log', args.threshold)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'scan.json').write_text(json.dumps(dict(threshold=args.threshold,runs=runs),indent=2)+'\n')
    events=[e for r in runs for e in r.get('events',[])]
    print('Runs:', len(runs), 'completed:', sum(r['completed'] for r in runs), 'curves:',sum(r.get('curve_count',0) for r in runs))
    print('Events:',len(events),'timestamp methods:',Counter(e['timestamp_method'] for e in events))
    for e in sorted(events,key=lambda e:-abs(e['pct']))[:25]:
        print(e['run'], e['strategy'], e['timestamp'] or (e.get('timestamp_lower'),e.get('timestamp_upper')),round(e['pct'],2), e['positions_before'],e['trades'])

if __name__=='__main__':
    main()
