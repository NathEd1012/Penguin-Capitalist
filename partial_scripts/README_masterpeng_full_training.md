# MasterPeng full training-window evaluation

From the workspace directory, submit five jobs (one for each year 2020–2024):

```bash
bash slurm_scripts/partial_scripts_run/masterpeng_training.sh
```

Use `--dry-run` to validate and preview without submitting jobs. Each year contains
5 methods × 3 penguins × 5 seeds × 5 checkpoints = **375 evaluations**;
the five jobs produce **1,875 rows**, plus one shared SPY benchmark per year.
Methods: Random, CMA-ES, TPE, GP-EI, GP-UCB. Seeds: 11, 22, 33, 42, 55.

For N = 100, 200, 300, 400, 500, select the best completed training trial among
trials 1 through N, separately for each strategy, method, and seed. The ranking
uses the original score tuple: penalized relative training profit, then fewer
buys, then fewer total trades. Exact ties retain the earliest trial. Skipped
trials count against the checkpoint budget. Every history must contain all 500
trial numbers for every strategy. Validation winners are not used.

Replay each winner over its original full January 1–October 1 training window,
using the full original symbol list, original initial capital, training transaction
cost, bar interval, and execution delay. Repeated winners at later checkpoints
are executed independently and have separate rows. No optimization is rerun.
The replay return is ordinary portfolio performance after transaction costs; it
does not subtract the search objective's activity penalty.

The launcher freezes the selected parameters and a copy of the evaluation code.
Each yearly job loads market data once and uses up to five fork workers, reduced
if necessary to fit its 230 GiB memory budget. The jobs request six CPUs and
72 hours each. They use the project's existing raw and finalized data caches.
The code snapshot preserves today's backtest implementation; it does not recreate
an older historical implementation or freeze raw data before loading.

Outputs are under the MasterPeng collection's
`performance_tables/full_training_replays/<batch>/`:

- `masterpeng_full_training_performances.csv`: all 1,875 checkpoint results,
  updated as workers finish, with parameters, source hashes, winning trials,
  training objectives, returns, SPY excess returns, drawdowns, Sharpe ratios,
  trade counts, execution settings, and paths to individual results/logs.
- `masterpeng_full_training_means.csv`: means and sample standard errors across
  completed seeds for each year/strategy/method/checkpoint. `n_completed` exposes
  partial results; `n_expected` is five. Missing values remain blank.
- `Year*/performances.csv`: the 375 rows for that year.
- `Year*/results/*.json` and `Year*/logs/*.out`: per-evaluation metrics and logs.
- `Year*/benchmark.json`: the SPY buy-and-hold benchmark on that training window.
- `Year*/slurm_*.out`, `progress.json`, `submitted.json`, and `plan.json`:
  runtime progress, Slurm job IDs, and the frozen evaluation manifest.

Returns and drawdowns use percent units; excess returns use percentage points.
Dollar fields use USD. Sharpe ratios use the existing evaluator's definition.
Pending/failed evaluations have blank performance values, never artificial zeros.

Resume an interrupted batch (completed checkpoints are retained; failed ones retry):

```bash
bash slurm_scripts/partial_scripts_run/masterpeng_training.sh --resume /absolute/path/to/batch/plan.json
```

Rebuild tables from saved checkpoints without evaluating anything:

```bash
module load devel/python/3.13.1
python /absolute/path/to/batch/code_snapshot/partial_scripts/reexecute_masterpeng_training.py \
  --manifest /absolute/path/to/batch/plan.json --refresh
```
