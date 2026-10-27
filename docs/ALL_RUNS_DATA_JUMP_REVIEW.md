# ALL_RUNS data-jump review

Reviewed on 2026-10-26. Scope: `run_log/ALL_RUNS_TS100`, `ALL_RUNS_TS500`, and `ALL_RUNS_TS1000`.

Residual suspicious price spikes reach the saved portfolio curves. Several isolated cached prices pass the cleaner and produce exactly matching portfolio changes. Some large sustained jumps coincide with company announcements and should not automatically be removed. Separately, the parallel-results export combines different timestamp grids, misdating trades and truncating plotted strategy curves.

## Coverage and screening counts

All 75 `log.out` files and their 75 `consistency_warnings.txt` reports were examined. All 70 available final `curves_data.json` files were scanned: 490 curves including benchmarks.

| Folder | Logs | Completed final results | Adjacent portfolio changes >=3% | Adjacent portfolio changes >=5% |
| --- | ---: | ---: | ---: | ---: |
| ALL_RUNS_TS100 | 25 | 24 | 457 | 87 |
| ALL_RUNS_TS500 | 25 | 22 | 595 | 104 |
| ALL_RUNS_TS1000 | 25 | 24 | 759 | 129 |
| Total | 75 | 70 | 1,811 | 320 |

These screening counts include gains and losses, overnight and news moves, and the same event repeated across strategies and runs. They are not counts of confirmed erroneous bars. No nonfinite portfolio values were found.

An additional screen of TS1000 found **135 strategy-curve occurrences** where a change of at least 2% returned within 0.3% of the pre-jump portfolio value on the next snapshot. These are candidates for investigation, not 135 independent confirmed bad ticks.

## Suspicious price spikes that reach the portfolio curves

The following cached close sequences reverse almost entirely on the next observation. Replaying the current cleaner marks all three observations in each sequence `OK`. The portfolio change matches the held quantity multiplied by the price change, to the cent.

Times below are **UTC timestamps from cached source bars**, rather than the incorrect calendar labels in the trade exports. Curve indices are zero based. Run paths are relative to `run_log/ALL_RUNS_TS1000`.

| Symbol / source timestamp | Cached close sequence | Run | Strategy / curve index | Portfolio sequence |
| --- | --- | --- | --- | --- |
| TXN / 2022-04-26 20:15 | 157.18 -> 168.44 -> 157.80 | Year2021/gpei/MR_2021_broad_gpei_1000 | EmperorPenguin_085 / 74130 | 72,169.58 -> 76,043.02 -> 72,382.86 |
| ADBE / 2023-12-13 23:07 | 590.70 -> 624.26 -> 591.00 | Year2022/random/MR_2022_broad_random_1000 | EmperorPenguin / 227266 | 60,016.89 -> 62,332.53 -> 60,037.59 |
| INTU / 2024-11-21 21:22 | 639.00 -> 678.70 -> 639.9999 | Year2023/random/MR_2023_broad_random_1000 | GentooPenguin / 217116 | 94,690.78 -> 98,422.58 -> 94,784.77 |

Attribution:

- TXN: 344 shares x 11.26 = **3,873.44**, a **5.37%** portfolio spike.
- ADBE: 69 shares x 33.56 = **2,315.64**, a **3.86%** portfolio spike. This is in the user's open Year2022/random/TS1000 run.
- INTU: 94 shares x 39.70 = **3,731.80**, a **3.94%** portfolio spike. The same cached price of 678.70 appears again at 21:33, between 647.00 and 648.99, producing another brief rise in this strategy.

These are strong suspect-print patterns. A second market-data source would be needed to establish whether each individual print is erroneous, stale, or an unusual valid execution. Their passage into portfolio marks is established by the local artifacts.

Additional TS1000 examples identified by matching cached price changes to held quantities:

