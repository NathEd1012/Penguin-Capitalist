# Experimental methodology: implementation audit

Inspection date: **10 November 2026**. Repository: `Penguin-Capitalist`; experiment launchers: sibling directory `slurm_scripts/full_runs`.

This report describes the **current working-tree implementation**, including existing uncommitted changes. The checked-out commit is `30849d140e8faef22a318e3292f39f19364602d8`; that commit alone does not identify all inspected code. Modified files include the simulation runner, evaluator, parameter-search configuration, all three strategies, and decision helpers. No implementation files were changed for this analysis, and no experiments were submitted or rerun.

**Subsequent implementation update (10 November 2026):** the extra per-buy scoring charge was removed from training and validation, and the Pareto zero-score line was removed. This report reflects that update. Existing archived trial scores and plots have not been regenerated.

The main configuration is the active launcher, `run_ALLRUNS.sh`, followed by its child `run_long.sh`. Python-only defaults and older archives differ. Values below refer to this launcher unless qualified. Environment variables inherited through `sbatch --export=ALL` can override child-script defaults that the parent does not fix. Existing logs establish particular run settings, not that every archive used the current code.

**Status terminology:** *Implemented* means an executable path exists; *configurable* means a setting or alternate path exists; *not implemented* means the inspected framework has no such procedure. **Not found in code** identifies information the repository and inspected artifacts do not establish. Source references [S1]–[S27] link to local files; Section 11.E names functions and line locations.

## 1. Historical data splitting

### 1.1 Periods and exact boundaries

`config/backtest.py` derives dates using `_add_months()`:

~~~text
TRAINING_START_DATE   = START_TIME
TRAINING_STOP_DATE    = TRAINING_START_DATE + TRAINING_PERIOD months
VALIDATION_START_DATE = TRAINING_STOP_DATE
VALIDATION_STOP_DATE  = VALIDATION_START_DATE + VALIDATION_PERIOD months
START_DATE           = VALIDATION_STOP_DATE       # test start
STOP_DATE            = START_DATE + TEST_PERIOD months
~~~

`run_long.sh` supplies `TRAINING_PERIOD=9`, `VALIDATION_PERIOD=3`, and `TEST_PERIOD=18`. `run_ALLRUNS.sh` submits anchors from 2020 through 2024. All boundaries below are **00:00:00 UTC**. Evaluation slices are **start-inclusive, stop-exclusive**, `[start, stop)`, through `backtest.data_cleaning.slice_data()`. Stop dates are boundaries, not guaranteed observation dates. [S1] [S2] [S3] [S14]

| Anchor | Training `[start, stop)` | Validation `[start, stop)` | Testing `[start, stop)` |
|---|---|---|---|
| 2020 | 2020-01-01 → 2020-10-01 | 2020-10-01 → 2021-01-01 | 2021-01-01 → 2022-07-01 |
| 2021 | 2021-01-01 → 2021-10-01 | 2021-10-01 → 2022-01-01 | 2022-01-01 → 2023-07-01 |
| 2022 | 2022-01-01 → 2022-10-01 | 2022-10-01 → 2023-01-01 | 2023-01-01 → 2024-07-01 |
| 2023 | 2023-01-01 → 2023-10-01 | 2023-10-01 → 2024-01-01 | 2024-01-01 → 2025-07-01 |
| 2024 | 2024-01-01 → 2024-10-01 | 2024-10-01 → 2025-01-01 | 2025-01-01 → 2026-07-01 |

The union of configured experimental periods is **2020-01-01 through, but excluding, 2026-07-01**. Each job spans 30 calendar months. Candidates use sampled portions of the nine-month training interval.

The raw cache is wider: inspected one-minute metadata for `LIST_5` spans **2016-01-01 00:00 UTC to 2026-06-30 23:59 UTC**, across instruments. This is a union of metadata bounds, not continuous coverage for every instrument. Metadata existed for 317 of the 318 configured symbols; `ADYEY` had no corresponding one-minute metadata file. Those earlier cache years are not additional training years.

Within an anchor, the three periods are ordered and non-overlapping. They meet directly: **no temporal gap, purge, or embargo is implemented**. Across anchors, consecutive test windows overlap by six calendar months: the 2020-anchor and 2021-anchor tests both include January–June 2022. Later anchors can train or validate on dates belonging to earlier anchors' tests.

The launcher implements a **fixed-length annual shift of independently initialized experiments**, which can be described as a rolling-origin experiment matrix. It does not implement an expanding training set, periodic retraining within a test window, a continuous walk-forward portfolio, or stitching of test windows into one out-of-sample curve. There are five training/validation/test triples, reused by all five search methods and all three strategies. [S1] [S3] [S10]

### 1.2 Training subwindows and stock sampling

`_train_trainable_penguins()` draws a fresh stock subset and time window **for every trial**. [S7] (lines 153–174 and 406–455)

- `FIXED_SYMB=50` comes from `run_long.sh`. `_training_symbol_subset()` samples up to **49 other symbols without replacement**, appends `SPY`, then sorts the subset. It can return fewer than 50 if the pool is smaller. `SPY` is included even in absolute-profit mode.
- `FIXED_MONTH=3` means `timedelta(days=3*30)`: **90 elapsed days**, not three calendar months.
- `_training_window_subset()` chooses a start from eligible observed timestamps with `rng.choice()`, leaving room for the requested length inside the training interval. It does not sample calendar dates or months uniformly.
- The helper gathers timestamps through `start+90 days` inclusively, but passes the first and last selected timestamps to a backtest that slices `[first, last)`. The logged `window_end` is an exclusive boundary; that final selected timestamp is excluded. Sparse observations can shorten the endpoint.
- Each candidate has one sampled-window evaluation. There is no average across repeated windows, instruments' independent backtests, or folds for that candidate.

Validation and testing use the job's available full configured universe, subject to eligibility gates. They do not retain the trial's 50-stock restriction. Thus **all 318 instruments are not used in every split or trial**. Nominal split dates are shared; actual sampled training observations are not necessarily identical between strategies or methods. See Section 9 for random-number streams.

### 1.3 Instrument availability and exclusions

`SYMBOL_LIST_5` contains **318 distinct symbols**. `pricing_symbols()` also requests `SPY` and distribution/reorganization dependencies. Extra names supply accounting prices and do not automatically join the strategy's tradable universe. An inspected full-run log requests **324 pricing symbols** for a 318-symbol strategy universe. [S6] [S14]

There is no fixed per-period exclusion table. Instead:

1. `DataLoader.detect_stale_data()` retains symbols with at least one `data_quality == 'OK'` observation in the supplied prepared dataset. This is not a requirement to have data at its final date.
2. `prepare_market_data()` marks observations `trade_eligible=False` when prior-session coverage is insufficient or volume is zero.
3. The simulation requires an accepted positive-volume observation in the configured session, sufficient history, and indicator-window coverage for signals and ordinary fills.

The session gate compares the stock's accepted positive-volume regular-session bar counts with SPY's observed counts across up to 20 completed earlier sessions, requiring at least five sessions and an aggregate ratio of at least 80%. Each stock's daily count is capped at SPY's count. This observed-SPY denominator is distinct from the exchange-calendar denominator used for the separate 50% indicator-window coverage gate.

The first filter operates on the wider prepared job dataset. Training-context reuse then retains matching symbol keys, potentially including empty training slices. A selected stock need not have observations throughout, or anywhere in, its sampled window. [S7] (lines 306–326) [S10] (lines 734–763) [S13] [S14] [S17]

Concrete inspected examples:

- `run_log/FinPeng_ALL_RUNS_TC2.0_TS1000/Year2024/RS_42/MR_2024_broad_random_1000_RS_42/artifacts/log.out` reports **316 valid configured symbols**, excluding `ADYEY` and `SGEN` from that job.
- Corresponding Year2020–Year2023 logs report **317 valid configured symbols**, with `ADYEY` absent. Some additional printed stale names are accounting dependencies rather than members of `LIST_5`.
- Current cache metadata starts `RIVN` on **2021-11-10 18:00 UTC** and `GREE` on **2021-09-15 10:16 UTC**. Neither supplies observations to 2020 training windows. A saved 2020 trial nevertheless lists `RIVN` among selected symbols, illustrating the difference between selection and actual availability.

A complete immutable manifest of accepted/tradable instruments for every historical split is **Not found in code**. These examples do not establish every exclusion in every archive.

### 1.4 Warm-up, carryover, and overrides

`run_backtest()` requests pre-start history via `history_warmup_bars()` and at least `DEFAULT_SPREAD_WINDOW-1 = 49` bars. For initial class-based runs, inherited `LOOKBACK_BARS=1000` normally makes this **1,000 nominal bars**. The canonical Step-1 cache anchor also uses 1,000 bars. At one-minute binning this subtracts **1,000 wall-clock minutes**, yielding an earliest nominal matrix load start of **2019-12-31 07:20 UTC**. Nontrading intervals and absent bars are not expanded into equivalent observed bars. Warm-up availability is attempted, not guaranteed. [S10] (lines 541–567 and 650–655) [S16]

Instance-based candidate backtests generally use the largest supplied parameter period plus two observations, subject to companion strategies' requirements. The broad maximum configured period is **360**; actual sampled periods determine candidate requirements. Each of the three strategies additionally demands `max(60, relevant periods)+2` observations.

A current implementation interaction matters: when a single candidate's largest period is below 60, the runner can pass fewer than 62 observations because its buffer uses `max_period+2`; the strategy then keeps returning `HOLD`. This can occur in training and single-strategy workers. Companion strategies with longer periods can change the shared history limit. This follows from `penguin_history_requirements()` and the strategy `min_required` checks; it is not an explicit parameter constraint. [S16] [S10] (lines 1255–1263 and 1496–1561)

Fresh portfolios, history buffers, spread histories, deferred orders, and normally fresh strategy instances are created for candidate, validation, and test evaluations. Cash, positions, and trades do not carry between them. Earlier-period observations may populate later warm-up windows, but computed indicators are not transferred: they are recalculated from each evaluation's visible history. **Precomputed cleaning and session-eligibility state does come from the wider prepared dataset and is preserved by slicing.** [S7] [S10] [S14]

