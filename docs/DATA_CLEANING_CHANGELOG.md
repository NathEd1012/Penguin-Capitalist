# Data cleaning implementation log

## 2026-10-27: require half of expected observations in each signal window

The user requested that strategies stop trading when less than half of their data is present. `backtest/signal_coverage.py` now maintains bounded, causal per-symbol observation slots on a historical XNYS calendar, supplied by the new `exchange-calendars>=4.11,<5` dependency.

- Every actual indicator period must have at least 50% coverage in its recent expected trading-bar window. Exactly half passes. Fixed 10/30/60-bar trend windows are included for strategies that use them. Storage buffers and global parameter-search maxima do not substitute for individual indicator periods. Normal full-history warmup still applies.
- Missing, rejected and zero-volume observations do not count. A session calendar supplies the denominator independently of observed SPY data, so a whole-feed outage cannot shrink the expected window. SPY coverage is checked separately for relative-strength inputs.
- `DATA_TRADING_SESSION` selects `extended` (default, 04:00–20:00 ET and 17:00 on scheduled half-days) or `regular` (core session). Weekends, holidays, special full-day closures, early closes and DST are handled by the calendar. UTC session-date labels are used for daily bars; intraday bars use provider bin starts. Outside-session data does not advance marks, indicators or execution quotes.
- Both per-symbol and batch strategies enforce coverage before decisions. Deferred buys and sells are rechecked when due; an order that fails coverage is discarded. Final liquidation cannot bypass coverage. Holdings and indicator histories are preserved while blocked. Buy-and-hold SP500/SP500x2 explicitly declare no indicator windows and still require current in-session execution quotes.
- Metrics/trade logs count coverage-blocked decisions/orders; the run banner records the minimum and selected session. Session schedules are cached across optimization trials, and per-symbol observation tracking is bounded by the largest active window.

The change applies through the shared engine to training, validation and test. Raw and prepared source bars and old results are unchanged; simulations/training must be rerun for updated results. Existing prior-session eligibility checks remain additional conditions. The earlier gap-carry policy below is retained, with this new signal-readiness gate and exchange calendar added.

Verification: **74 active tests pass**, including exact-half/below-half boundaries, individual short-window enforcement, recovery, bounded tracking, invalid/zero-volume exclusions, benchmark coverage, per-symbol and batch decisions, deferred buys/sells, final liquidation, holidays, special closures, early closes, DST and all supported binnings. A 4,058-bar offline SPY holiday replay still produces one buy and one final liquidation, with no gap sale. `git diff --check` passes. No market-data downloads or training jobs were run.

## 2026-10-27: carry stale valuations without synthetic gap sales

The 72-calendar-hour liquidation rule also sold SPY across ordinary holiday weekends. It executed at an old price without a current quote, then the benchmark bought again. The earlier description of this as protective behavior is superseded by the following rules.

- `prepared-bars-v3` no longer generates gap-liquidation events. Legacy `stale` events are ignored, including when old prepared inputs are passed directly to a backtest. Holdings, indicator history and pending orders are not cleared by those events.
- Portfolio valuations carry the last accepted mark when no new accepted positive-volume observation exists. `mark_timestamp`, `mark_age_seconds` and `mark_is_stale` expose the provenance. A stale flag describes a carried valuation; it does not distinguish a market closure from a data outage and does not trigger a trade.
- Missing, rejected and zero-volume observations do not advance indicator histories. RSI/SMA formulas are unchanged, history survives gaps, and the next accepted bar includes the price change since the prior observation. Periods count accepted observations rather than missing clock intervals.
- Final liquidation uses only current tradable bid quotes. Positions without one remain open and their marked values remain in final equity. No cash proceeds or sale fee are invented for them.
- `valuation_marks.json` and the text trade report expose final open holdings and their quote ages. Metrics include `stale_position_count`. Liquidation reporting identifies trades by their explicit reason, rather than treating every final-timestamp trade as liquidation.
- PDF/CSV accounting uses each portfolio's recorded prices for remaining holdings, includes their market value in P&L, and avoids counting open inventory cost twice. PDF strategy summaries identify stale valuations.
- The 72-hour reference-age limit remains only in outlier-baseline and distribution-child-price validation; it no longer resets strategy history or liquidates a position. No exchange-calendar dependency is introduced: normal closures carry valuations and preserve holdings in the same way as any absent quote.

Raw cache and historical outputs are unchanged. Versioned processed caches rebuild automatically; rerun simulations and training to obtain results under the new execution policy.

