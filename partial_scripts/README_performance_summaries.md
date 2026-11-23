# Performance summary tables

Generate a pair of PDFs at each experiment collection's root:

```bash
module load devel/python/3.13.1
~/.cache/penguin-capitalist/bonus-analysis-venv/bin/python \
  partial_scripts/summarize_run_collections.py \
  run_log/GP_BP_UCB_mb100_p0.1_TC1.0_TS500 \
  run_log/KER0_20_1.5_1.0_TS500
```

`performance_summary.pdf` reports test returns (%).
`performance_summary_vs_spy.pdf` reports the strategy's test return minus the
same run's SPY return (percentage points). Both use the MasterPeng Viridis
layout: one page per strategy/variant, years in rows and search methods in columns.

Each cell includes mean return ± sample standard error, **Avg buys**, and
`n = completed / expected seeds`. Avg buys is the arithmetic mean of executed
test BUY orders from `metrics_summary.json`, using exactly the same completed
seeds as the return. It is an order count, not a training-trial count, daily
rate, or count of distinct stocks. Valid zero-buy results remain in the mean.
Missing results are excluded; fewer than two results have no estimable SEM.

The script discovers prefixed run names beneath `Year*/RS_*`. Duplicate reruns,
mixed training-step counts/search ranges, and incomplete strategy variants
are rejected to prevent pooling unlike runs. Seed-level CSV and cell-level
CSV/JSON are saved in `performance_tables`; existing simulation reports stay intact.

For methods whose runs have not started yet, specify the expected columns:

```bash
~/.cache/penguin-capitalist/bonus-analysis-venv/bin/python \
  partial_scripts/summarize_run_collections.py run_log/Lower_Mean_GP_1.0_TS500 \
  --methods gpei gpucb gpbpucb
```

Rerun the command after simulations finish to refresh the tables. MasterPeng's
existing exporter, mean plots, and SPY-relative statistical summary also include
Avg buys; regenerate the seed exports before plotting older CSV/XLSX tables
that do not contain the `buy_trades` column.

The Slurm wrapper is `../slurm_scripts/partial_scripts_run/performance_summary.sh`.
It accepts the same arguments. For example, use `sbatch --dependency=afterany:JOB_ID`
with that wrapper and a collection path to refresh after a simulation ends.