`FIXED_START` and `FIXED_STOP` override test dates independently, with no explicit overlap check against training/validation. `FIXED_TRAIN_START` and `FIXED_TRAIN_STOP` are declared in `config/training_step.py`, but `config/__init__.py` exposes the original training dates from `config/backtest.py` without importing these replacements. The current main runner and training entry point import dates from `config`: those legacy training overrides are **not wired into these paths**. [S3] [S4]

## 2. Data snooping and information leakage

### 2.1 Which results influence selection?

The main workflow is **training-only search → training shortlist → validation ranking → frozen test candidates**. Validation scores do not enter `completed_trials` or the optimizer history. Validation actively selects final candidates: up to ten training-ranked candidates per strategy are evaluated and the best two by validation score proceed to testing. There is no average or weighted combination of training and validation scores for final ranking. [S7] (lines 563–579) [S10] (lines 842–1013)

No test metric is fed back into parameter suggestion or validation selection in the main workflow. After testing, `Evaluator.print_summary()` sorts results by `return_pct` and labels a **“Best Performer.”** This is a post-test report ranking. Whether the researcher subsequently chooses final parameters or methods from that ranking is **Not found in code**. [S12] (lines 337–364)

The same test dates recur across five methods, two selected variants per strategy, and reruns; consecutive annual tests overlap. There is no single-use test registry or access barrier preventing repeated inspection. A helper can request manual replay of saved parameters, although Section 9 describes a current constructor incompatibility.

### 2.2 Implemented protections

| Mechanism | Actual behavior |
|---|---|
| Chronological separation within an anchor | Adjacent half-open training, validation, and test intervals. |
| Optimizer isolation | Only completed training objectives guide Optuna proposals. |
| No recursive training in evaluation | Nested validation and candidate calls use `training_step_allowed=False`. |
| Causal strategy inputs | The ordered loop appends accepted observations through the current candle and passes trailing windows to `decide()`. |
| Execution delay | Default `T_PLUS_X=1` queues signals for a later simulation bar. |
| Causal outlier acceptance | `annotate_quality()` uses previous accepted prices/volumes and confirmation evidence accumulated through the current timestamp. Later confirmation does not retrospectively accept earlier rejected bars. |
| Prior-session eligibility | Eligibility uses completed earlier sessions; the current session is added afterward. |
| Signal coverage | Every applicable window needs at least 50% of expected in-session observations. Deferred orders are rechecked when due. |
| Missing-data treatment | No fabricated OHLCV or future-price backfill. Last accepted marks are carried only for valuation. |
| Portfolio isolation | Separate cash, positions, and accounting state for each candidate/strategy evaluation. |
| Spread histories | Per-symbol trailing OHLCV, including the current completed execution candle, with no later candles. |
| Overfitting-related scoring | Net profits include execution fees; low-activity penalties, fixed bounds, and validation after search remain. These mechanisms do not establish immunity to overfitting. |

Sources: [S7] [S8] [S9] [S10] [S14] [S15] [S17].

### 2.3 Retrospective dependencies and potential leakage

**Split normalization uses future observations relative to earlier bars.** `normalize_splits()` inspects valid observations immediately before and after each registered split boundary. It compares `abs(log(ratio/factor))` with `abs(log(ratio))` to decide whether earlier OHLC needs multiplication by the split factor; volume changes inversely. This occurs before the wider job dataset is sliced. A boundary in validation or test can therefore determine earlier training prices' and volumes' scale. [S14] (lines 126–171)

This is a definite retrospective dependency, without establishing that strategies explicitly read future returns. Its economic effect is not proven neutral: whole-share rounding, affordability, and order quantities can depend on adjusted price units. Reciprocal price/volume adjustment preserves price × volume, so dollar-volume thresholds alone do not establish an effect. The size and direction of any performance effect are **Not found in code**.

Other qualifications:

- **Universe membership:** the static list and wider-dataset “any OK observation” filter can let future availability influence the training sampling pool. No absent future quote is passed as a current quote. A point-in-time universe, universe selection-date record, and survivorship correction are not implemented.
- **Corporate actions:** splits, distributions, and reorganizations use a retrospective hard-coded registry. Accounting normally acts at effective timestamps, but normalization and dependency discovery inspect the registry in advance. Announcement-time/versioned information sets are not modeled.
- **Distribution accounting:** a prepared event uses a child's latest accepted-quality quote at or before event execution, subject to a 72-hour age limit. It does not look up a later quote. If required child prices are unavailable, the parent is sold at its last accepted pre-event mark at the event timestamp. This is an accounting fallback, not an observed executable event-time quote. [S14] (lines 314–350) [S18]
- **Bar timestamps:** session-clock code describes intraday timestamps as bar starts. Signals/fills use completed-candle OHLCV but retain that source timestamp in logs; no bar duration is added. Default delay separates the signal and fill candles, but a printed bar-start time does not prove its close was already observable at that literal instant.
- **Same-candle mode:** configurable `T_PLUS_X=0` allows completed-candle signals and a fill against the same candle's close/spread. Intrabar event simulation establishing input availability and achievable execution is not implemented.
- **Spread inputs:** fills use execution-candle open/high/low/close/volume. This is a completed-candle close-fill assumption and cannot be described as execution at its open.
- **Repeated selection/evaluation:** multiple validation candidates, two test variants, repeated tests across methods, and overlapping annual tests are implemented. Nested cross-validation, multiple-testing correction, an additional untouched final holdout, and an intervention registry are not implemented.
- **Changes after inspection:** existing data-quality audit documents inspect archived equity moves and document cleaning changes. The repository establishes that evaluation-related inspection and implementation changes occurred. It does not establish a complete chronology of which strategy/search settings were frozen before each evaluation or why each setting changed. That research history is **Not found in code**.

`has_corporate_action_near()` and `describe_corporate_action_near()` can inspect a ±2-day registry window, but are not called by the current main cleaning/signal path. Their existence alone does not establish forward-looking outlier acceptance. [S19]

Universe and period settings are fixed during a normal submitted job. Evidence that they were fixed **before experimentation began** is **Not found in code**.

## 3. Backtesting and portfolio simulation

### 3.1 Lifecycle of one backtest

1. `run_backtest()` normalizes boundaries to UTC, determines warm-up requirements, and slices prepared data or loads/cleans it.
2. It creates a fresh `Portfolio(initial_capital, transaction_cost, ...)` per strategy and a fresh `SyntheticSpreadModel()`. A training call contains one candidate and `SP500`.
3. It sorts the union of pricing-symbol observations and prepared accounting-event timestamps. This is an observed union clock, not a complete one-minute grid.
4. At each timestamp it accepts current prices only from `data_quality='OK'`, positive-volume, in-session candles; applies accounting events; and updates accepted price, volume, benchmark, and spread histories.
5. Pre-start observations warm histories without strategy trading. Event-only/unavailable timestamps can still produce valuations but do not advance the deferred-order trading-bar counter.
6. At an evaluation bar it executes due queued orders first. History and coverage checks then control new decisions. Strategies receive trailing closes, SPY observations aligned at each stock observation time, volumes, and current candle low/high.
7. `call_penguin_decide()` returns an action/quantity. Positive `BUY`/`SELL` signals are queued at `trade_bar_idx+T_PLUS_X`; a signal is not a completed trade. Zero delay executes immediately.
8. The runner records equity after each bar. At the last timestamp, due orders can execute, but no new strategy signals are generated.
9. It liquidates all remaining holdings, appends a final value snapshot, computes metrics, releases buffers, and returns results. The outer workflow saves artifacts.

Sources: `run_backtest()` [S10] (especially lines 1255–1637), `Portfolio` [S11], and `Evaluator.calculate_metrics()` [S12].

### 3.2 Capital and valuation

Configured initial capital is **USD 100,000**, supplied equally to candidate, benchmark, validation, and test portfolios. The class's standalone default of USD 5,000 is not used here. Each strategy can hold multiple stocks simultaneously using its own shared cash account; strategies and selected variants do not share money.

For cash \(C_t\), quantities \(q_{s,t}\), and current-or-carried accepted marks \(m_{s,t}\):

\[
V_t=C_t+\sum_s q_{s,t}m_{s,t}.
\]

A buy of \(q\) at ask \(a\) changes cash by \(-qa-c\); a sale at bid \(b\) changes it by \(+qb-c\), where \(c\) is the fixed fee per fill. `cost_basis[symbol]` is a weighted average of entry fill prices, excluding fees. Missing current marks fall back to that symbol's `last_known_prices`. An unpriced holding with no usable past mark raises an error. Mark provenance includes time, age, stale status, quality reason, and observed price. [S11] (lines 181–380)

All three strategies use default `max_leverage=1.0`: no shorting or borrowing. Higher leverage is supported for other strategies declaring `MAX_LEVERAGE`.

### 3.3 Signal and execution model

Indicators are calculated **inside `decide()`** from supplied accepted trailing observations. Stop-loss/take-profit checks compare current accepted **close** with average entry price. They are strategy signals subject to execution delay, not resting stop/limit orders filled intrabar.

Buy sizing uses whole shares:

\[
q=\left\lfloor
\frac{\text{cash}\,\text{max_cash_fraction}\,\text{strength}}
{\text{signal candle high}}
\right\rfloor,
\]

where strategy-specific `strength` is clamped to `[0.25, 2.0]`. Decision low/high and execution bid/ask are separate inputs. The signal quantity remains fixed until its scheduled execution; it is not resized at the later price.

With **`T_PLUS_X=1`**, a signal executes at the next counter-advancing union timestamp, against that later candle's close-centered synthetic quote. Buys pay **close + half-spread** and sells receive **close − half-spread**. This is neither next-open execution nor an unadjusted next-close fill. If the symbol lacks a usable eligible candle when the order is due, the order is discarded rather than postponed.

The counter advances when at least one accepted current pricing observation exists after evaluation start. “One bar” therefore need not mean one elapsed minute or that stock's next observation. Worker symbol calendars can differ, and accounting dependencies participate in timestamp construction. [S10]

### 3.4 Spread and explicit fees

