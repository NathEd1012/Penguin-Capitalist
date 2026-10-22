# ALL_Year portfolio-jump audit

Audit date: 2026-10-22. Production simulation code and existing results were not changed.

The remaining jumps have several causes. There are confirmed corporate-action accounting gaps, a validator that delays large price changes instead of resolving them, and concentrated positions in thinly traded stocks. Some large moves coincide with real company announcements and should remain in the P&L of a portfolio that already holds those shares.

## Scope and confidence

- Inspected the five top-level `run_log/ALL_Year*` groups, including `ALL_Year1_gpucb`: **30 run directories**, **19 with saved curves**, **171 strategy curves**, **60,634,800 adjacent-value comparisons**.
- A candidate is an absolute change of **at least 3% between adjacent saved portfolio values**. This is a screening threshold, not a definition of bad data. Smaller visual jumps are outside this ledger.
- Found **871 portfolio/strategy events at 527 distinct UTC timestamps**. The same market event can affect several strategies/runs.
- Reconstructed pre-event positions from execution logs, selected the price basis using the loader's current rule, and attributed each delta to holdings, trades, and the logged $1 execution fee. **All 871 reconcile within the precision of the saved two-decimal trade prices**. Of these, 727 reconcile within $0.03; the remaining differences fit the share-count-dependent rounding bound.
- Recovered 660 event timestamps directly from trade-log anchors and 211 from adjacent anchors whose elapsed minutes exactly match their bar-index difference. There were no unresolved event timestamps.
- The 11 directories without `curves_data.json` are listed in [runs.csv](runs.csv); they cannot be included in a saved-equity audit. This does not infer whether each job failed or is unfinished. Archived `8Failures/ALL_Years*` and other groups are outside this audit.
- `MR_2020` is the training-start label; its execution window is January 2021–June 2022. `MR_2024` executes January 2025–June 2026.
- The attribution uses the **current local cache/code**, rather than a versioned market-data snapshot from each run. The reconciliation is strong evidence that these cached prices explain the saved jumps. It does not independently verify every exchange print.

A supplementary boundary check also finds **4 LCID portfolios and 17 GE portfolios exposed**, including effects below the 3% screening threshold; see [corporate_action_exposures.csv](corporate_action_exposures.csv). These are portfolio instances across runs, not independent securities.

Artifacts: [complete jump ledger](jumps.csv), [run inventory](runs.csv), [summary counts](summary.json), [full attribution and price context](attribution.json), [diagnostic figure](jump_examples.png), [figure PDF](jump_examples.pdf).

## Categories

These are mutually exclusive screening categories assigned from the largest dollar contributor. They describe observed mechanisms; only the explicitly identified corporate-action cases are confirmed accounting errors. Reentry can also occur during genuine market news, so it is not a count of false profits.

| Category | Events | Meaning | Recommended response |
|---|---:|---|---|
| Missing split | 1 | LCID's raw reverse-split boundary is treated as a gain | Restore the factual event, use its trading boundary, and reconcile price/share bases |
| Unmodeled spin-off | 3 | GE falls on the GEHC distribution while no child shares are credited | Model distribution entitlements and mark the distributed asset |
| Reentry after rejected bars | 204 | The dominant holding's mark crosses one or more rejected raw observations | Track the last accepted reference and explicitly resolve/rebase a dislocation |
| Transient reversal candidate | 56 | An accepted >=3% stock move reverses to within 1% of the prior price on the next observed bar, within 10 minutes | Check independent prices and liquidity; use robust, causal quality rules |
| Sparse/session repricing | 340 | No intervening rejected bar, but at least five minutes between the dominant holding's valid observations | Distinguish stale marks, session gaps, and current executable prices |
| Other accepted movements | 267 | Remaining accepted stock moves; underlying cause not individually verified | Preserve legitimate P&L; investigate execution realism and concentration |

Category order is the table order: a confirmed corporate action takes precedence over the general filter mechanism. The transient rule is a research screen using the next observation, not a proposed causal execution rule.