Verification: **52 active tests pass**, including a two-worker run, retained holdings through gaps, gap-loss recognition, RSI history continuity, zero-volume rejection, stale terminal holdings, and JSON/text/PDF accounting. An offline replay of **4,058 cached SPY bars** from January 15–22, 2025 spans the January holiday closure and executes exactly **one buy and one final liquidation**, with no gap sale or repurchase. `git diff --check` passes. No downloads or training jobs were run.

## 2026-10-26: residual-jump and timeline correction

The ALL_RUNS review found two independent problems: isolated 2-8% source-price reversals could pass the original high-volume threshold, and parallel strategies were exported against the first completed worker's timestamp grid. The latter mislabeled trades and silently shortened plotted curves whenever strategies used different symbol calendars.

### Implemented changes

| File | Correction |
|---|---|
| `backtest/data_cleaning.py` | Advances the prepared-bar contract to `prepared-bars-v2`. Moves above 2% become `PENDING_REGIME`; a new level requires two mutually coherent positive-volume observations and at least $100,000 of combined dollar volume. A return to the accepted level is marked `REVERSION`. Confirmed levels are marked `CONFIRMED_REGIME`. Thinness also considers volume below 10% of the recent 20-observation median, with a 1% default threshold. All decisions remain causal. |
| `backtest/portfolio.py` | Stores one UTC timestamp per equity value and tracks the timestamp/status of every mark. Equity changes of at least 1% receive cash and per-position attribution, including held quantity, mark, contribution, mark age, observed rejected price, and whether the mark was fresh, carried, pending, reverted, or confirmed. |
| `run_simulation.py` | Parallel results retain `timestamps_by_strategy`. Execution details are merged by actual UTC timestamp instead of incomparable worker-local bar indices. Valuation passes bar-quality metadata into attribution, and final-liquidation snapshots receive explicit timestamps. |
| `backtest/evaluator.py` | Validates that each curve and its own timestamp array have equal lengths. Writes `curve_timestamps.json` and `equity_jump_attribution.json`; trade-log headings now contain actual ISO UTC timestamps. |
| `scripts/plotting.py` | Plots each curve against its own timestamps. Supplied length mismatches raise an error instead of truncating values with `min(...)`. Shared axes span all strategy calendars. |
| `tests/test_data_cleaning.py` | Adds causal regression cases for the observed INTC, KMI, and KTOS reversals, sustained regime confirmation, timestamped attribution, explicit liquidation timestamps, and parallel workers with different grids. |
| `tests/test_reporting_alignment.py` | Verifies strict plot/export alignment and the new timestamp, trade-time, and jump-attribution artifacts. |

### New defaults

| Rule | Default / setting |
|---|---|
| Move requiring confirmation | 2%, `DATA_CONFIRMATION_JUMP_PCT` |
| Candidate-level coherence | 5%, `DATA_CONFIRMATION_TOLERANCE_PCT` |
| Coherent positive-volume observations | 2, `DATA_CONFIRMATION_BARS` |
| Combined confirmation dollar volume | $100,000, `DATA_CONFIRMATION_DOLLAR_VOLUME` |
| Thin-observation move | 1%, `DATA_THIN_MAX_JUMP_PCT` |
| Relative thinness | Below 10% of recent median, `DATA_THIN_RELATIVE_VOLUME` |
| Relative-volume window | 20 accepted observations, `DATA_VOLUME_WINDOW` |
| Equity attribution threshold | 1%, `EQUITY_ATTRIBUTION_MIN_MOVE_PCT` |

The 8% `DATA_CONSISTENCY_MAX_JUMP_PCT` remains the hard unexplained-move bound used by optional permanent quarantine. The lower confirmation threshold controls whether a move can mark a portfolio immediately.

### Verification

- The complete active suite passes: **43 passed**.
- A two-worker regression produces a three-point SPY-only curve and a four-point AAPL/SPY curve, preserving and validating each timeline independently.
- Replays of the actual cached TXN, ADBE, INTU, INTC, KMI, and KTOS transient sequences classify the isolated excursion as `PENDING_REGIME` and the return as `REVERSION`, so those excursion prices cannot supply marks or executions.
- The actual PINS sequence remains causal: 37.54 and the first 40.00 are pending, the second 40.00 confirms the earnings regime, and 40.95 confirms the subsequent level after 41.10. Its genuine repricing remains visible and receives exact attribution.
- Python syntax compilation and `git diff --check` pass.

Processed cache keys include the cleaning policy and version, so `prepared-bars-v2` does not reuse version-1 finalized data. Raw Parquet and historical run directories remain unchanged. All ALL_RUNS outputs must be regenerated to obtain corrected calendars, curves, trades, quality summaries, and attribution artifacts.

## 2026-10-23: initial causal cleaning implementation

Date: 2026-10-23. This change builds on the existing Copilot registry and split-timing patch. Existing raw Parquet prices, run results, and finalized Step 1 files were not deleted. No download or full training job was submitted during implementation.