`SyntheticSpreadModel` uses separate trailing OHLC and volume windows of **50** observations per symbol. With at least three candles it calls `bidask.edge(opens, highs, lows, closes, sign=False)` and multiplies the relative estimate by the current execution close. The current completed candle is included; future candles are not. [S15]

With insufficient history, missing open, or a non-finite EDGE estimate, fallback full spread is

\[
s_t^{base}=\max(0.0002p_t,\;0.05(H_t-L_t)).
\]

The spread is multiplied by **1.5** during the first 15 minutes from fixed **14:30 UTC**, **1.2** during the last 15 minutes before fixed **20:00 UTC**, and otherwise **1.0**. These spread-model times are fixed UTC values, separate from the DST-aware session clock. It also multiplies by `clamp(trailing_mean_volume/current_volume, 0.5, 2.0)`; that mean includes the current candle. Final quotes are `bid=p-spread/2` and `ask=p+spread/2`. A local backtest computes at most one quote per symbol/execution timestamp.

A separate fee applies to every successful buy and sell, including liquidation: **USD 2.00 in training**, **USD 1.00 in validation/test**. Execution fees are included once through portfolio profit; scores apply the separate low-activity penalty (Section 4). Separate slippage, market impact, order-book simulation, partial fills, borrow fees, and volume-participation limits are not implemented.

### 3.5 Order handling, liquidation, and corporate actions

- **Insufficient cash:** reject the entire buy if quantity × execution ask + fee exceeds cash. No partial fill or resizing. Invalid quantities/prices and oversized sells are also rejected.
- **Reservation/order priority:** delayed signals reserve neither cash nor positions. Multiple signals may size against the same cash. Due orders execute in stored order; earlier buys can exhaust funds for later ones.
- **BUY and SELL:** each strategy checks sells first and returns immediately on a sell for that symbol. There is no global sell-before-buy pass, netting, or simultaneous-fill clearing. Ordinary symbol iteration follows input order; training subsets are sorted alphabetically.
- **Fractions:** strategy buys use `floor()`. Portfolio accounting permits fractional positions from corporate actions and sells those fractions, including at liquidation. `Portfolio.buy()` itself does not enforce integer quantities.
- **Missing/rejected/ineligible observations:** ordinary fills are unavailable. Due orders are popped and not requeued. Holdings persist, using previous accepted marks when needed. Coverage failures increment counters; not every missing-data rejection has a separate metric.
- **Final liquidation:** every remaining holding, including fractional/distributed assets, is sold at the last timestamp's accepted synthetic bid if available, otherwise its last accepted stored mark. This bypasses ordinary eligibility/coverage gates, charges the fee, and tags `reason='final liquidation'`. Failure to price/liquidate raises an error. Current source takes precedence over older documentation describing another rule.
- **Splits:** normal loading converts prices/volume to canonical split units and marks the basis adjusted, avoiding runtime double adjustment. Raw-dictionary fallback can adjust positions, bases, histories, and marks once at a registered boundary. Affected accounting boundaries cancel pending orders and reset spread history.
- **Distributions/reorganizations:** prepared effective events book child shares/target symbols with converted ratios and allocated book cost. Missing child prices trigger the parent-exit fallback in Section 2. Ordinary cash dividends are not credited by current portfolio code; `Adjustment.RAW` does not create a dividend-total-return portfolio.

There is no random fill or spread component. For fixed parameterized instances, prepared data, symbol order, companion-strategy/history context, and settings, simulation is deterministic in its implemented logic. Search sampling, data revisions, and initialization of strategy classes from randomly sampled parameters are separate sources of variability.

## 4. Optimization objective

The objective is implemented in `scripts/training_objective.py`, chiefly `training_profit_amount()`, `activity_penalty()`, and `score_training_candidate()`. `_objective_from_score()` in the training runner passes only its first component to Optuna. It is **maximized**. [S7] [S8] [S9]

Let:

- \(C_0=100{,}000\): initial capital;
- \(P_\theta=\operatorname{round}(V_{\theta,T}-C_0,2)\): candidate dollar profit after spread, actual execution fees, and liquidation;
- \(P_b=\operatorname{round}(V_{b,T}-C_0,2)\): SPY benchmark dollar profit on the same candidate window;
- \(B_\theta\): successful buy-fill count, not number of shares;
- \(N_\theta\): successful total buy/sell-fill count, including liquidation;
- \(m=20\): `TRAINING_MIN_BUY_TRADES`;
- \(I_b=1\) for `FIXED_REL=SPY` and \(0\) for `FIXED_REL=0`.

The implemented scalar is

\[
\boxed{
f(\theta;D)=P_\theta-I_bP_b
-1.5C_0\frac{\max(0,m-\max(0,B_\theta))}{m}
}
\]

and application-level candidate ranking maximizes the tuple

\[
\big(f(\theta;D),\,-B_\theta,\,-N_\theta\big)
\]

lexicographically. Equal scalar scores prefer fewer buys, then fewer total fills. This is **one Optuna objective with application tie-breakers**, not multi-objective optimization.

Despite its name, the evaluator's `total_return` field is **dollar profit**, not a return fraction. The objective is consequently a custom penalized dollar-profit objective; it is neither Sharpe, CAGR, final capital alone, nor drawdown-adjusted return.

**Execution fees enter the score once, through net portfolio profit.** During training, candidate and SPY portfolios each pay USD 2 per successful fill. Validation and test portfolios pay USD 1 per successful fill. The score does not subtract any additional cost per buy; training and validation subtract only the low-activity penalty from absolute/benchmark-relative net profit. Test metrics report portfolio performance; the main test output does not calculate a new penalized selection score.

Low activity is a **soft penalty**, not a feasibility rule. At initial capital USD 100,000, zero buys costs USD 150,000; each missing buy below 20 contributes USD 7,500. The activity penalty disappears at 20 buys; execution fees remain included in net portfolio profit. Zero-trade candidates retain initial capital, earn zero candidate profit, and score

\[
f_{\text{zero trades}}=-I_bP_b-150{,}000.
\]

For zero benchmark profit, scores for 0, 1, 19, and 20 buys with otherwise zero candidate profit are respectively `-150000`, `-142500`, `-7500`, and `0` in training.

No explicit drawdown, volatility, Sharpe, portfolio-exposure, or percentage-turnover penalty is implemented. Trade counts influence costs, activity penalties, and tie-breaking. “Pareto” PDFs do not turn this into multi-objective search.

Each objective is the result of **one multi-instrument portfolio over one sampled training window**. It is not an average of per-stock returns or multiple periods. Validation is a later separate evaluation and does not enter the optimizer's objective history.

For fixed parameters, prepared data, order, execution settings, and history context, scoring/backtesting logic is deterministic. Across trials, the dataset \(D\) is resampled, so the search does **not** observe a fixed-data response solely determined by \(\theta\). It is not averaging repeated observations of each parameter vector.

Failure handling is not a finite bad-score policy:

- An empty stock/time subset consumes the outer loop iteration, appends a `status='skipped'` record, and supplies no objective.
- A candidate-construction error can propagate directly. A candidate backtest exception is wrapped in `RuntimeError` and aborts that training path.
- Ordinary rejected orders are not failed trials. Individual per-symbol decision exceptions are silently swallowed in the simulation, potentially leaving a completed candidate with fewer/no trades.
- Failed CMA-ES backtests mark the pending Optuna trial `FAIL`; GP/TPE do not retain failed trial records. Failed evaluations are not retried to achieve a fixed number of successful observations. No explicit non-finite-objective penalty is implemented.

## 5. Optuna implementation

### 5.1 Version evidence and study lifecycle

`requirements.txt` requests **`optuna>=5.0.0`**. The exact installed/executed Optuna version is **Not found in code or inspected result artifacts**. No lockfile, per-run package freeze, or Optuna version field was found. The partially retained `venvPeng` directory lacks the activation script referenced by the launcher and usable Optuna distribution-version metadata; its directory name does not establish an experiment's Optuna version. An older error message mentioning `optuna>=4.0.0` in `_optuna_sampler()` is not a version record. [S8] [S23]

CMA-ES training maintains **one live in-memory Optuna study per strategy** through `OptunaSearch`. At the first adaptive proposal, it imports completed application warm-up observations once. Each later candidate comes from `study.ask()` and its evaluated objective is returned through `study.tell()`. This preserves the trial generation attributes and serialized CMA optimizer state needed for population updates. The sampler is seeded once when this study is created. Failed backtests mark the pending trial `FAIL` before aborting; skipped subsets also clear any pending initial trial. This is process-lifetime persistence, not a database checkpoint or restart/resume mechanism.

The earlier implementation rebuilt the study before every CMA proposal and copied only parameters, distributions, and objective values. In Optuna 5.0.0, those imported trials lack the generation metadata required for CMA updates, so the distribution never adapts. Existing runs made with that implementation must be rerun to obtain adaptive CMA-ES results; changing source files does not update already-running Python processes.

GP and TPE retain their original transient-study path. On every post-warm-up proposal, `_optuna_suggest()`:

1. Creates a fresh study with `optuna.create_study(direction="maximize", sampler=_optuna_sampler(seed))`, without a storage URI or explicit study name.
2. Constructs `IntDistribution` / `FloatDistribution` objects from the configured space.
3. Re-adds previous `status='completed'` records using `study.add_trial(optuna.trial.create_trial(params=..., distributions=..., value=...))`. Records missing required parameters or outside current bounds are omitted.
4. Calls `study.ask()`, then `trial.suggest_int()` or `trial.suggest_float()`.
5. Returns parameters to the custom training loop; that loop performs the backtest and adds its result to the Python `completed_trials` list.

There is no `study.optimize()` or `study.tell()` in the GP/TPE path. The newly asked trial is not completed in that transient study. History is passed to the next newly constructed study as parameters/distributions/objective values; sampler-specific system attributes and optimizer state are not preserved. Stateful CMA-ES training uses the separate ask/tell path described above; stateless CMA history reconstruction is rejected. [S8]

### 5.2 Methods and exact constructors

The five launcher labels map as follows:

