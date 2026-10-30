# Recent LF run data quality review

Reviewed **2026-10-28, approximately 12:13 CET**. Scope: all 75 runs in `LF_ALL_RUNS_TC1_TS100`, `LF_ALL_RUNS_TC1_TS500`, and `LF_ALL_RUNS_TC1_TS1000`.

**Verdict: the saved outputs are structurally consistent, but the market data cannot yet receive an unconditional clean verdict.** The old timestamp defect is absent, and the previously identified isolated spikes are rejected by the current cleaner. However, suspicious multi-minute price excursions still reach portfolio marks, including a 5.22% portfolio rise that largely reverses two minutes later. A few holdings also retain quotes for months after ticker changes or corporate events.

This is an offline review of local artifacts and cached source bars. No source data, run results, strategy configuration, or running job was changed; no prices were downloaded and no jobs were submitted or cancelled. Suspicious prints have not been independently verified against another data source.

## Run status

| Batch | Expected runs | Final results available | Failed | Still running |
|---|---:|---:|---:|---:|
| TS100 | 25 | 24 | 1 | 0 |
| TS500 | 25 | 25 | 0 | 0 |
| TS1000 | 25 | 0 | 0 | 25 |

Slurm confirms all 25 current TS1000 jobs are running. They are training and have no final curves to audit yet. This includes the open `Year2022/MR_2022_broad_gpei_1000` run. Their final data quality therefore remains pending.

`LF_ALL_RUNS_TC1_TS100/Year2024/MR_2024_broad_tpe_100` failed, job **15554739**, exit **1:0**. Its validation workers stalled for 3,600 seconds, with five Gentoo candidates still at 0%. This is an execution failure; there are no final results to use for that run.

## Checks that passed

The 49 completed runs contain **343 curves and 119,586,248 equity snapshots**. All eight expected JSON artifacts are present in each completed run.

- Every curve has an equally long, correctly ordered UTC timestamp array. The explicit duplicate timestamp for final liquidation is allowed. No earlier duplicate or backward timestamp was found.
- Every equity value is finite and positive. Final equity, total return, and maximum drawdown reconcile with the metrics within export rounding.
- All saved jump-attribution records match their curve values. Cash changes plus position contributions reconcile to the equity change. Curve moves materially above the 1% attribution threshold have attribution records.
- Final open-position quantities, marks, and values reconcile. Stale-position counts agree with the metrics.
- Execution-detail timestamps were checked against the historical XNYS extended-session calendar, including holidays, DST and early closes. **All 1,657,135 execution timestamp headings passed.** Final-liquidation timestamps were separately matched to the corresponding strategy curves by the core audit.
- For each start year, the SP500 curve and its timestamps are identical across the completed algorithms/batches. Prepared-quality summaries are also identical across all 15 runs with that start year, including the running TS1000 batch.
- All 75 run banners record the extended session and the 50% minimum coverage requirement. Completed portfolios record coverage-blocked decisions/orders, so the new gate is active.

Two trade-count differences remain in the text export; these are described below rather than hidden in the passing checks.

## Residual suspicious price excursions

The next-snapshot screen found **zero** moves of at least 2% returning within 0.3% of the pre-move equity on the immediately following snapshot. That narrow screen misses excursions which persist for two or three minutes.

A broader screen found **683 short round-trip occurrences at 289 distinct initial timestamps**: consecutive attribution events, first move at least 1%, separated by at most five minutes, with the second event's final equity within 0.3% of the first event's starting equity. Smaller intermediate moves can occur. Counts repeat events across strategies and batches, include genuine volatility, and are **not counts of confirmed erroneous bars**.

The following examples were traced to raw cached OHLC/volume and replayed through the current cleaner. Times are UTC. Run paths below are relative to `run_log/`.