- Year2024/gpei, GentooPenguin, index 97202: **81,149.13 -> 78,429.66 -> 81,149.13**. ESTC source closes at 2025-05-29 20:10 UTC are **82.00 -> 78.33 -> 82.00**. The 741-share holding explains the entire 2,719.47 dip.
- Year2024/gpei, EmperorPenguin_015, index 31220: **111,583.84 -> 115,616.08 -> 111,346.05**. U source closes at 2025-02-20 13:00 UTC are **19.57 -> 20.757 -> 19.50**. The 3,397-share holding explains the 4,032.24 rise, to rounding precision.

## Why the first three examples passed prepared-bars-v1

At the time of this review, `prepared-bars-v1` used an 8% close-to-last-accepted-price threshold, reduced to 3% when the current close multiplied by volume was below $100,000. TXN, ADBE, and INTU rise approximately 7.16%, 5.68%, and 6.21%, respectively. Their reported bar dollar volumes exceed that cutoff, so they passed despite the immediate reversals.

The rule does not screen for stale isolated prints. TXN and ADBE close at the tops of unusually wide bars; INTU has an isolated bar at the elevated price. Separately, `backtest/data_cleaning.py:170` permits a large new price level after two observations agree. This accommodates real repricing but can also admit a persistent data discontinuity.

`OUTLIER` counts in `consistency_warnings.txt` describe rejected observations, not these accepted spikes. The report is repeated under the training heading, so adding both sections double-counts it. First-section totals range from roughly 13,051 to 19,747 outliers over the full loaded training/validation/test windows. High GREE counts do not imply portfolio exposure: the reviewed GREE reports show zero eligible sessions.

## Large jumps with event context

The largest portfolio step is **+18.83%**: Year2023/gpucb, RockhopperPenguin_024, index 324574, **100,051.01 -> 118,891.66**. It appears in TS100, TS500, and TS1000.

This matches 269 APP shares and an accepted source-price change from 280.0104 to 350.05 on **2025-05-07**, approximately 25.01%. AppLovin reported earnings and a business-sale agreement that day, after the market closed. The timing is consistent with an event-driven move; the announcement alone does not independently verify the cached prices. Size alone does not establish a bad adjustment.