| Launcher label | `PARAMETER_SEARCH_METHOD` | Sampler / acquisition | Sampling path |
|---|---|---|---|
| `random` | `random` | Sampler fields are irrelevant | Python `random.Random` baseline throughout |
| `cmaes` | `bayesian_rand` | `cmaes` / `ei` | 10 random warm-up completions, then `CmaEsSampler` |
| `tpe` | `bayesian_rand` | `tpe` / `ei` | 10 random warm-up completions, then `TPESampler` |
| `gpei` | `bayesian_rand` | `gp` / `ei` | 10 random warm-up completions, then `GPSampler` |
| `gpucb` | `bayesian_rand` | `gp` / `ucb` | 10 random warm-up completions, then custom `GPSampler` subclass |

The `ei` field does not cause CMA-ES or TPE to use a GP acquisition function. It is the launcher's common configuration label; the respective sampler branches do not use it. [S1] [S8]

Exact project constructors:

~~~python
optuna.samplers.TPESampler(seed=seed, n_startup_trials=0)
optuna.samplers.CmaEsSampler(seed=seed, n_startup_trials=0)
optuna.samplers.GPSampler(seed=seed, n_startup_trials=0)

# _UCBGPSampler(seed) dynamically defines a GPSampler subclass, then returns:
UCBGPSampler(seed=seed, n_startup_trials=0)
~~~

No additional sampler keyword arguments are supplied. In particular, no project setting specifies TPE multivariate mode, GP deterministic-objective mode, CMA population size, sigma, restart behavior, or an independent sampler. These are not established as explicit experiment settings by the source; exact library-default behavior depends on the executed version.

The custom UCB subclass overrides private `_optimize_acqf()` and evaluates

\[
a(x)=\mu(x)+\kappa\sqrt{\max(\sigma^2(x),0)},\qquad \kappa=2.0.
\]

It uses private `optuna._gp.optim_mixed.optimize_acqf_mixed`, `acqf._gpr`, and inherited optimization settings. This makes its behavior dependent on compatible Optuna internals. It does not explicitly configure a GPU device.

Additional configurable search modes are `grid`, `bayesian_grid`, and `bayesian`. The grid is a custom compact Cartesian sequence: `levels=max(2, ceil(point_count**(1/d)))`, with mixed-radix indexing and interpolation between bounds. It is not Optuna `GridSampler`. `bayesian_grid` uses this sequence for warm-up; `bayesian` goes directly to the chosen sampler. None of these additional modes is selected by `run_ALLRUNS.sh`. Random search also uses custom `randint`/`uniform`, not Optuna `RandomSampler`. [S8]

### 5.3 Parameter distributions and dependencies

All integer parameters use inclusive integer bounds and unit step. Continuous proposals use linear bounds. Random/grid and transient GP/TPE suggestions are rounded to **four decimal places**. Stateful CMA-ES suggestions retain Optuna's exact float values so the evaluated vector matches the vector stored in its trial; its application warm-up still uses the rounded random/grid suggestions. No `log=True`, categorical distributions, project-level feature normalization, or reparameterization is used in the search path. Normalized L2 distances in plots are post-processing only.

The active broad bounds are below. G = Gentoo, R = Rockhopper, E = Emperor. [S5] (lines 103–165)

| Parameter | Type | Broad bounds | Strategies |
|---|---|---|---|
| `rsi_period` | int | 5–50 | G, E |
| `buy_rsi` | float | 5–50 | G, E |
| `sell_rsi` | float | 50–100 | G, E |
| `bb_period` | int | 10–100 | R, E |
| `bb_stddev` | float | 0.5–4 | R, E |
| `upper_band_buffer` | float | −0.25–1 | R, E |
| `ker_period` | int | 5–50 | G, E |
| `ker_reversal_threshold` | float | 0–55 | G, E |
| `ker_entry_threshold` | float | 0.01–75 | G, E |
| `max_cash_fraction` | float | 0.01–0.50 | G, R, E |
| `stop_loss_pct` | float | 0.01–0.20 | G, R, E |
| `take_profit_pct` | float | 0.005–0.50 | G, R, E |
| `cooldown_bars` | int | 0–100 | G, R, E |
| `relative_performance_period` | int | 10–360 | G, R, E |
| `relative_performance_threshold` | float | −0.10–0.05 | G, R, E |
| `rvol_period` | int | 10–120 | G, R, E |
| `rvol_threshold` | float | 1–5 | G, R, E |
| `trend_reversal_threshold` | float | 0–1 | R, E |
| `trend_entry_threshold` | float | 0.1–1.1 | R, E |

Gentoo has **14 dimensions**, Rockhopper **13**, and Emperor **19**. `strategy_parameter_space()` resolves strategy-specific names and filters them against constructor signatures; these three constructors accept `**parameters`.

A separate `narrow` space is configurable, not selected by the launcher. Its differences are: RSI period 5–25; buy RSI 10–40; sell RSI 60–90; BB period 10–50; BB standard deviations 1–4; upper buffer −0.25–0.25; KER period 7–30; both KER thresholds 20–40; cash fraction 0.05–0.20; stop loss 0.02–0.10; take profit 0.03–0.10; relative-performance period 30–100 and threshold −1–1; RVOL period 10–60 and threshold 1.5–2; trend-entry threshold `1e-6`–1. Cooldown 0–100 and trend-reversal threshold 0–1 are unchanged. Four-decimal rounding can turn the narrow trend-entry lower endpoint into zero; there is no rounding-aware bound repair.

No cross-parameter constraint, conditional search branch, feasibility callback, or dependency tying exit thresholds to entry thresholds is implemented. Parameter bounds and strategy-internal checks are the restrictions. For example, broad trend-entry values above the trend score's maximum of 1 can produce no Rockhopper buys without being rejected as invalid.

### 5.4 Startup, seeds, parallelism, persistence, pruning

Application warm-up is **10 completed random trials**, within the total 500 iterations, for the four adaptive methods. Python's default warm-up is 4 if scripts are bypassed. Samplers themselves receive `n_startup_trials=0`; library fallback behavior is distinct from the application's warm-up.

The training generator is `random.Random(TRAINING_RANDOM_SEED)`, default **42**. Every Optuna proposal consumes a seed draw via `rng.randrange(0, 2**32)`. GP/TPE use each new seed; persistent CMA-ES uses only the first draw to initialize its sampler, while later draws preserve the application's stock/time sampling cadence. A NumPy generator is also created, but `suggest_parameters()` deletes/ignores its `np_rng` argument. No explicit global PyTorch seed/deterministic-algorithm configuration appears in this path.

Trials within one strategy are sequential. Parallelism is across strategy training workers and across evaluation portfolios, rather than Optuna `n_jobs`. There is no persistent Optuna database, journal storage, study resumption, pruner call, `trial.report()`, `trial.should_prune()`, or objective-based early stopping. JSON archives persist application results after training, not resumable studies. [S7] [S8] [S10]

## 6. Optimization budget and repetitions

### 6.1 Budget, repetitions, and limits

The active launcher fixes **`FIXED_TS=500`** for every method and all three strategies. Each strategy performs `range(1, TRAINING_ITERATIONS+1)`: 500 attempted outer iterations, including warm-up. With no skips/failures, the four adaptive methods each have **10 warm-up + 490 sampler-driven** candidate evaluations; the random baseline has 500 random evaluations. [S1] [S7]

The launcher accepts one optional seed argument, with precedence `argument → TRAINING_RANDOM_SEED environment → 42`. It does not loop over seeds. Therefore the defined matrix has **one seed per invocation**, not a specified set of independent repeated-seed runs. The five annual anchors are different data periods, not five independent seed repetitions. Inspected named 500/1,000-trial batch directories use seed marker `RS_42`. An experiment-wide required number/list of independent seeds is **Not found in code**.

Startup trials consume the total budget. A skipped empty-subset iteration also consumes an iteration without adding a completed observation. A backtest failure aborts without replacement; CMA-ES additionally marks its pending Optuna trial `FAIL`. Thus 500 is not guaranteed to mean 500 successful completed trials.

The optimization budget is iteration-based, not elapsed-time-based. No Optuna/per-trial timeout exists. External/computational limits include:

- SLURM job wall time **50:00:00**, **230gb**, one node/task, **64 CPUs**, exclusive allocation, `cpu-single` partition.
- Evaluation-worker inactivity timeout `PENGUIN_WORKER_TIMEOUT=3600` seconds by default; it measures lack of worker progress, not an optimization-time budget.
- Pool shutdown timeout `PENGUIN_POOL_SHUTDOWN_TIMEOUT=30` seconds.
- Default memory estimate **40 GiB per worker**, reserve fraction **0**, used to cap process count.

One training trial calls `run_backtest()` once with **two separate portfolios: candidate and SPY**. No validation backtest occurs inside that trial.

### 6.2 Planned totals for the current launcher

Assume one invocation, no inherited overrides changing the stated matrix, all jobs complete, all 500 trials produce candidates, at least ten candidates per strategy reach validation, and two proceed to test.

| Quantity | Per submitted job | Across 25 jobs |
|---|---:|---:|
| Method/year jobs | 1 | **5 methods × 5 anchors = 25** |
| Strategy optimization runs | 3 | **75** |
| Training candidate trials | 3 × 500 = 1,500 | **37,500** |
| Training candidate portfolio simulations | 1,500 | **37,500** |
| Training SPY portfolio simulations | 1,500 | **37,500** |
| Validation candidate simulations | 3 × 10 = 30 | **750** |
| Validation SPY simulations | 1 | **25** |
| Test candidate simulations | 3 × 2 = 6 | **150** |
| Test SPY simulations | 1 | **25** |
| **All portfolio simulations** | **3,038** | **75,950** |

The candidate-only count including validation/test is **38,400**. Training requires **37,500 candidate-plus-benchmark backtest calls**; there are also 25 logical validation stages and 25 logical test stages. Recursive worker dispatch creates additional function invocations, so a count of `run_backtest()` calls is not interchangeable with independent portfolio simulations.

With \(B\) trials per strategy, total portfolio simulations for this matrix are \(25(6B+38)\). A 1,000-trial version would have **75,000 training candidates** and **150,950 total portfolio simulations** under the same assumptions.