| Source sequence | Run / strategy | Saved equity impact | Assessment |
|---|---|---|---|
| PLUG, 2024-01-24: accepted 3.61 → pending 4.05 at 13:03 → **confirmed 4.17 at 13:04** → pending 3.63 → confirmed 3.6397 at 13:06 | `LF_ALL_RUNS_TC1_TS100/Year2022/MR_2022_broad_random_100`, RockhopperPenguin | **103,444.83 → 108,243.79 → 103,744.06**; first step **+4.64%**. The 8,545 PLUG shares contribute **+$4,785.20**. | Strong suspect-print pattern. Two elevated closes pass confirmation, and the first return is rejected, keeping the elevated mark for another minute. |
| COIN, 2024-01-03: 146.87 → pending 157.76 at 13:02 → **confirmed 158.20 at 13:03** → pending 146.87 → confirmed 147.4597 at 13:05. RIOT simultaneously marks at 15.65, then 14.30. | `LF_ALL_RUNS_TC1_TS100/Year2023/MR_2023_broad_gpucb_100`, GentooPenguin | **88,377.00 → 92,987.40 → 88,637.34**; first step **+5.22%**, no cash change. COIN contributes **+$2,515.26**, RIOT **+$2,059.20**. | Strong suspect-print pattern affecting multiple holdings at 08:00 ET. The elevated COIN bars span roughly 147–158 but close at their highs. |
| SWKS, 2024-05-01: 91.25 → pending 96.00 at 12:02 → **confirmed 96.00 at 12:04**; 96 persists through 12:05; 91.35 is pending before 91.10 confirms at 12:07 | `LF_ALL_RUNS_TC1_TS100/Year2022/MR_2022_broad_random_100`, GentooPenguin_089 | **49,447.55 → 51,319.05 → 49,388.45**; **+3.78%**, then **−3.76%**. First step is exactly **394 × (96 − 91.25) = $1,871.50**. | Repeated elevated prints can satisfy the two-observation and $100,000 combined-dollar-volume rule. |
| SPY, 2023-03-24 at 12:00–12:02: **389.96 → 394.50 → 389.53**, all accepted | All ten completed Year2022 runs, SP500 | **100,943.99 → 102,115.31 → 100,833.05**; **+1.16%**, then **−1.26%**. | A below-2% price excursion still passes the normal threshold, including in the benchmark. The broader event file contains 20 occurrences because it also includes other exposed curves. |

These examples establish that the source prices enter valuations and explain the dollar changes. They do not establish whether each print is erroneous, stale, or an unusual valid execution; independent quotes or trade-condition data are needed for that distinction. The examples alone also do not quantify their effect on final returns or optimizer selection.

The old TXN/ADBE/INTU/INTC/KMI/KTOS examples were replayed from local source bars. All six excursion observations are now `OUTLIER/PENDING_REGIME`, with the returning observations accepted as `REVERSION`. Evidence is in `known_spike_replays.json`. The remaining weakness is therefore broader than the isolated-print cases covered by those fixes.

Not every large move is suspicious. The reviewed SPCE, BLUE, MARA and PLUG large-loss sequences show sustained or evolving source prices after the move. Some of the largest percentage changes are $1 fees on a nearly exhausted portfolio: the −22.65% maximum step is only a **$0.99** loss from **$4.37** to **$3.38**. Neither a large return nor a reversal is sufficient grounds to delete a bar.

## Old terminal marks and symbol lifecycle gaps

Across the completed runs, **2,412 positions remain open**, **2,015** with carried marks. Most carried marks are intraday; a stale flag alone does not imply bad data. Retaining holdings through absent quotes is the intended policy and is not a reason to invent a sale.

**17 position occurrences in eight portfolios across six runs have marks older than 72 hours**. These are concentrated in four symbols:

| Symbol | Position occurrences | Approximate quote age at run end | Largest marked exposure / final equity |
|---|---:|---:|---|
| GPS | 5 | 313 days | **$2,357.76 / $88,126.08 = 2.68%**, TS100 Year2023/random, RockhopperPenguin |
| SQ | 4 | 164 days | **$261.51 / $64,238.84 = 0.41%**, Year2023/random, EmperorPenguin |
| SPLK | 3 | 472 days | **$627.68 / $87,569.08 = 0.72%**, TS500 Year2023/gpucb, GentooPenguin |
| BLUE | 5 | 31 days | **$1,385.10 / $87,569.08 = 1.58%**, TS500 Year2023/gpucb, GentooPenguin |

The local corporate-action registry records SQ→XYZ and cash mergers for SPLK/BLUE. The execution path handles splits/distributions but has no corresponding ticker-continuation or cash-merger settlement path. GPS's history ends in August 2024 and needs identity/continuation review. The portfolio export faithfully discloses the carried marks; the missing lifecycle handling is the remaining economic-data limitation. The quoted exposure is not an estimate of the valuation error.

## Cleaning and fetch warnings

Quality reports repeat under a training heading. The totals below count the first report only, once per start year. `PENDING_REGIME` equals `OUTLIER` in these reports and must not be added to it.