## Code structure

| File | Change |
|---|---|
| `backtest/data_cleaning.py` | New preprocessing module: validated policy, per-boundary split normalization, causal bar checks, session eligibility, indexed slices, and prepared accounting events. |
| `backtest/market_events.py` | New small executor for prepared gap/distribution events. Holds portfolio-dependent behavior separately from cleaning. |
| `backtest/data_loader.py` | Uses the preprocessing modules; removes the end-of-run stale prefilter and the old next-bar outlier classifier. Bounds queued raw-symbol loads. Supports offline cache inspection and explicit dependency expansion. Requests raw provider prices explicitly. |
| `backtest/finalized_data_cache.py` | Version 5. Keys include cleaning settings, registry/policy, raw-cache location, and each required raw file's size/modification time. Includes child securities and SPY. Refresh explicitly bypasses a processed cache hit. |
| `backtest/portfolio.py` | Rejects nonfinite/invalid executions; unpriced holdings raise an explicit error instead of disappearing from equity. Protective/final sales carry a reason. |
| `run_simulation.py` | Reuses prepared data for training/validation/test; keeps auxiliary pricing securities separate from the trading universe; executes prepared events; cancels affected deferred orders; stops fabricating missing observations. Aligns benchmark inputs with actual stock observations. Final liquidation uses the latest accepted mark. Event-only timestamps receive aligned equity snapshots without advancing deferred-order bars. |
| `scripts/train_trainable_penguins.py` | Prepared context now returns the data mapping as its fifth result. Both callers reuse it; standalone training no longer reloads data for each candidate. |
| `penguins/decision_utils.py` | Relative strength handles a missing time-aligned benchmark endpoint using its existing stock-return fallback. |
| `scripts/data_fixes/corporate_actions.py` | Distribution ex-price boundaries use aware trading-session timestamps, with an explicit override available. Validates ratios and respects the disable flag consistently. Retains the existing split registry. |
| `market_data/cache.py` | A fetched revision replaces its timestamp; unresolved duplicate conflicts elsewhere are preserved for quarantine rather than silently selecting a historical value. |
| `partial_scripts/review_datacache.py` | Streams one security at a time, includes distribution dependencies, and writes accepted/invalid/outlier/eligibility coverage to Markdown. Explicit inspect/fill/refresh modes. |
| `../slurm_scripts/partial_scripts_run/view_datacache.sh` | Uses Python from the loaded module instead of a nonexistent venv executable; exposes review mode, writes `.md`, and requests 32 GiB instead of 300 GB for the streaming review. |
| `tests/test_data_cleaning.py` | Regression coverage for validation, causality, mixed split states, adjusted entitlements and basis, missing-child protection, eligibility, gaps, execution, raw requests, metadata/cache persistence, and aligned benchmark inputs. |

## Data contract

1. Raw Parquet remains the source. Cleaning creates a processed dataset rather than overwriting source prices.
2. `SymbolBars` contains chronological bar rows, a timestamp index, split-basis metadata, a small event tuple, and summary counts. Prepared bars are read-only by convention; execution tests verify that simulations do not mutate their rows.
3. Slices share bar dictionaries and preserve event/basis metadata. They use a timestamp index and binary search. Processed cache pickle round-trips preserve the metadata.
4. Invalid/outlier rows remain visible to inspection, with a reason, but cannot supply execution prices or strategy history. Zero-volume observations can supply a mark but cannot supply an executable quote or reset real-quote freshness.
5. Valid but sparse observations can still value existing holdings; they do not permit new model decisions/orders. Distribution-only dependencies are not added to the model's trading universe.

## Rules and defaults

| Rule | Default / setting |
|---|---|
| General unexplained jump | 8%, `DATA_CONSISTENCY_MAX_JUMP_PCT` |
| Thin-bar jump | 3%, `DATA_THIN_MAX_JUMP_PCT` |
| Thin-bar dollar volume | Below 100,000, `DATA_THIN_DOLLAR_VOLUME` |
| Session coverage | At least 80%, `DATA_MIN_SESSION_COVERAGE` |
| Coverage history | Up to 20 completed sessions, `DATA_COVERAGE_SESSIONS` |
| Initial eligibility | At least 5 completed sessions, `DATA_MIN_SESSIONS` |
| Permanent jump quarantine | Off; optional `DATA_CONSISTENCY_QUARANTINE_AFTER_JUMP` |
| Long-gap protection | Strictly greater than 72 calendar hours since the last accepted positive-volume quote |