**671/871 events (77.0%) occur outside 09:30–16:00 America/New_York**, accounting for daylight saving time. GREE is the largest contributor to **320/871 (36.7%)**, followed by VERI (53), BLUE (46), SOUN (40), and BBAI (34). These concentrations are a useful order for further independent price validation.

## Concrete findings

### 1. Confirmed artificial gain: LCID reverse split

- Run: `ALL_Year1_gpucb/MR_2024_broad_gpucb_500`, `KingPenguin_040`.
- Timestamp: **2025-09-02 13:01 UTC**, saved bar **158588**.
- Portfolio jump: **+$14,964.61 / +14.76%**. LCID contributes **+$14,937.55**.
- The portfolio holds **895 LCID shares**. The previous accepted price is **$1.99**; the new accepted price is **$18.68**. The first post-split $19.00 bar at 13:00 is rejected; the following bar is accepted.
- The 1-for-10 event is commented out at [`list_of_corp_act.py:496`](../../../scripts/data_fixes/list_of_corp_act.py#L496), with a comment claiming the cache is adjusted. The cache demonstrably retains the price boundary.
- Lucid announced an effective time after market close on August 29, with **split-adjusted trading beginning September 2, 2025**. [Lucid announcement](https://ir.lucidmotors.com/news-releases/news-release-details/lucid-group-inc-announces-effective-date-reverse-stock-split).

At the new price, **89.5 shares**, rather than 895, would be held under raw-price accounting before any broker-specific fractional-share settlement. That changes the LCID component at this transition from +$14,937.55 to **−$109.19**. The overstatement in the post-event LCID holding is **$15,046.74**. This is a local accounting illustration; subsequent strategy decisions would also change, so it is not a corrected final backtest return.

**Solution:** retain the factual corporate-action registry independently of how a particular cache is adjusted. Store/verify adjustment state per event and data series, using September 2 as the price-scale boundary. Use either consistent adjusted prices and constant synthetic units, or raw prices plus inverse share adjustment. Handle cost basis, fallback prices, pending quantities, fractional shares, and indicator state consistently. A comment or filename cannot substitute for an observed boundary check.

The existing loader chooses between raw and adjusted prices once for the entire symbol/load window (`backtest/data_loader.py:179`); this should eventually become a per-event decision for mixed-basis histories. Simply uncommenting an August 29 midnight adjustment can introduce a premature adjustment while that day's prices still use the old scale.

### 2. Confirmed missing asset: GE HealthCare spin-off

- Timestamp: **2023-01-04 09:02 UTC**, bar **235797** in the MR_2021 runs.
- Three >=3% portfolio moves: GPUCB `KingPenguin_147` **−4.04%**, TPE `KingPenguin` **−3.70%**, TPE `KingPenguin_314` **−3.43%**.
- GE's mark falls **$84.87 → $67.99**. The strategies hold 86, 101, and 82 GE shares, respectively.
- The event is present in `REORGANIZATIONS`, but `get_price_adjustment_events()` returns only splits/reverse splits. `Portfolio.apply_price_adjustments()` only changes quantities and cost basis; it never creates a distributed child position.
- GE distributed **one GEHC share per three GE shares**. [GE's SEC filing](https://www.sec.gov/Archives/edgar/data/40545/000119312523001157/d431727d8k.htm).

**Solution:** record the distribution entitlement and credit/mark GEHC, even if GEHC is outside the strategy's selected trading universe. Define how the child position is retained or liquidated. If implementing the event is not yet possible, flag that backtest as economically incomplete. A no-trade gate cannot repair a missing asset on the balance sheet. The same event engine should later cover cash mergers, share exchanges, ticker identity, and ordinary distributions; their registration alone does not account for them.

### 3. Confirmed validator defect: rejected bars become the next comparison baseline

In [`backtest/data_loader.py:342`](../../../backtest/data_loader.py#L342), the next price is compared with the previous **raw** row. Even after rejecting a row, the code advances `previous_timestamp` to that row (`:461`). Meanwhile, valuation keeps the last accepted price. The two references diverge.

Minimal reproduction using the actual `_annotate_data_quality()` method:

```text
Raw closes:             100, 100, 150, 151
Strategy/valuation OK:        100,      151
Rejected:                         150
Reported unresolved events: []
```

The +50% price change has been delayed by one bar. It is neither repaired nor persistently quarantined. `_finish_unresolved_event()` only reports unresolved events with more than one affected bar (`:285`), so this example also disappears from the warning summary.

Observed examples:

| Run / strategy | UTC timestamp | Portfolio jump | Dominant price transition |
|---|---|---:|---|
| random / MR_2020 / Rockhopper | 2022-05-02 09:30 | **+85.20%, +$81,553.88** | 9,236 SOUN shares, $8.17 → $17.00 after four rejected bars |
| cmaes / MR_2021 / Gentoo | 2022-05-02 09:30 | **+34.58%, +$30,179.93** | 3,418 SOUN shares over the same boundary |
| random / MR_2022 / Gentoo | 2023-01-12 13:01 | **+51.39%, +$56,180.89** | 70,224 BBAI shares, $0.85 → $1.65 after one rejected bar |
| random / MR_2022 / Gentoo | 2023-01-12 13:05 | **+33.13%, +$54,774.82** | BBAI $1.65 → $2.43 after three rejected bars |
| tpe / MR_2020 / Rockhopper | 2021-03-01 09:01 | **+24.56%, +$25,963.10** | RKLB/predecessor $10.25 → $16.77 after one rejected bar |

For SOUN, the rejected closes are $9.10, $11.68, $14.00, $17.14; the next close, $17.00, differs little from the last rejected raw close, so it passes. The whole holding then jumps from its stale $8.17 mark.

**Solution:** maintain separate last-observed and last-accepted references, and an explicit dislocation state. A series should recover through a defined path: verified corporate action, correction/reversion, or confirmed new market level. Record the full event, including single rejected bars and the eventual repricing. Keep **execution eligibility** separate from **valuation quality**. For a verified real gap, advance the economic mark at the correct time even if fresh trading is temporarily blocked. For unverified data, preserve an explicit stale/uncertain mark until resolution.

`DATA_CONSISTENCY_QUARANTINE_AFTER_JUMP=1` currently removes the rest of a symbol's series after an unresolved jump. This can freeze a held position and prevent its exit, so it is not a complete fix.

### 4. Sub-threshold reversals and thin prints

Example: `ALL_Year1_gpucb/MR_2024_broad_gpucb_500`, `GentooPenguin_250`, **2025-05-09 13:37 UTC**, bar **83920**:

```text
GREE closes:   $0.900 → $0.969 → $0.901
Stock moves:             +7.67%    −7.02%
Portfolio:               +6.06%    −5.63%
```

Both prices pass the global 8% rule. The strategy holds **97,650 shares**, about **79% of equity** immediately beforehand. The upward-print minute has **5,006 shares** of volume. This is a suspicious round trip, not independently proven bad data: the entire position is being marked using a relatively small print.

Another example: at **2026-06-09 09:32 UTC**, GREE's accepted mark rises from **$1.47 to $1.6745**, after rejecting a $1.66 print. The new bar has **404 shares** of volume. Five Gentoo curves jump between **9.11% and 10.44%**. GPUCB's main Gentoo holds 57,159 shares, around 141 times that minute's volume.

**Solution:** validate suspicious prints against another feed or quotes; use volatility-, session-, and liquidity-aware thresholds. Treat rapid reversals as review candidates. Set limits on per-symbol equity exposure and on fills relative to available volume; allow partial fills and model slippage. The current execution loop checks price availability and cash/holdings but does not impose a volume participation limit. A mark is not a guarantee the whole position can be sold at that price.

The synthetic spread uses the candle range and volume but has no exchange quote/depth evidence. For single-price bars, the range component is zero, leaving a very small price-based spread. That is insufficient protection for large holdings in an illiquid symbol.

### 5. Genuine market repricing should survive cleaning

The BBAI rally coincides with its January 12, 2023 announcement of a multiple-award $900 million Air Force IDIQ contract vehicle. That is a right to compete for task orders, not $900 million of booked revenue. [BigBear.ai release](https://ir.bigbear.ai/news-events/press-releases/detail/55/bigbear-ai-secures-10-year-multiple-award-900-million-idiq).

The RKLB/predecessor move coincides with the March 1, 2021 merger announcement. [Contemporaneous SEC filing](https://www.sec.gov/Archives/edgar/data/1819994/000121390021012373/ea136708-8k_vectoracq.htm). SOFI's January 7, 2021 move also coincides with its merger announcement. [SoFi release](https://investors.sofi.com/news/news-details/2021/-SoFi-A-Leading-Next-Generation-Financial-Services-Platform-Announces-Plans-to-Become-Publicly-traded-via-Merger-with-Social-Capital-Hedosophia/default.aspx).

These dates support a real market catalyst; they do not independently validate every minute close or fill. In particular, the large BBAI/SOUN holding gains are not automatically artificial just because they appear as vertical lines. Blocking new trades on an outlier does not eliminate the P&L of shares already owned.

**Solution:** preserve genuine repricing, correct its timing, and control concentration/execution assumptions if these moves are unsuitable for the intended strategy. If extended-hours trading is outside the intended strategy, use an exchange calendar with America/New_York session times for both trading rules and reporting. Still recognize overnight risks at the next valid market mark. Do not interpolate, clip, or delete real held-position losses/gains simply to smooth the curve.

## Recommended implementation order

1. **Corporate-action correctness:** fix LCID's observed boundary and add spin-off entitlements, beginning with GE/GEHC. Verify wealth conservation through a split with missing post-event bars, and through a distribution when the child is outside the selected universe.
2. **Validator and audit trail:** separate observed/accepted references and explicit recovery. Log every rejected bar, the mark used, its age, and the resolution. Verify persistent steps, isolated spikes, multi-bar spikes, real gaps, and recovery. The current next-bar outlier check uses future data; keep offline data repair clearly separate from a causal simulation decision rule.
3. **Liquidity and position sizing:** investigate GREE first, then VERI/BLUE/SOUN/BBAI. Add per-symbol equity caps and volume-aware partial execution. Keep risk limits and data-quality classification distinct.
4. **Cache invalidation:** bump `CACHE_VERSION` and include the corporate-action registry/adjustment-policy fingerprint, jump threshold, quarantine mode, and relevant data-source provenance in the finalized cache key. The current key does not include the threshold, quarantine mode, or registry contents. Otherwise a corrected run may reuse old annotations.
5. **Replay and reassess optimization:** rerun representative saved parameter sets first. Then repeat affected training/validation as well as execution; their selection objectives can also have been influenced by these prices. No corrected final returns are claimed in this audit.
6. **Persist timestamped accounting evidence:** export timestamps with curve values and, for large deltas, per-symbol quantities, prices, stale ages, adjustment events, fees, and realized/unrealized contributions. The present curve JSON contains values only, making historical attribution depend on trade-log anchors.

Additional code-review risks, not identified as the cause of these 871 events: share adjustments do not rescale `last_known_prices` at the same time, so raw-price fallback valuation around a split deserves a focused check; and applying split factors to OHLC without the inverse adjustment to volume can put liquidity inputs on inconsistent units.

## Reproduction

Run from the repository using its Python module with NumPy, pandas, PyArrow, pytz, and matplotlib installed:

```bash
module load devel/python/3.13.1
python3 partial_scripts/audit_run_jumps.py
python3 partial_scripts/audit_run_jumps.py --attribute
python3 partial_scripts/audit_run_jumps.py --summarize
python3 partial_scripts/audit_run_jumps.py --plot
python3 partial_scripts/audit_run_jumps.py --corporate-exposures
```

The script reads local artifacts/cache and writes only this audit directory. The current attribution is specific to these saved one-minute ALL_Year runs, their 8% quality rule, and their $1 execution fee. The category examples for LCID and GE are explicit reviewed cases, not a generic corporate-action discovery algorithm. No network credentials or API fetching are used by the audit script.
