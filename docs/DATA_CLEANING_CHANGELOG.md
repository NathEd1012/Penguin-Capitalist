# Data cleaning implementation log

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
