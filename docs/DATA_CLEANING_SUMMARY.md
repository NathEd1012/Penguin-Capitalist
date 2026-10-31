# What changed in data cleaning

Data is now cleaned once during loading. Training, validation and testing reuse slices of the same prepared dataset.

- Invalid prices, impossible OHLC ranges, negative/nonfinite volume and conflicting duplicates are rejected.
- Split corrections handle each event independently and keep prices, volumes and distribution share units consistent.
- Sparse symbols are blocked using prior trading-session coverage. GREE fails the examined coverage window.
- Suspicious moves above 2% are checked causally. A new regime requires two coherent positive-volume observations and sufficient combined dollar volume; a return to the prior accepted level reenters immediately. Pending, confirmed and reverted observations are counted separately.
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

Cleaning and review remain bounded in memory; expensive checks are not repeated for each training candidate. The cache viewer now supports `inspect` (default), `fill` and explicit full `refresh` modes.

Next: run the cache viewer, use fill mode for missing securities/ranges, inspect its Markdown report, then rerun the ALL_RUNS jobs. Keep the raw Parquet cache. Existing run results remain unchanged and retain their incorrect shared plot calendar until regenerated; versioned finalized data is rebuilt automatically.

These checks reduce faulty-data trading; they do not independently verify every market print or resolve every security-identity ambiguity. Sparse-coverage and thin-bar thresholds are configurable and intentionally conservative.
