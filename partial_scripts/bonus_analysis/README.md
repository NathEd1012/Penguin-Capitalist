# Bonus analyses of saved runs

These scripts read existing run artifacts. They do not import the simulation,
rerun training/backtests, or change existing reports. New outputs go directly
into the selected run's `artifacts` directory.

## Launcher

Edit `RUN_DIR` and `ANALYSIS_SCRIPTS` in
`../slurm_scripts/partial_scripts_run/run_bonus_analysis.sh` relative to
the project root, or use the absolute launcher path below. The initial run is:

```text
FinPeng_ALL_RUNS_TC2.0_TS500/Year2024/RS_42/MR_2024_broad_gpei_500_RS_42
```

Run locally or submit to Slurm:

```bash
bash /home/hd/hd_hd/hd_qp268/slurm_scripts/partial_scripts_run/run_bonus_analysis.sh
sbatch /home/hd/hd_hd/hd_qp268/slurm_scripts/partial_scripts_run/run_bonus_analysis.sh
```

The optional first argument replaces the run directory; remaining arguments
replace the script list. For example, from the project root:

```bash
bash ../slurm_scripts/partial_scripts_run/run_bonus_analysis.sh \
  run_log/FinPeng_ALL_RUNS_TC2.0_TS500/Year2024/RS_42/MR_2024_broad_gpei_500_RS_42 \
  histogram.py UMAP.py
```

The launcher runs scripts sequentially, tries the remaining scripts if one
fails, and exits with a failure status if any analysis failed. Add another
script here that accepts `--run-dir`, then add its filename to:

```bash
ANALYSIS_SCRIPTS=("histogram.py" "UMAP.py")
```

The launcher uses a separate virtual environment under
`~/.cache/penguin-capitalist/bonus-analysis-venv`, loading the cluster's
`devel/python/3.13.1` module. On first use it installs this directory's
`requirements.txt`. It leaves `venvPeng` and the simulation requirements alone.
The first installation needs package-index access; if compute nodes have no
access, run the launcher once on the login node before submitting to Slurm.
Set `ANALYSIS_VENV` to change the environment location, or `ANALYSIS_PYTHON`
to use an already prepared Python interpreter.

## Purchase value: `histogram.py`

- `buy_histograms.pdf`: one page per reported strategy/variant, excluding the
  SP500/SPY benchmark. Each page ranks tickers by total purchase value in USD, descending.
  Long rankings continue into columns on that same page, with a shared scale.
- `buy_histograms.csv`: purchase values (`purchase_value_usd`), ranks, and BUY
  order counts.

Purchase value is **quantity × execution price**, summed across all BUY trades
for each ticker, excluding commissions. Repeat purchases add to the total;
SELL trades do not subtract from it. It uses test-period executed trades in
`trades_log.txt`'s `EXECUTION DETAILS` section and ignores later repeated
recent-trade summaries. Prices in this log are rounded to cents, so totals
reflect those logged prices. When `json/metrics_summary.json` is available, the
parser verifies each strategy's BUY order count so an incomplete execution log
cannot silently produce a partial chart. Strategies with zero buys get an
empty explanatory page.

## Parameter-space UMAP: `UMAP.py`

- `umap_pareto.pdf`: one page per trained strategy, with the saved trial
  configurations projected into two dimensions. Colour shows the recorded
  training objective in dollars; a star marks the best eligible objective.
- `umap_pareto.csv`: trial IDs, coordinates, objective, absolute profit,
  benchmark-relative profit, BUY counts, and the best-trial marker.
- `umap_pareto.json`: settings, UMAP version, included trial counts, and feature
  names/scaling bounds for each strategy.

The input is `json/trainable_penguin_parameter_log.json`. It uses completed
trials with **at least 20 BUY trades**, or the run's saved `minimum_buy_trades`
if that threshold is higher. Trials below 20 buys are excluded before parameter
scaling, embedding, colouring, and CSV export. It includes the eligible trial cloud,
not only the nondominated frontier. Validation/test results are not included.

Each strategy is embedded separately because strategies have different
parameter sets. Input features are numeric parameter values, scaled to
`[0, 1]` using the observed eligible range of each parameter. Constant
parameters are removed. Performance, trial numbers, and the sampled
stock/time subsets are **not** embedding inputs; performance only sets colour.
Strategies need at least three distinct eligible configurations to get an
embedding; otherwise their page explains why one cannot be drawn.

Defaults are Euclidean distance, 15 neighbours, `min_dist=0.1`, two dimensions,
and layout seed 42 with one worker. For small samples, the neighbour count is
reduced to at most the number of points minus one. The UMAP seed belongs only
to this visualization and does not alter any experiment seed.

UMAP axes have no financial units, and coordinates from separate strategy
pages cannot be compared directly. Nearby points represent local parameter
similarity. Colours are outcomes from the trials' different sampled stock/time
windows, so colour differences do not isolate the effect of parameters.
See the official [UMAP parameter guide](https://umap-learn.readthedocs.io/en/latest/parameters.html)
and [reproducibility guide](https://umap-learn.readthedocs.io/en/latest/reproducibility.html).

To choose another colouring or layout, invoke the script directly after
loading the Python module:

```bash
module load devel/python/3.13.1
~/.cache/penguin-capitalist/bonus-analysis-venv/bin/python \
  partial_scripts/bonus_analysis/UMAP.py --run-dir /path/to/run \
  --color-by relative-profit --neighbors 20 --min-dist 0.15 --seed 42
```

Other options: `--color-by profit` and `--output /path/to/custom.pdf`.
Both analysis scripts accept `--output`;
companion CSV/JSON files use the same basename. Rerunning replaces only these
bonus-analysis output files.