The current launcher specifies 500 trials, while inspected `MasPeng...TS1000` and `FinPeng...TS1000` archives/logs record 1,000. These are different budgets. The available archive does not prove completion of the planned matrix: for example, the inspected `FinPeng_ALL_RUNS_TC2.0_TS1000` tree had logs but no completed training-history, validation-selection, or test-metrics JSON files at inspection time. This does not establish whether those jobs were still running or had stopped.

## 7. Training, validation, and final selection

The full selection path is implemented in `_train_trainable_penguins()` and the training/validation block inside `run_backtest()`. [S7] (lines 378–590) [S10] (lines 795–1015)

1. Sample an initial parameter vector. For every attempted training trial, draw a fresh 50-symbol/90-day sample inside the nine-month training interval.
2. Evaluate candidate and SPY with fresh USD 100,000 portfolios and training execution fees. Calculate the custom training score; append completed trial parameters and scalar objective to optimizer history.
3. Continue until the fixed iteration budget ends. Subsequent proposals can depend on earlier **training** objectives; validation/test results are unavailable to this loop.
4. Sort all completed candidates by the training tuple `(objective, -buys, -total_trades)`. Retain up to **`VALIDATION_CANDIDATES=10` per strategy**. No parameter-vector deduplication is implemented.
5. Create fresh named validation instances, `Strategy__validation_<training-trial>`. Evaluate up to 30 candidate portfolios plus one common SPY portfolio on the full three-month validation interval/full available universe.
6. Compute validation scores with the same functional form from net profits that already include USD 1 execution fees. Sort independently within each strategy **only by validation tuple**.
7. Keep the top **`PARAMETERS_EXECUTED=2` per strategy**. There is no automatic comparison/selection among independent seeds or different algorithm jobs.
8. Replace the original strategy with fresh instances using those selected parameters and new portfolios. The first validation-ranked variant keeps the base name; the second is named `<base>_<original-training-trial>`.
9. Test the **six frozen strategy configurations plus SP500** on the subsequent 18-month interval. Parameters are not updated during testing. Each of the 25 jobs produces its own selection, giving up to **150 tested strategy configurations** across the matrix, without requiring all vectors to be distinct.
10. Export test metrics and curves; sort printed test results by raw percentage return. No retraining or parameter selection is automatically triggered by these test results.

Training and validation are **not combined for refitting**. Optimization is not repeated after validation. The final ranking is not the mean training trial, average test trial, or an average across seeds: training chooses a shortlist, validation chooses two configurations, and the reports show their individual test performance. Automated cross-method statistical comparison or an overall single final model is not implemented.

File meanings are consequential: `trainable_penguin_training.json` retains **training-best** `best_params`/`best_metrics` and training-ranked lists. Its `top_params` and the parameter-delta report are not rewritten to the validation winners. `validation_selection.json` is the authoritative saved record of selected **validation-ranked** test parameters. Test performance influencing subsequent manual choices remains possible outside this automatic selection path; whether that occurred is **Not found in code**.

## 8. Performance metrics and evaluation

### 8.1 Exact portfolio metrics

`Evaluator.calculate_metrics()` reads `portfolio.value_history` and cached successful-fill counters. Dollar/percentage/Sharpe outputs are rounded to two decimals. [S12] (lines 28–112)

For recorded equity values \(V_1,\ldots,V_n\):

\[
\begin{aligned}
\text{final_value}&=\operatorname{round}(V_n,2),\\
\text{total_return}&=\operatorname{round}(V_n-C_0,2),\\
\text{return_pct}&=\operatorname{round}\left(100\frac{V_n-C_0}{C_0},2\right),\\
M_i&=\max_{j\leq i}V_j,\\
\text{max_drawdown}&=\operatorname{round}
\left(100\min\left(0,\min_{i:M_i>0}\frac{V_i-M_i}{M_i}\right),2\right).
\end{aligned}
\]

Drawdown is reported as a **nonpositive percentage**, not a positive loss magnitude. The running peak begins at the first recorded snapshot; the evaluator does not prepend initial capital.

For adjacent snapshots with positive previous equity and a finite return, define \(r_i=(V_i-V_{i-1})/V_{i-1}\). The code uses population variance:

\[
\mu=\frac1k\sum_i r_i,\qquad
\sigma^2=\max\left(0,\frac1k\sum_i r_i^2-\mu^2\right),\qquad
\text{Sharpe}=\frac{\mu}{\sqrt{\sigma^2}+10^{-10}}\sqrt{252}.
\]

It subtracts no risk-free rate. **The factor \(\sqrt{252}\) is applied to adjacent recorded bar returns even for one-minute/irregular timestamps; returns are not resampled to daily observations.** Thus the field should be described using its actual calculation, not as a conventionally time-adjusted annualized intraday Sharpe. Final liquidation appends another snapshot at the same last timestamp; its fee/spread effect can enter the adjacent-snapshot returns.

| Requested metric | Implementation and role |
|---|---|
| Final value, total dollar profit, percentage return | Implemented as above. Dollar profit is used inside training/validation scoring; all are reported. |
| Annualized return / CAGR | **Not found in code** for the active evaluation path. |
| Maximum drawdown | Implemented above; reported, not optimized. |
| Sharpe ratio | Implemented above; reported, not optimized. |
| Sortino ratio | **Not found in code**. |
| Volatility | Return variance/std is used internally for Sharpe. A separately saved volatility/annualized volatility metric is **Not found in code**. |
| Number of trades | `buy_trades`, `sell_trades`, `total_trades` count successful fills, including accounting/final liquidation sells. Buy/total counts affect score/ties. |
| Win rate | **Not found in code**. Per-symbol P&L is not a closed-trade win rate. |
| Average trade return | **Not found in code**. No matched-round-trip return series is calculated. |
| Transaction costs | Fixed fees are deducted from cash; spread is embedded in fill prices. Per-symbol cost/revenue summaries include fixed fees. No separate aggregate fee/spread-cost metric is saved; fixed fees can be derived as fee × successful-fill count. |
| Portfolio exposure | Positions/marks and generic leverage checks exist. No full time-weighted exposure metric/series is saved by the main evaluator. Large-jump attributions and an audit helper contain selected-event position/exposure information. |
| Buy-and-hold benchmark | `SP500` buys/holds `SPY` using the same simulation/fees; details below. |
| Optimization runtime | Whole training-stage wall time is logged; no per-trial runtime field. |
| Best objective after each trial | No dedicated cumulative-best field. It can be reconstructed from completed trial objectives. |
| Training/validation/test differences | Stage scores/metrics exist in separate files to different degrees; no automatic generalization-gap calculation or unified comparison table. |

Additional fields are `stale_position_count`, `coverage_blocked_decisions`, and `coverage_blocked_orders`. The stale count reflects the latest valuation marks, not cumulative stale exposure. Normal successful final liquidation leaves no open positions, so the final count is generally zero. Empty value history returns a small zero-metric dictionary without `final_value`; there is no elaborate invalid-result scoring policy.

### 8.2 P&L summaries and trade-count conventions

`Portfolio.get_symbol_summary()` computes per-symbol buy/sell counts, shares bought/sold, total buy cost, total sale revenue, current quantity/value, realized and unrealized P&L, and `pnl_pct`. Its formulas are

\[
\begin{aligned}
\text{total_cost}&=\sum_{\text{buys}}(q\,a+c),\\
\text{total_revenue}&=\sum_{\text{sells}}(q\,b-c),\\
\text{total_pnl}&=\text{total_revenue}-\text{total_cost}+\text{market_value},\\
\text{unrealized_pnl}&=(\text{mark}-\text{average entry price})q,\\
\text{realized_pnl}&=\text{total_pnl}-\text{unrealized_pnl},\\
\text{pnl_pct}&=100\,\text{total_pnl}/\text{total_cost}\quad(\text{if cost}>0).
\end{aligned}
\]

These are symbol-level cash-flow summaries, not matched-trade statistics; corporate-action allocations can make a per-symbol interpretation differ from portfolio-level profit.

An output convention differs: `create_final_report_pdf()` excludes `reason='final liquidation'` sells from displayed sell counts and shares sold, while retaining their proceeds/P&L. Evaluator metrics and objective counts include those sells. PDF sell counts should therefore not automatically be equated with `metrics_summary.json` sell counts. [S11] (lines 459–531) [S22] (lines 1205–1226)

### 8.3 Benchmark and diagnostic plots

`penguins/SP500.py::SP500` trades only `SPY` and declares no indicator coverage windows. After its history/eligibility checks, it proposes `int(max(cash-fee,0)/signal_high)` shares when no SPY is held. A successful entry is held until end liquidation. If an entry fails, it may try again on later signals. The benchmark has the same delayed close/spread execution model and fees, rather than an idealized first-open/last-close return. Cash dividends are not modeled.

Training includes a separate SPY simulation per candidate window; validation uses one common SPY portfolio for the shortlisted candidates; the test includes SP500 as a reported comparator. Candidate SPY-relative profit subtracts that simulated benchmark's **dollar profit**. It is not a regression alpha or risk-adjusted excess return.

`create_training_pareto_pdf()` plots buy count against absolute/benchmark-relative dollar profit, colors points by normalized L2 distance to chosen parameters, and omits the zero-score reference line. Current plotting excludes nonbenchmark trials below the minimum-buy threshold while retaining low-activity legend counts. It does not construct a nondominated set or run a Pareto optimizer. Plot normalization uses observed per-parameter ranges and does not affect proposals or selection. [S22] (lines 307–556)

## 9. Experimental comparability and reproducibility

### 9.1 Shared assumptions and differences

