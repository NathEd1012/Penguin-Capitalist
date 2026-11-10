# What changed in data cleaning

Data is now cleaned once during loading. Training, validation and testing reuse slices of the same prepared dataset.

Missing-bar policy (including `1m` data): **no OHLCV field is forward-filled, and no replacement bar is generated**.

| Field | Treatment when a symbol has no bar at a timestamp |
|---|---|
| `open`, `high`, `low` | Remain absent; previous candle values are not copied. |
| `close` | Remains absent from market data and indicator history. Only portfolio valuation carries the last accepted close, retaining its original mark timestamp. |
| `volume` | Remains absent; it is neither forward-filled nor replaced with zero. An explicit provider row with `volume=0` retains that value but supplies no new mark, indicator observation or execution quote. |

A carried valuation is not a generated OHLCV bar and supplies neither a strategy signal nor an execution quote. Strategy buys/sells, deferred orders and final liquidation require a current accepted, positive-volume, in-session bar for the traded symbol, plus the applicable eligibility and coverage checks. A bar for another symbol at the same timestamp does not make the missing symbol tradable. The separate unpriced-distribution protection described below can sell a parent at its last accepted pre-event mark as a corporate-action fallback; missing minutes alone never trigger that fallback.

For example, if a symbol has observations at 09:30 and 09:32 ET but none at 09:31, no 09:31 candle or volume is inserted. At a 09:31 portfolio snapshot supplied by another symbol's timestamp, the holding keeps its 09:30 mark and is identified as stale. Its indicators next advance on the accepted 09:32 observation.

A missing one-minute bar may mean no trades occurred, or it may reflect unavailable data; the backtest does not infer the cause or label it a confirmed feed outage. Within the configured trading session it still counts as an absent observation for coverage checks, so legitimate inactivity can restrict trading. Scheduled closures are excluded from expected-bar counts. Cache-viewer `fill` mode downloads available provider observations; it does not manufacture bars for absent minutes.

- Invalid prices, impossible OHLC ranges, negative/nonfinite volume and conflicting duplicates are rejected.
- Split corrections handle each event independently and keep prices, volumes and distribution share units consistent.
- Sparse symbols are blocked using prior trading-session coverage. GREE fails the examined coverage window.
- Suspicious moves above 2% are checked causally (1% for thin bars). By default, confirmation requires at least two positive-volume observations within 5% of the first candidate close and at least $100,000 of combined dollar volume. Only the observation meeting both requirements becomes accepted; earlier flagged bars remain rejected. A return to the prior accepted level reenters immediately. Pending, confirmed and reverted observations are counted separately.
- Missing quotes keep holdings open. Carried valuations retain the last accepted observation's timestamp and expose `mark_is_stale` and `mark_age_seconds`; elapsed calendar time never manufactures a sale. A carried mark may simply reflect a scheduled market closure.
- RSI, moving averages and other indicators keep their accepted-observation history across gaps. Missing, rejected and zero-volume bars add no synthetic flat prices, advance no indicator window, and supply no execution quote. The next accepted positive-volume bar includes the price change across the gap. A 14-period indicator uses 14 observed periods, which may span more than 14 clock minutes.
- Strategy trades require at least **50% of the expected bars in every indicator window**. Exactly half passes this check; normal full-history warmup and other eligibility checks still apply. Actual parameter periods and fixed trend windows are checked individually, rather than using the largest history buffer. Relative-performance strategies also require half coverage in the corresponding SPY window.
- A historical XNYS exchange calendar excludes weekends, holidays, exceptional full-day closures and scheduled early closes from missing-bar counts, including daylight-saving changes. `DATA_TRADING_SESSION=extended` (default) matches 04:00–20:00 ET cached data, with a 17:00 late close on half-days. Set `regular` for core-session-only signals. Observations outside the configured session are excluded from marks, indicators and executions. Daily bars use UTC session-date labels.
- Decisions and delayed executions both enforce window coverage. Below half, buys and sells are blocked while existing positions and histories remain intact. Final liquidation also respects coverage. SP500/SP500x2 have no indicator windows; their execution still requires a current quote within the configured session.
- Spin-off securities are included for pricing. Missing child prices cause a protective parent exit instead of disappearing from portfolio value.
- Stock/SPY inputs use matching observation times. Final liquidation requires a tradable quote at the final timestamp and uses its bid. Other holdings remain open and are included in final equity at their marked value, with stale marks identified explicitly.
- Processed-cache keys now include cleaning settings, corporate actions and raw-file revisions.
- Every strategy curve now carries its own UTC timestamp array. Trade logs use actual execution timestamps, and plotting raises on misalignment instead of silently truncating a curve.
- Moves of at least 1% are written to `artifacts/json/equity_jump_attribution.json` with cash and per-position contributions, mark status and mark age. `curve_timestamps.json` provides the matching calendar for each curve in `curves_data.json`.
- `artifacts/json/valuation_marks.json` exports final open holdings with their mark timestamp, age, status and stale flag. `trades_log.txt` lists these holdings separately from actual sales; `metrics_summary.json` includes `stale_position_count`.
- Metrics and the trade log include `coverage_blocked_decisions` and `coverage_blocked_orders`. The run banner records the session and 50% minimum. Training, validation and test runs use the same gate.