OHLC prices must be finite and positive, high/low must contain open and close, and volume must be finite and nonnegative. Conflicting duplicate timestamps are rejected. A return to the accepted price level can reenter immediately; a stable new level can reenter after one rejected observation. No next-bar price is consulted to decide the current bar's quality. A known distribution boundary is handled separately from an unexplained price jump.

Coverage uses accepted regular-session SPY observations, including the observed holiday/short-session pattern. Each day's eligibility uses completed prior sessions, starting at the security's first observed date. This removes the former end-of-run selection bias. It is an observed-reference coverage measure, not an exchange calendar or independent proof that every source minute is present.

Split correction is chosen independently at each bracketed registry boundary, so mixed raw/already-adjusted boundaries do not force one choice for the entire symbol. Price multipliers have inverse volume multipliers. Runtime must not split normalized holdings a second time. Events without observations on both sides are not inferred from a distant price level.

Distribution entitlements convert parent adjusted units to event-date original units, apply the legal ratio, and convert to the child's pricing basis. Parent/child book cost is allocated by their observed relative market values, preserving total book cost; this is a backtest allocation, not tax reporting. If a child cannot be marked at the event, the existing parent holding is conservatively closed at its last accepted pre-event price with a recorded protection reason. It is never silently valued as zero. Legal payment dates remain separate from the ex-distribution trading-price boundary.

Gap protection is precomputed during loading. Simulation executes a sale just beyond the 72-hour boundary at the last accepted price, clears stale history, and cancels pending orders. This implements the requested synthetic backtest exit; it is not a claim that a market fill was available during a halt or closure. Shorter gaps and accepted reentries remain allowed.

## Cost controls

- Price checks and coverage preparation run during loading, not on each optimization trial.
- Work is linear in bars apart from timestamp sorting and a few corporate-action lookups.
- Raw fetch concurrency is bounded by `DATA_LOADER_MAX_WORKERS` (default 1); completed futures no longer retain every symbol's raw dictionary.
- Reports use aggregate counts rather than retaining a message for every rejected bar.
- Execution processes a small prepared event schedule; it does not rescan history for anomalies.
- Stock/SPY alignment adds bounded rolling deques, not per-decision historical joins.
- Wider training/validation mappings are released before test-worker creation.
- Cache invalidation stats files; it does not hash entire multi-gigabyte Parquet files.
- Review holds one symbol at a time and computes the SPY session reference once.

## Verification

- Active regression suite: **31 passed**. Whitespace validation and shell syntax checks pass. Tests ran offline with Python 3.13 and the installed pytest package; no package installation was needed.
- Existing cached windows checked: SSO 2022-01-13; BLUE 2024-12-13; LCID 2025-09-02; SSO 2025-11-20; NOW 2025-12-18. Each identifies its registered split boundary and normalized basis.
- Actual GREE/SPY window 2026-05-11 through 2026-06-08: GREE has 2,898 observations, 43 rejected outliers, and **0 eligible sessions out of 20** under default coverage settings. SPY has 7,800 accepted regular-session bars in that window.
- A synthetic 100,000-bar preprocessing check took approximately **0.72 seconds** on this host. This excludes downloading and cache serialization and is not a full-run runtime guarantee. Peak process RSS for that verification script, including imports and earlier cached-window checks, was about 465 MiB.
- Cache viewer inspect-mode smoke test passed for GREE, NOW, and SPY with network calls forbidden.
- Detailed temporary evidence: `/tmp/penguin_cleaning_verification/results.json` and `viewer_smoke.md`.
- Full ALL_Year retraining and a complete universe download were deliberately left for the user's rerun.

## Review and rebuild procedure

From the workspace parent directory:

```bash
# Inspect existing raw cache without downloading.
sbatch slurm_scripts/partial_scripts_run/view_datacache.sh

# Fetch missing securities and outer date ranges, then review again.
REVIEW_MODE=fill sbatch slurm_scripts/partial_scripts_run/view_datacache.sh

# Only when a full source refresh / interior-gap investigation is intended.
REVIEW_MODE=refresh sbatch slurm_scripts/partial_scripts_run/view_datacache.sh
```

The script's symbol list, timeframe and dates remain configurable at its top. Inspect the generated Markdown in `slurm_scripts/logs`. Fill mode does not infer every interior hole from file bounds; refresh mode explicitly requests the whole range. Genuine listing boundaries and no-trade intervals must not be filled with invented bars.

After reviewing/filling data, remove only the configured finalized Step 1 directory if a manual reset is desired (`PENGUIN_FINALIZED_CACHE_DIR`, otherwise `Penguin-Capitalist/data_cache/finalized_step1`). Keep raw Parquet. Version 5 also bypasses old processed entries automatically. Rerun the existing full-run script to regenerate training, validation, tests and reports. Old run logs are not changed retroactively.