| Aspect | Finding |
|---|---|
| Nominal dates | Identical within an anchor across all methods/strategies. Annual anchors have overlapping tests. |
| Raw/prepared data | Shared loader/cache/cleaner implementation; one job reuses prepared data across its trials and evaluation stages. Separate jobs can see different cache/provider revisions. |
| Actual training samples | Resampled every trial, not guaranteed identical across methods/strategies. |
| Trading assumptions | Same engine, spread model, initial capital, gates, and delay across methods. Training fees differ from validation/test fees by design. |
| Search boundaries | Same active bounds for a given strategy across methods. Dimensions differ across the three strategies. |
| Trial budgets | Same 500 attempts per strategy/method in the current launcher; archived 1,000-trial batches differ. Not equal CPU-time budgets. |
| Seed repetitions | One specified seed per launcher invocation; configurable seed, no multi-seed loop. |
| Evaluation criterion | Training shortlist by custom score; final parameters by validation custom score; test report ranked by raw return. No implemented cross-method/seed statistical selection rule. |

### 9.2 Random streams and execution mode

`_train_trainable_penguins()` creates one `random.Random(seed)` used for parameter proposals, stock subsets, and time windows. After the adaptive warm-up, an Optuna proposal consumes one seed draw; a random-search proposal consumes draws for every parameter. The shared stream therefore diverges across methods, changing later samples even under the same top-level seed.

Parallel training workers each call this function with one strategy, resetting to the same configured seed. Sequential training calls it once for several strategies, sharing a stream across those strategies. Consequently switching `PENGUIN_PARALLEL` or worker availability can change later strategies' samples and search trajectories. Different parameter-space dimensions also consume different random draws. The fixed seed supports repeatability within a fixed execution setup; it does not establish paired identical trial datasets across all methods/strategies.

History-size interactions described in Section 1 can also make the companion strategy set and parallel evaluation mode affect which signals have enough history. Backtest determinism is conditional on these settings, not merely on the parameter vector and nominal dates.

### 9.3 Resources and software

`run_long.sh` requests `cpu-single`, one node, one task, 64 CPUs, exclusive allocation, 230gb, and 50 hours. It loads **`devel/python/3.13.1`**, attempts to activate `/home/hd/hd_hd/hd_qp268/venvPeng/bin/activate`, and runs `python -m pip install -q -r requirements.txt` before simulation. No GPU is requested by this main path; a separate `run_gpu.sh` exists outside the matrix. The UCB implementation imports PyTorch but does not explicitly select a GPU.

Worker count comes from `PENGUIN_WORKERS` or `SLURM_CPUS_PER_TASK` and is capped by strategy count and memory estimates. With the stated allocation and 40-GiB estimate, the memory rule generally permits about **five evaluation workers**; training has at most **three strategy workers**. Training trials inside each worker are sequential and disable nested strategy parallelism. Validation can evaluate 31 portfolios and testing seven portfolios through recycled processes. The launcher submits separate method/year jobs, whose overlap depends on SLURM scheduling. No explicit numerical-library thread count is set.

Requirements mostly provide lower bounds; exceptions include `exchange-calendars>=4.11,<5` and `bidask>=2.1.0,<3`. Other relevant declarations are `cmaes>=0.11.0`, `torch>=2.0.0`, `scipy>=1.15.0`, `numpy>=1.24.0`, `pandas>=2.0.0`, `alpaca-py>=0.19.0`, `matplotlib>=3.8.0`, and `pyarrow>=11.0.0`. Pip is invoked on every job, but dependencies are not locked to exact versions. Exact per-run versions, numerical-library build details, CPU model, and deterministic PyTorch settings are **Not found in code/result manifests**. [S2] [S7] [S10] [S23]

A concrete log in `FinPeng_ALL_RUNS_TC2.0_TS1000/Year2024/RS_42/MR_2024_broad_random_1000_RS_42` reports the activation file missing and then continues to simulation. The child script has no fail-fast setting around that activation command. Thus its intended virtual environment is not evidence of its actual package environment.

### 9.4 Caching and persistence

There are three relevant reuse mechanisms:

1. **Raw Parquet cache:** `DataCache` stores `data_cache/<SYMBOL>_<binning>.parquet` and metadata bounds. `PENGUIN_DATA_CACHE_DIR` can relocate it. Missing head/tail segments are fetched; internal holes are not automatically refetched unless refresh is requested. Small leading gaps of up to four days spanning dates may be left unfetched. New provider revisions replace cached rows at matching fetched timestamps. Cache writes use temporary-file replacement.
2. **Finalized Step-1 cache:** `backtest/finalized_data_cache.py` stores compressed pickle results in `data_cache/finalized_step1` or `PENGUIN_FINALIZED_CACHE_DIR`. Its key includes symbol list, dates, binning, warm-up, cleaning policy/version, corporate-action registry fingerprint/policy, adjustment flag, and raw file sizes/mtime values. `CACHE_VERSION=5`; current cleaning version is `prepared-bars-v3` and price-basis policy `canonical-price-volume-v3`. Cache reads are attempted; new writes in full runs require `SAVE_FIRST_STEP=1`, whose default is **0**.
3. **In-memory prepared data/session clocks:** trials slice shared prepared rows without re-cleaning; exchange session schedules are cached with `lru_cache(maxsize=16)`. Portfolios, indicators, and spread histories are not cached between candidate simulations.

These mechanisms do not cache/reuse candidate objective values. They can affect reproducibility through data availability, fetched revisions, raw-file changes, and cleaner/registry changes. No immutable per-run raw-data snapshot/checksum manifest is saved. The finalized key tracks file size/mtime rather than full raw-file content hashes. [S13] [S14] [S20] [S21]

### 9.5 Existing scripts and current reproduction limits

The main recipe exists as `run_ALLRUNS.sh → run_long.sh → run_simulation.py`, conditional on the intended module/packages, data/cache access, credentials for uncached observations, and inherited settings. Saved parameter vectors, trial sample windows/symbols, logs, and seeds help identify experiments. They do not by themselves recover an old data/code/software environment.

Several auxiliary paths have source-visible incompatibilities:

- `scripts/train_trainable_penguins.py::main()` passes `transaction_cost=...` to `run_training_step()`, whose current signature has no such parameter. That standalone path would raise a keyword-argument error if it reaches this call; the integrated main simulation does not pass it.
- `partial_scripts/reexecute_modelparameters.py::_strategy_instances()` constructs `base = strategy_class()` before applying saved parameters. The current three strategy constructors immediately instantiate parameter dataclasses with required fields; empty construction fails. The helper documents replay functionality but is not a verified working replay route for these current classes.
- The direct `run_long.sh` default active list and `scripts/run_range_check.py` include `KingPenguin`, which the current strategy registry does not expose. `run_ALLRUNS.sh` supplies its own valid three-strategy-plus-SP500 list and avoids that default.

No reproduction run was performed for this report. These are findings about existing source paths, not code changes or proposed fixes.

## 10. Experiment output and result files

### 10.1 Locations

For the current launcher and default seed, output is reserved under

~~~text
Penguin-Capitalist/run_log/
  FinPeng_ALL_RUNS_TC2.0_TS500/
    Year<2020..2024>/
      RS_42/
        MR_<year>_broad_<random|cmaes|tpe|gpei|gpucb>_500_RS_42/
~~~

Existing names get suffixes such as `_2`. The child exports `PENGUIN_RUN_OUTPUT_DIR`, allowing Python to use the reserved directory. `RUN_LOG_NAME=0` instead targets `run_test/`. Python-only runs use `get_run_output_dir()` and do not independently recreate all shell folder nesting.

SLURM stdout is also saved below `slurm_scripts/logs_multi_start/<FOLDER>/`, with method/year/seed and SLURM job ID. The child tees stdout/stderr to `<run>/artifacts/log.out`. The run name, folder, trial strategy/name/number, and seed in text logs distinguish repetitions; the two main training JSON files do not contain a dedicated seed field. [S1] [S2] [S3]

### 10.2 Artifact contents and completeness

| Artifact relative to run directory | Contents / limits |
|---|---|
| `artifacts/json/trainable_penguin_parameter_log.json` | Complete completed/skipped training iteration history when training finishes successfully; sampled window/symbols, parameters, objectives, profits, counts, penalties, proposal source. Written after training, not after every trial. |
| `artifacts/json/trainable_penguin_training.json` | Iteration/subset/cost/activity settings; initial and training-best parameters/metrics/score; training-ranked validation shortlist and training `top_params`. Full metrics for shortlisted candidates, not every historical trial. |
| `artifacts/trainable_penguin_training.log` | Training configuration, seed, per-trial windows/parameter changes/scores, training-best summaries, and total training time. Displayed symbol lists can be truncated; JSON stores full selected lists. |
| `artifacts/trainable_penguin_parameter_delta.txt` | Initial sampled versus training-best parameters, not final validation winners. |
| `artifacts/json/validation_selection.json` | Validation boundaries/count settings and **selected candidates only**: original trial, parameters, training score, validation score/metrics, activity penalty, and base name. |
| `artifacts/json/metrics_summary.json` | Final test metrics for six selected strategy variants plus SP500 in a complete default job. |
| `artifacts/json/curves_data.json` | Test portfolio values rounded to cents, keyed by strategy. |
| `artifacts/json/curve_timestamps.json` | Per-strategy UTC timestamp arrays aligned to test curves, including final liquidation snapshot. |
| `artifacts/json/equity_jump_attribution.json` | Large equity-move component attribution; default trigger is absolute one-snapshot move ≥1%. |
| `artifacts/json/valuation_marks.json` | Final holdings' mark provenance; normally no positions after successful liquidation. |
| `artifacts/trades_log.txt` | Test execution details at actual UTC timestamps, separately tagged liquidation trades, summaries, and recent ordinary trades. |
| `artifacts/consistency_warnings.txt` | Prepared-data quality summaries/warnings when available. |
| `TrainingPareto.pdf`, `ValidationPareto.pdf`, `artifacts/trainable_penguin_pareto_front.pdf` | Training/validation diagnostic scatter plots; not full numeric evaluation histories. |
| `artifacts/capital_curves.png` and `report.pdf` | Test capital curves and portfolio/symbol summaries. PDF generation errors can be caught and skipped. |
| `artifacts/csv/*_summary.csv` | Optional symbol/strategy summaries when `SAVE_CSV=1`; default is **0**. |
| `artifacts/log.out` | Runtime configuration, progress, whole training/run durations, and errors captured by the shell. |

Sources: [S7] (lines 749–852) [S10] (lines 994–1013 and 1735–1823) [S12] (lines 158–318) [S22].