Price-jump confirmation uses these configurable defaults:

| Requirement | Default | Environment setting |
|---|---|---|
| Price consistency | Within 5% of the first candidate close: `abs(close / candidate_close - 1) <= 0.05` | `DATA_CONFIRMATION_TOLERANCE_PCT=0.05` |
| Supporting observations | At least 2 positive-volume observations, including the initially flagged candidate | `DATA_CONFIRMATION_BARS=2` |
| Combined trading value | At least $100,000, calculated as the sum of `close * volume` across the candidate observations | `DATA_CONFIRMATION_DOLLAR_VOLUME=100000` |

The candidate close stays anchored to the first suspicious observation, rather than moving with each supporting observation. A subsequent suspicious close outside its tolerance starts a new candidate and resets the accumulated count and dollar volume. If two supporting observations do not supply $100,000, further coherent observations are required.

There is **no maximum candidate bar count and no separate timeout measured from the first candidate**. Coherent observations keep accumulating until confirmation or one of these resets:

| Event | Effect on pending confirmation |
|---|---|
| A new suspicious close falls outside the candidate's 5% tolerance | Discard the old candidate's count and dollar volume; start again using this new close and its volume. |
| Price returns within the applicable jump threshold of the last accepted close | Cancel the candidate and accept the returning observation, subject to the normal validity and positive-volume requirements. |
| Trading session ends or the date changes | No reset. A pending candidate can carry overnight into another session. The quality-preparation pass itself does not filter by configured trading hours, so available extended-hours rows can also contribute. |
| More than 72 calendar hours have elapsed since the last accepted positive-volume observation | Clear the candidate and stop comparing against the old accepted close. The next otherwise valid positive-volume observation becomes a new accepted baseline **without requiring the $100,000 confirmation**. This age is measured from the last accepted observation, not the candidate or the last incoming bar; it can expire even while pending bars continue to arrive. |
| A known distribution boundary is crossed since the last accepted observation | Clear the candidate and bypass the old-price comparison at that boundary. |

The reference-age boundary is implemented as 72 hours plus one microsecond (`REFERENCE_MAX_AGE`). Invalid rows do not contribute or clear a candidate, and missing timestamps supply no observation; elapsed time is checked when the next structurally valid row is processed. These recovery rules assume permanent quarantine is disabled, as it is by default. None of them retrospectively validates earlier rejected bars or bypasses the separate trading-eligibility checks.

For example, after an accepted $100 close, a $115 bar with 500 shares is `OUTLIER` / `PENDING_REGIME`. A subsequent $114.80 bar with 500 shares differs from the candidate by about 0.174% and brings combined dollar volume to $114,900. That subsequent bar becomes `OK` / `CONFIRMED_REGIME`. The original $115 bar remains rejected: it supports confirmation but is never retrospectively inserted into marks, indicators or executions. This example assumes the default disabled permanent-quarantine option; acceptance by the price-quality filter still leaves session, coverage and trading-eligibility checks in force.

Cleaning and review remain bounded in memory; expensive checks are not repeated for each training candidate. The cache viewer now supports `inspect` (default), `fill` and explicit full `refresh` modes.

Next: run the cache viewer, use fill mode for missing securities/ranges, inspect its Markdown report, then rerun the ALL_RUNS jobs. Keep the raw Parquet cache. Existing run results remain unchanged and retain their incorrect shared plot calendar until regenerated; versioned finalized data is rebuilt automatically.

These checks reduce faulty-data trading; they do not independently verify every market print or resolve every security-identity ambiguity. Sparse-coverage and thin-bar thresholds are configurable and intentionally conservative.