| Start year | Accepted observations | Rejected outliers | Rejected share | Invalid bars reported |
|---|---:|---:|---:|---:|
| 2020 | 82,572,213 | 405,810 | 0.489% | 0 |
| 2021 | 84,928,260 | 338,333 | 0.397% | 0 |
| 2022 | 85,474,957 | 402,285 | 0.468% | 0 |
| 2023 | 85,910,219 | 394,600 | 0.457% | 0 |
| 2024 | 88,024,225 | 367,773 | 0.416% | 0 |

These counts cover the complete loaded training/validation/test windows and 324 pricing symbols, not just the final test trades. The requested trading universe contains 318 symbols. GREE has zero eligible sessions in the Year2022–2024 reports; many rejections in a blocked symbol do not imply portfolio exposure.

Missing-cache fetch failures occur in **26/75 runs**: 7 TS100, 18 TS500, 1 TS1000. Most are API rate limits; one TS1000 fetch has a connection error. Several requested ranges precede the first cached history or follow its last bar, so the warnings alone do not establish an interior outage. SQ's missing post-January-2025 continuation is a concrete issue, independently visible in stale holdings.

One warning in `TS1000/Year2022/MR_2022_broad_gpucb_1000` reports GP kernel Cholesky failure and explicitly falls back to default initial kernel parameters. Slurm still reports that job running. This affects optimization diagnostics, not evidence of nonfinite market prices.

The launch logs also report the missing `venvPeng/bin/activate`. Jobs proceed with the module Python and installed packages. This is a separate environment-reproducibility issue, not the cause of the price excursions above.

## Two execution-log omissions

After counting the separate final-liquidation section, reported trade counts reconcile for **341/343** portfolios. Two portfolios contain one more trade in their metrics than in the execution ledger:

- TS500 Year2020/gpei, EmperorPenguin_053: **14,823 vs 14,822**.
- TS500 Year2020/random, EmperorPenguin_464: **32,790 vs 32,789**.

Both held BLUE at its 2021-11-05 08:00 UTC distribution boundary: 45 and 4 shares respectively. The first cached TSVT price is at 12:13 UTC. `backtest/market_events.py` executes an `unpriced distribution protection` sale when the child is unpriced. That path calls `portfolio.sell` directly, while `run_simulation.py` only appends ordinary order fills to the execution-detail ledger. This explains the one-sale omission in each case. Equity attribution still reconciles. Historical text exports cannot be used as complete transaction ledgers without accounting for such event-driven sales.

## Follow-up required for a clean verdict

1. Validate the PLUG, COIN/RIOT, SWKS and SPY prints against independent quote/trade-condition data. Improve causal handling of repeated off-market/stale-looking prints and re-test real repricing before changing thresholds. Merely demanding two observations does not remove these cases.
2. Add verified ticker continuation and merger settlement handling for the affected symbols, retaining the intended carry policy for genuine missing quotes and market closures.
3. Include event-driven protection sales in the complete execution export.
4. Recover the failed TS100 Year2024/tpe run. Audit the 25 TS1000 final outputs after they finish; a running training log cannot establish final-result quality.

No cleaner thresholds or historical results were changed during this review. The existing LF results should retain these qualifications when used for strategy comparison.

## Review artifacts and reproduction

Core audit:

```bash
module load devel/python/3.13.1
python partial_scripts/audit_lf_runs.py
```

Outputs are under `partial_scripts/output/lf_quality_audit/`:

- `summary.json`, `runs.csv`, `curves.csv`: coverage, status and per-curve checks.
- `issues.json` / `issues.csv`: the two execution-ledger differences.
- `jumps.csv`: all screened adjacent equity changes of at least 1% with attribution fields. Its largest-position column can reflect an inventory sale; cash must be considered with it.
- `terminal_positions.csv`, `quality.csv`, `warnings.csv`: position provenance and full per-run diagnostics.
- `known_spike_replays.json`, `residual_reversal_replays.json`: targeted raw-cache cleaning replays.
- `short_reversal_candidates.json`: the broader five-minute reversal screen with full saved attributions.
- `execution_session_check.json`: independent execution-calendar check.

The core script regenerates the core CSV/JSON inventory and consistency checks. The targeted replay, broader reversal and calendar files are supplementary evidence produced during this review. All dates and counts are a snapshot; running jobs may add artifacts later.