A completed training-history entry records: `strategy`, `trial`, `status`, `proposal_source`, `window_start`, `window_end`, `selected_months`, `selected_symbols`, `params`, `param_changes_vs_previous`, `profit_amount`, `benchmark_profit_amount`, `relative_profit_amount`, `activity_penalty`, `relative_to`, `final_value`, `objective_value`, `relative_value`, `relative_net_gain`, `buy_trades`, `total_trades`, and the score tuple. `relative_value` and `relative_net_gain` duplicate its scalar score. A skipped entry is much smaller.

**Complete trial histories** exist for successful completed training stages, but are not crash checkpoints. A failure before persistence can leave only process logs. Training uses `collect_trade_details=False`: full per-trial trade tapes and equity curves are not saved. Full per-trial Sharpe/drawdown metrics are not present in the parameter-history JSON.

**Validation retention is partial:** all shortlisted candidates are evaluated in memory, but only up to two selected candidates per strategy are written to `validation_selection.json`. Rejected candidates' full numeric validation metrics and validation curves are not saved in a dedicated complete JSON history. The PDF can depict them subject to plot filtering.

Stage outputs are separate, but their scope differs: training history is broad, validation JSON is winner-only, and test files contain the frozen variants. There is no single saved table with complete train/validation/test metrics for every trial.

### 10.3 Convergence and timing reconstruction

For a successful history, training objective convergence can be reconstructed by sorting each strategy's completed trials by `trial` and taking the cumulative maximum of `objective_value`. No explicit best-so-far column is stored. Since trial datasets differ, this is a record of best observed sampled-window score, not convergence on one fixed evaluation dataset.

Training wall time is measured across the strategy-training stage, including parallel-worker completion, and excludes the subsequent training artifact/PDF writes. Main `Total run time` is printed after summary and before final artifact/plot/PDF generation, so it is not total job wall time. Per-trial duration, proposal overhead, and separated per-strategy optimization wall times are **Not found in code** as structured trial fields. SLURM/process logs may supply additional coarse timings.

### 10.4 Plot/table/summary scripts

- `scripts/plotting.py`: `plot_capital_curves()`, `create_final_report_pdf()`, `create_training_pareto_pdf()`, and optional CSV export.
- `partial_scripts/plot_training_params_evoution.py`: plots each sampled parameter over training steps and marks the maximum training-objective step; `run_long.sh` invokes it after successful simulation. It does not plot cumulative-best objective by default.
- `partial_scripts/plot_trainable_penguin_pareto.py`: parses training text logs and plots buy/profit/distance diagnostics plus raw benchmark-relative training performance over steps.
- `partial_scripts/audit_lf_runs.py` and `audit_run_jumps.py`: quality audits, curve/metric consistency checks, jump/holding summaries, and CSV/JSON outputs, rather than optimization-method significance tests.
- `partial_scripts/generate_data_inventory.py` and `review_datacache.py`: cached-data availability/density summaries.
- `partial_scripts/audit_corporate_actions.py` and `plot_all_stocks_pdf.py`: corporate-action/data diagnostic reports.
- `partial_scripts/reexecute_modelparameters.py`: intended parameter replay and additional report generation, with the current compatibility limit in Section 9.

An implemented procedure for repeated-seed confidence intervals, hypothesis tests between optimization methods, multiple-comparison adjustment, or a pooled final thesis comparison table is **Not found in code**.

## 11. Final summary

### A. Experimental workflow

1. Read the launcher seed (default 42); submit five methods × five annual anchors.
2. Derive adjacent nine-month training, three-month validation, and 18-month testing intervals.
3. Load raw cached/provider data plus accounting dependencies; normalize split units, annotate quality, and prepare prior-session eligibility over the wider job horizon.
4. Initialize strategy objects and independent USD 100,000 portfolios.
5. For each of the three trainable strategies, run 500 attempted parameter trials, each with a fresh 49-other-stocks-plus-SPY sample and approximately 90-day window.
6. Use custom random proposals throughout the baseline or for ten completed warm-up trials; subsequently use a persistent ask/tell study for CMA-ES, or reconstructed transient studies for GP/TPE, to propose adaptive candidates.
7. Backtest candidate and SPY with delayed close-centered spread fills, USD 2 fees, fresh state, final liquidation, and the penalized training objective.
8. Rank completed training candidates and take up to ten per strategy for a common full-universe validation stage.
9. Validate fresh portfolios with USD 1 execution fees already included in net profits and no extra per-buy scoring charge; keep two candidates per strategy by validation tuple.
10. Freeze those six parameter configurations and evaluate fresh portfolios plus SP500 on the 18-month test.
11. Liquidate holdings and save test metrics, curves, timestamps, trade logs, training/validation artifacts, and reports when each stage succeeds.
12. Repeat as independent jobs for remaining methods/anchors; no cross-job seed aggregation, stitched walk-forward portfolio, or automatic further refit is implemented.

### B. Configuration table

The launcher values below assume no inherited overrides of child-default settings.

| Setting | Main matrix value | Python-only/default distinction |
|---|---|---|
| Annual anchors | 2020, 2021, 2022, 2023, 2024 | `START_TIME` defaults to 2024-01-01 |
| Split lengths | 9 / 3 / 18 calendar months | Same Python period defaults |
| Experiment date union | `[2020-01-01, 2026-07-01)` UTC | Earlier cache data are not all used |
| Evaluation boundaries | Start inclusive, stop exclusive | No embargo |
| Binning | `1m` | Configurable: `1m, 5m, 15m, 1h, 1d` |
| Session | `extended`: 04:00–20:00 New York; half-day late close 17:00 | `DATA_TRADING_SESSION` can select `regular` |
| Universe | `LIST_5`, 318 distinct configured symbols | Actual eligibility/availability varies |
| Active strategies | Emperor, Gentoo, Rockhopper, SP500 | Python defaults also include SP500x2 |
| Initial capital | USD 100,000 per portfolio | Class-only Portfolio default is USD 5,000 |
| Methods | Random, CMA-ES, TPE, GP-EI, GP-UCB | Python default: `bayesian_rand` / GP-EI |
| Range set | `broad` | `narrow` also configured |
| Search dimensions | Gentoo 14; Rockhopper 13; Emperor 19 | Strategy-specific spaces |
| Iterations | 500 per strategy/method/anchor | Python default 3; archives also contain 1,000 |
| Random startup | 10 completed trials, within budget | Python default 4; sampler `n_startup_trials=0` |
| Trial universe | Up to 50 including SPY | Python default 30 |
| Trial time length | 3 × 30 = 90 days | Python default 2 × 30 = 60 days |
| Benchmark mode | `FIXED_REL=SPY` | `0` supports absolute profit |
| Training execution fee | USD 2 per successful buy/sell | Direct child default USD 5; Python default USD 2 |
| Validation/test execution fee | USD 1 per successful buy/sell | Python default USD 1 |
| Extra scoring cost per buy | None | Execution fees enter through net profit only |
| Minimum-buy target | 20 | Soft linear penalty, not exclusion |
| Maximum activity penalty | 1.5 × capital = USD 150,000 | USD 7,500 per missing buy below 20 |
| Validation shortlist | Up to 10 per strategy | Same Python default |
| Tested variants | Up to 2 per strategy | Python default 1 |
| Seed | Argument/environment, otherwise 42 | No automatic seed sweep |
| Delay | `T_PLUS_X=1` simulation bar | Configurable nonnegative integer |
| Initial warm-up | Normally 1,000 nominal bars | Wall-clock subtraction; availability not guaranteed |
| Session eligibility | ≥80% coverage over prior up to 20 sessions; at least 5 sessions | Cleaning-policy environment settings |
| Indicator coverage | ≥50% in each applicable expected-bar window | Constant `MINIMUM_COVERAGE=0.5` |
| Outlier confirmation | 2 coherent positive-volume bars, ≥USD 100,000 combined | Tolerance 5%; threshold 2%, or 1% when thin |
| Thin observation rule | Dollar volume <100,000 or volume <10% of prior 20 accepted volumes' median | Settings in `CleaningPolicy` |
| Outlier max jump / quarantine | 8%; permanent quarantine off | Base confirmation threshold is 2%, not simply 8% |
| Old-reference age limit | 72 hours + 1 microsecond | Used for reference resets/distribution-price age |
| Spread / volume window | 50 / 50 observations | EDGE after ≥3 OHLC candles |
| UCB exploration | `kappa=2.0` | Custom private-API GP subclass |
| SLURM resources | 1 node, 1 task, 64 CPUs, 230gb, 50 hours, exclusive `cpu-single` | Main matrix requests no GPU |
| Memory worker estimate | 40 GiB each; reserve fraction 0 | Worker count also capped by task/strategy count |
| Persistent Optuna study / pruning | CMA-ES in memory / none | GP/TPE use transient studies; no disk checkpoint/resume |
| CSV / finalized Step-1 writes | `SAVE_CSV=0` / `SAVE_FIRST_STEP=0` | Existing finalized cache can still be read |
| Python / Optuna requirement | Python module 3.13.1 / `optuna>=5.0.0` | Exact executed package versions not recorded |
| Planned jobs / optimization runs | 25 / 75 per seed invocation | Completion not guaranteed by archive presence |
| Planned total portfolio simulations | 75,950 at 500 trials | Includes training benchmarks, validation, test |

Additional cleaning defaults: `confirmation_tolerance=0.05`, `volume_window=20`, `coverage_sessions=20`, `minimum_sessions=5`, and `quarantine=False`. They are evaluated causally except for the split-basis normalization dependency discussed in Section 2. [S14]

### C. Methodology coverage

