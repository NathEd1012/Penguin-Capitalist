# What changed in data cleaning

Data is now cleaned once during loading. Training, validation and testing reuse slices of the same prepared dataset.

- Invalid prices, impossible OHLC ranges, negative/nonfinite volume and conflicting duplicates are rejected.
- Split corrections handle each event independently and keep prices, volumes and distribution share units consistent.
- Sparse symbols are blocked using prior trading-session coverage. GREE fails the examined coverage window.
- Suspicious jumps are checked causally. Reentry remains possible; missing bars do not create fake prices or volume.
- Gaps greater than 72 calendar hours close holdings at the last accepted price and reset old history.
- Spin-off securities are included for pricing. Missing child prices cause a protective parent exit instead of disappearing from portfolio value.
- Stock/SPY inputs use matching observation times. Final liquidation uses the latest accepted price rather than a ten-bar average.
- Processed-cache keys now include cleaning settings, corporate actions and raw-file revisions.

Cleaning and review remain bounded in memory; expensive checks are not repeated for each training candidate. The cache viewer now supports `inspect` (default), `fill` and explicit full `refresh` modes.

Next: run the cache viewer, use fill mode for missing securities/ranges, inspect its Markdown report, then clear only finalized Step 1 data if desired and rerun. Keep the raw Parquet cache. Existing run results remain unchanged.

These checks reduce faulty-data trading; they do not independently verify every market print or resolve every security-identity ambiguity. Sparse-coverage and thin-bar thresholds are configurable and intentionally conservative.