Sources: [AppLovin earnings announcement](https://investors.applovin.com/news/news-details/2025/AppLovin-Announces-First-Quarter-2025-Financial-Results/default.aspx), [scheduled announcement timing](https://investors.applovin.com/news/news-details/2025/AppLovin-to-Announce-First-Quarter-2025-Results/default.aspx).

The open Year2022/random/TS1000 run also has a **-13.16%** step in GentooPenguin_066 at index 349278: **133,231.09 -> 115,692.12**. Its SPCE holding and the normalized price gap around 2024-06-17 account for this move. The cached pre-boundary close normalizes to 13.912, followed by an accepted close of 11.405: an approximately 18.02% decline after normalization, rather than an uncorrected 20-fold jump. Virgin Galactic's registered 1-for-20 reverse split began adjusted trading on June 17. The residual move needs separate price-source validation.

Source: [Virgin Galactic split announcement filed with the SEC](https://www.sec.gov/Archives/edgar/data/1706946/000119312524159991/d829568dex991.htm).

## Follow-up: GentooPenguin_097 in MR_2023_broad_gpucb_500

The prominent February jump appears consistent with a genuine PINS earnings rebound, made more abrupt by the cleaner's rejection of intermediate bars. Its actual source date is **2024-02-08**; the mismatched export calendar places it near **2024-02-16**.

At curve index **25944**, portfolio equity rises from **117,238.74 to 128,623.74**, or **9.71095%**. The strategy holds **2,070 PINS shares**. Source bars and the replayed cleaning classifications are:

| Actual UTC time on February 8 | PINS close | Quality |
| --- | ---: | --- |
| 21:49 | 34.50 | OK |
| 21:50 | 37.54 | OUTLIER |
| 21:51 | 40.00 | OUTLIER |
| 21:52 | 40.00 | OK |
| 21:53 | 41.10 | OK |
| 21:54 | 40.95 | OK |

The 21:50-21:52 bars report volumes of 378,041, 466,094, and 287,815 shares. The portfolio remains marked at 34.50 during the two rejected bars, then moves directly to 40.00. **2,070 x (40.00 - 34.50) = 11,385.00**, exactly matching the portfolio step. Thus a rebound unfolding across several minutes becomes one large accepted-data step.

The execution log records buying 2,070 PINS at approximately 31.92 at bar 25900 and selling them at approximately 40.94 at bar 25946. Those match source bars at 21:08 and 21:54 UTC, respectively. The dollar prices in the text export are rounded. This is a realized modeled trade, rather than solely an unrealized mark that immediately disappears.

Pinterest confirmed earnings after the close on February 8 and a conference call at 21:30 UTC. Contemporary Reuters reporting describes an initial decline and recovery following the announcement of a Google advertising integration. This context, the multi-minute price sequence, and substantial reported volume support an event-driven interpretation. Independent minute quotes would still be needed to verify the exact execution prices and spreads.

Sources: [Pinterest's earnings timing announcement](https://investor.pinterestinc.com/news-and-events/press-releases/press-releases-details/2024/Pinterest-to-Announce-Fourth-Quarter-and-Full-Year-2023-Results/default.aspx), [Reuters report syndicated by StreetInsider](https://www.streetinsider.com/Earnings/Pinterest%2Bforecasts%2Bfirst%2Bquarter%2Brevenue%2Bbelow%2Bestimates/22743102.html).

## Follow-up: both Rockhopper curves in MR_2023_broad_gpucb_500

Scanned both full curves in `ALL_RUNS_TS500/Year2023/gpucb/MR_2023_broad_gpucb_500`. RockhopperPenguin_024 has **39 adjacent changes of at least 2%**; plain RockhopperPenguin has **six**. Counts include both legs of reversals and multiple steps during one news event. Holdings reconstructed from execution text can omit corporate-action/protection closures; exact attributions below are supported by matching portfolio dollar changes to source prices, rather than assuming every reconstructed old holding remains active.

### Suspect or ambiguous transient prices in RockhopperPenguin_024

Dates and times are from source bars, in UTC; chart dates remain shifted by the export defect.

| Source event | Curve indices | Source closes | Portfolio changes | Assessment |
| --- | --- | --- | --- | --- |
| INTC, 2024-03-20 12:04-12:05 | 52405-52406 | 43.42 -> 42.22 -> 43.44 | -2.13%, +2.21% | Isolated downward print amid alternating closes; worth checking against quotes/trade conditions. |
| U, 2024-02-27 13:02-13:05 | 37042-37045 | 27.97 -> 26.81 -> 28.00 -> 27.18 -> 28.05 | -3.15%, +3.31%, -2.22%, +3.05% | Repeated rapid oscillation the morning after earnings; ambiguous microstructure/print behavior, not enough evidence to label every leg a data error. |
| DOCU, 2024-06-06 20:07-20:08 | 104899-104900 | 54.69 -> 56.71 -> 54.54 | +2.88%, -3.05% | Earnings-hour whipsaw. Reversal alone does not establish bad data. |
| KMI, 2024-07-17 22:13-22:20 | 130767 and 130774 | 19.9013 -> 20.53 -> 19.90 | +2.37%, -2.32% | Strong stale-print pattern; 20.53 repeats an earlier regular-session/closing price after the market had moved lower. |
| KTOS, 2025-06-25 20:03-20:05 | 356351 and 356353 | 40.55 -> 42.33 -> 40.69 | +2.69%, -2.41% | Strong stale-print pattern; 42.33 repeats the 19:59 close after several lower after-hours observations. |

The current cleaner accepts the elevated/depressed observations listed above. KMI has an additional problem: its immediate return to 19.91 at 22:14 is rejected under the 3% thin-bar rule, keeping the elevated portfolio mark until 22:20, when 19.90 is accepted. The false-looking rise therefore persists for seven minutes of the shared timeline.

Exact attributions:

- INTC: 2,329 shares x (42.22 - 43.42) = **-2,794.80**; 2,329 x (43.44 - 42.22) = **+2,841.38**. Portfolio: 131,376.96 -> 128,582.16 -> 131,423.54.
- KMI: 4,600 shares x (20.53 - 19.9013) = **+2,892.02**; 4,600 x (19.90 - 20.53) = **-2,898.00**.
- KTOS: 1,813 shares x (42.33 - 40.55) = **+3,227.14**; 1,813 x (40.69 - 42.33) = **-2,973.32**.
- DOCU: 1,904 shares x (56.71 - 54.69) = **+3,846.08**. The return step includes selling the position and execution costs, so its -4,198.04 portfolio change exceeds the mark-only decline.

A large shareholding amplifies each price disturbance. The INTC/KMI/KTOS observations pass the cleaner because their price changes remain below the applicable threshold. Their treatment as representative current prices is questionable, even if some underlying trade prints were technically valid. Quote or trade-condition data is needed to establish whether they are delayed, stale, or unusual valid executions.

Intel announced CHIPS funding that morning, and KMI reported earnings that day, so news context also exists. That does not by itself validate an isolated return to an earlier price. Sources: [Intel announcement](https://www.intel.com/content/www/us/en/newsroom/news/us-chips-act-intel-direct-funding.html), [KMI earnings](https://ir.kindermorgan.com/news/news-details/2024/Kinder-Morgan-Reports-Second-Quarter-2024-Financial-Results/default.aspx), [DOCU earnings](https://www.sec.gov/Archives/edgar/data/1261333/000126133324000083/q125ex-991er.htm).

### Larger moves with plausible news context

- **Unity/U, February 26, 2024**: RockhopperPenguin_024 loses 3.46% and then 3.38% at indices 36570-36571. Its 3,177 shares explain the source-price declines **30.46 -> 29.09 -> 27.80**, at 21:10-21:11. These bars report 272,902 and 294,578 shares of volume and coincide with Unity's scheduled earnings release. This sustained decline has a stronger event-driven explanation than the next morning's alternating prices. [Unity earnings timing](https://investors.unity.com/news/news-details/2024/Unity-Announces-Fourth-Quarter-and-Fiscal-Year-2023-Financial-Results-Webcast/default.aspx).
- **Opendoor/OPEN, May 2, 2024**: RockhopperPenguin_024 gains 3.94% and then 3.33% at indices 81751-81752; plain Rockhopper gains 2.07% and 1.78%. The source closes at 20:04-20:06 are **1.93 -> 2.03 -> 2.12**. The two strategies hold 48,177 and 22,630 shares, respectively, then sell at approximately 2.12. This is an earnings-hour rebound; the first-step dollar changes exactly match the 0.10 source-price rise. [Opendoor earnings](https://investor.opendoor.com/news-releases/news-release-details/opendoor-announces-first-quarter-2024-financial-results/).
- **AppLovin/APP, May 7, 2025**: the 18.83% RockhopperPenguin_024 step is the APP earnings event described above. It is the largest step in this curve; size alone does not establish corruption.

### The six >=2% steps in plain RockhopperPenguin

| Curve index | Portfolio change | Main identified exposure / actual source date | Context |
| --- | ---: | --- | --- |
| 53368 | -2.10% | LI / 2024-03-21 | 671 shares; accepted price 34.41 -> 31.02 explains -2,274.69 exactly. Li Auto reduced its delivery outlook that day. |
| 78326 | +2.04% | SOFI / 2024-04-29 | 4,339 shares; 7.72 -> 8.22 explains +2,169.50 exactly. Earnings-release timing. |
| 81751 | +2.07% | OPEN / 2024-05-02 | Earnings rebound described above. |
| 81762 | -3.00% | NET / 2024-05-02 | 271 shares; the cleaner rejects 74.02 at 20:15, then accepts 75.06 at 20:16 after the previous accepted mark of 87.58. NET explains -3,392.92 of the -3,449.25 net step; new trades also execute on this bar. |
| 283191 | +2.12% | AVGO / 2025-03-06 | 217 shares; source prices rise from 180.2738 to 192.896 at 21:15 during earnings. Other holdings account for the small difference from the total curve change. |
| 314006 | -2.25% | ENPH and ISRG / 2025-04-22 | Large ENPH holding falls during its earnings release. ENPH source closes decline 50.90 -> 48.89 at 20:07, then 47.32 the next minute; the portfolio continues lower. |

These have plausible company-news context. That verifies timing and a reason for repricing, not every recorded print or simulated fill. Sources: [Li Auto guidance revision](https://ir.lixiang.com/news-releases/news-release-details/li-auto-inc-updates-first-quarter-delivery-outlook), [SoFi earnings timing](https://investors.sofi.com/news/news-details/2024/SoFi-Schedules-Conference-Call-to-Discuss-Q1-2024-Results/default.aspx), [Cloudflare earnings](https://www.cloudflare.com/en-ca/press/press-releases/2024/cloudflare-announces-first-quarter-2024-financial-results/), [Broadcom earnings](https://www.broadcom.com/company/news/financial-releases/62921), [Enphase earnings](https://www.sec.gov/Archives/edgar/data/1463101/000146310125000054/a2025q1exx991pressrelease.htm).

The remaining trained-strategy steps were screened and candidate source-price matches recorded locally; not all 39 have been independently classified. This follow-up establishes several concrete transient-print candidates and several distinct news-driven moves, rather than treating the entire jump count as data errors.

## Timestamp and plotting defect

All 70 completed runs have a shorter SP500 curve than their other strategy curves. In the open Year2022/random/TS1000 run:

- SP500: **299,571** snapshots.
- Each other strategy: **357,586** snapshots.
- Difference: **58,015** snapshots.

`run_simulation.py:246` gives workers strategy-specific symbol sets. SP500 therefore runs on its SPY timeline, while other strategies use the larger market timeline. The parent merges trades by integer bar index at `run_simulation.py:1114`, and keeps timestamps from the first completed worker at `run_simulation.py:1116`. SP500 completes first in the reviewed example.

Integer indices on these grids do not represent the same instant. `backtest/evaluator.py:199` assigns benchmark timestamps to other strategies' indices. For example, the TXN source spike on April 26 appears near May 9 in the Year2021/gpei trade export. Later trades lack calendar labels once their indices exceed the shorter timestamp array.

`scripts/plotting.py:624` and `scripts/plotting.py:632` trim curves to the timestamp-array length. The open Year2022/random plot consequently omits the final **58,015 strategy snapshots** and uses incorrect calendar coordinates for the remaining strategy values. This distorts the presentation and plotted end values; it does not create the numerical jumps in `curves_data.json`.

## Other limitations

Five runs lack final result curves because validation stalled: TS100/Year2021/tpe; TS500/Year2022/tpe; TS500/Year2024/gpei; TS500/Year2024/tpe; TS1000/Year2024/gpucb. The last is the user's open 2024 GPUCB log.

Missing-cache-segment fetch warnings appear in 62 of 75 logs. Many reported ranges correspond to listing boundaries, missing distribution-child history, or terminated symbols; these warnings alone do not establish a bad interior gap.

## Correction implemented after this review

The correction was implemented on 2026-10-26 and is logged in `docs/DATA_CLEANING_CHANGELOG.md`.

- `prepared-bars-v2` makes moves above 2% pending until two coherent positive-volume observations with sufficient combined dollar volume establish a new regime. Actual-cache replays now reject the isolated TXN, ADBE, INTU, INTC, KMI, and KTOS excursion bars and accept their returns as `REVERSION`.
- Parallel results retain a separate timestamp array for every strategy. Trades merge by actual UTC timestamp, and plotting rejects mismatches rather than truncating longer curves.
- New runs write `artifacts/json/curve_timestamps.json` and `artifacts/json/equity_jump_attribution.json` alongside `curves_data.json`.
- Forty-three active regression tests pass, including a two-worker case with deliberately different calendars and replay-shaped transient/sustained price sequences.

Raw market cache and historical run outputs were not rewritten. The numerical evidence in this review describes the old runs and remains useful as the before state. ALL_RUNS must be regenerated before comparing corrected strategy results.