| Aspect | Status | Qualification |
|---|---|---|
| Chronological train/validation/test separation | Implemented | Within each anchor; tests overlap across anchors |
| Fixed-length rolling-origin matrix | Implemented | Annual independent jobs, no stitched portfolio |
| Continuous walk-forward / expanding training | Not implemented | No in-test retraining or cross-window state |
| Full-universe validation/test | Partially implemented | Full configured request, actual data/eligibility restrictions |
| Equal trial counts | Implemented as attempted budget | Successful completions can be fewer |
| Paired identical trial samples across methods | Not implemented | Shared RNG consumption differs |
| Multiple independent seed repetitions | Configurable, no scheduled sweep | One seed per matrix invocation |
| Causal indicators/outlier confirmation/coverage | Implemented | Completed current candles and previous observations |
| Strict point-in-time preprocessing | Partially implemented | Retrospective split-state inference and static universe |
| Delayed execution/spread/fees | Implemented | Later close-centered quotes, not intrabar/order-book simulation |
| Portfolio reset and liquidation | Implemented | Last accepted mark fallback can be an accounting exit |
| Custom scalar objective/activity penalty | Implemented | Net dollar profit (including execution fees) minus low-activity penalty |
| Validation-based final selection | Implemented | Two winners from ten training-ranked candidates |
| Test-driven parameter feedback | Not implemented in main loop | Printed test ranking and manual inspection remain possible |
| Resumable Optuna optimization | Not implemented | CMA-ES state persists in memory only; JSON histories are not study checkpoints |
| Sharpe/drawdown/return reporting | Implemented | Sharpe uses fixed √252 on adjacent snapshots |
| CAGR/Sortino/win rate/average trade return | Not implemented in active path | Not saved as performance metrics |
| Complete validation history retention | Partially implemented | Winner-only numeric JSON, diagnostic plots |
| Version/data-environment capture | Partially implemented | Requirements/logs/cache keys, no exact per-run lock/snapshot |
| Cross-method statistical inference | Not implemented | Audit summaries are not significance testing |

### D. Unresolved questions for the researcher

The following cannot be established from the code alone:

1. Which batch and exact working-tree revision define the thesis results: the current 500-trial launcher, a 1,000-trial archive, or another set?
2. How many distinct independent seeds/repetitions were actually intended and completed beyond the inspected seed-42 batches?
3. When and on what evidence were the 318 instruments and historical periods selected? Were future listings, survivorship, and exclusions known at selection time?
4. Which exact provider/cache versions, registry revision, cleaning version, Python/packages, and execution mode produced each included result?
5. Which strategy/search/cleaning settings changed after inspection of validation or test results, and which runs were then regenerated?
6. What is the intended final reporting unit: both validation-selected variants, only the first variant, or a later manually selected parameter configuration?
7. What external rule, if any, aggregates methods, seeds, and overlapping annual tests? Such a rule is not implemented here.
8. Are retrospective split normalization and stale-mark accounting exits treated as part of the research's permitted data/execution model? Their measured performance effects are not established by this audit.
9. Where are any complete nonwinning validation metrics, per-trial runtimes, historical accepted-instrument manifests, or exact environment snapshots retained outside the inspected outputs?
10. Which planned jobs completed successfully under the intended environment? Existing directory/log presence alone does not answer this.

These are documentation gaps and external research-history questions, not recommendations to change the implementation.

### E. Relevant source files and functions

Function names identify the supporting code; line locations from the inspected tree may shift after the subsequent implementation update.

| Reference | Source path | Main supporting locations |
|---|---|---|
| [S1] | `../slurm_scripts/full_runs/run_ALLRUNS.sh` | Lines 10–23, method mapping, `submit_run()`, annual loop |
| [S2] | `../slurm_scripts/full_runs/run_long.sh` | SLURM directives; defaults lines 10–42; environment/output setup; commands lines 97–112 |
| [S3] | `config/backtest.py` | `_add_months()` line 76; dates 152–170; capital/fees/delay 203–212; `get_run_output_dir()` |
| [S4] | `config/training_step.py` | Training defaults 11–50; artifact names 55–64; legacy date declarations |
| [S5] | `config/parameter_search_con.py` | Method/range settings 18–75; bounds 81–123; assignments 142–165; `strategy_parameter_space()`; `max_period_for_strategies()` |
| [S6] | `config/symbols.py` | `SYMBOL_LIST_5` lines 203–293; active-list resolution 295–309 |
| [S7] | `scripts/train_trainable_penguins.py` | Sampling 153–174; `prepare_training_context()` 244; training loop 332–590; `run_training_step()` 613; persistence 749–852 |
| [S8] | `scripts/parameter_search.py` | `_UCBGPSampler` 19; random/grid 68–86; `_optuna_sampler()` 89; `_optuna_suggest()` 106; `suggest_parameters()` 147 |
| [S9] | `scripts/training_objective.py` | `training_profit_amount()` 6; `activity_penalty()` 14; `score_training_candidate()` 22 |
| [S10] | `run_simulation.py` | Worker/memory helpers 101–173; `run_backtest()` 487; training/validation 795–1015; event/signal/fill loop 1313–1599; liquidation 1601–1637; `main()` 1681 |
| [S11] | `backtest/portfolio.py` | Initialization 36; corporate actions 89–175; `get_total_value()` 181; `buy()` 252; `sell()` 334; snapshots 393; symbol summaries 459 |
| [S12] | `backtest/evaluator.py` | `calculate_metrics()` 28; `save_results()` 158; `print_summary()` 326; report wrappers |
| [S13] | `backtest/data_loader.py` | `load_bars()` 172; RAW requests 249–255; loading/preparation 368–407; `detect_stale_data()` 435 |
| [S14] | `backtest/data_cleaning.py` | `CleaningPolicy` 24; `slice_data()` 84; `normalize_splits()` 126; `annotate_quality()` 174; `pricing_symbols()` 259; `prepare_market_data()` 281 |
| [S15] | `scripts/data_fixes/synthetic_spread_model.py` | Defaults 45–58; `observe_candle()` 114; spread estimate 152; volume factor 181; `get_bid_ask()` 290 |
| [S16] | `backtest/history.py` | `penguin_history_requirements()` 5; `binning_to_minutes()` 29; `history_warmup_bars()` 43 |
| [S17] | `backtest/signal_coverage.py` | `MINIMUM_COVERAGE` 14; `indicator_windows()` 17; `MarketBarClock` 34; `SignalCoverage` 85 |
| [S18] | `backtest/market_events.py` | `event_schedule()` 4; `apply_events()` 13 |
| [S19] | `scripts/data_fixes/corporate_actions.py` | Price-boundary/fingerprint functions 35–56; split events 159; distribution events 188; registry in `list_of_corp_act.py` |
| [S20] | `backtest/finalized_data_cache.py` | `CACHE_VERSION` 19; configuration key 26; `load()` 98; `save()` 148 |
| [S21] | `market_data/cache.py` | `DataCache` raw cache/bounds/range handling; `save_cache()` 163; `merge_cache_and_new_data()` 362 |
| [S22] | `scripts/plotting.py` | CSV 152; symbol aggregation 233; L2 normalization 307; training scatter 357; test curves 757; final PDF 973 |
| [S23] | `requirements.txt` | Dependency constraints, including `optuna>=5.0.0` |
| [S24] | `partial_scripts/plot_training_params_evoution.py` | `load_histories()` 67; `best_training_step()` 80; `plot_strategy()` 94 |
| [S25] | `partial_scripts/reexecute_modelparameters.py` | `_load_trials()` 25; `_select_trials()` 64; `_strategy_instances()` 93; replay call 203 |
| [S26] | `scripts/run_range_check.py` | Alternative 32-job matrix, `PENGUINS` 28; `_job_environment()` 51; `main()` 77 |
| [S27] | `config/strategies.py` | Available classes and `_resolve_active_penguins()` 33 |

Strategy-specific sources are [GentooPenguin](../penguins/GentooPenguin.py), [RockhopperPenguin](../penguins/RockhopperPenguin.py), [EmperorPenguin](../penguins/EmperorPenguin.py), [SP500](../penguins/SP500.py), [BasePenguin](../penguins/base_penguin.py), and [decision_utils](../penguins/decision_utils.py). The latter contains the active RSI, BB, KER, trend, relative-performance, and relative-volume helpers; these three strategies do not use similarly named archived helpers as their primary indicator implementations.

Existing supporting tests include [test_training_objective.py](../tests/test_training_objective.py), [test_training_activity.py](../tests/test_training_activity.py), [test_data_cleaning.py](../tests/test_data_cleaning.py), [test_signal_coverage.py](../tests/test_signal_coverage.py), [test_split_timing.py](../tests/test_split_timing.py), and [test_reporting_alignment.py](../tests/test_reporting_alignment.py). They provide additional implementation evidence; their presence is not a claim that all tests were run for this documentation-only audit.

Representative archive inspected: `run_log/MasPeng_ALL_RUNS_TC2.0_TS500/Year2020/MR_2020_broad_tpe_500_RS_42/artifacts/json/`. Its parameter history contains **1,500 trial records**, its validation file records **two selections per strategy**, and its test summary has **seven portfolios**. This corroborates those stage shapes for that archive, without establishing compatibility of all historical results with current working-tree behavior.

[S1]: ../../slurm_scripts/full_runs/run_ALLRUNS.sh
[S2]: ../../slurm_scripts/full_runs/run_long.sh
[S3]: ../config/backtest.py
[S4]: ../config/training_step.py
[S5]: ../config/parameter_search_con.py
[S6]: ../config/symbols.py
[S7]: ../scripts/train_trainable_penguins.py
[S8]: ../scripts/parameter_search.py
[S9]: ../scripts/training_objective.py
[S10]: ../run_simulation.py
[S11]: ../backtest/portfolio.py
[S12]: ../backtest/evaluator.py
[S13]: ../backtest/data_loader.py
[S14]: ../backtest/data_cleaning.py
[S15]: ../scripts/data_fixes/synthetic_spread_model.py
[S16]: ../backtest/history.py
[S17]: ../backtest/signal_coverage.py
[S18]: ../backtest/market_events.py
[S19]: ../scripts/data_fixes/corporate_actions.py
[S20]: ../backtest/finalized_data_cache.py
[S21]: ../market_data/cache.py
[S22]: ../scripts/plotting.py
[S23]: ../requirements.txt
[S24]: ../partial_scripts/plot_training_params_evoution.py
[S25]: ../partial_scripts/reexecute_modelparameters.py
[S26]: ../scripts/run_range_check.py
[S27]: ../config/strategies.py

