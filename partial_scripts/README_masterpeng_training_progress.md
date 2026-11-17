# MasterPeng training progress plots

From the project root:

```bash
module load devel/python/3.13.1
python partial_scripts/plot_masterpeng_training_progress.py
```

The default input is the completed collection in
`run_log/Done_usefull/MasterPeng_ALL_RUNS_TC1.0_TS500`.
Use `--root PATH` for a different copy of the MasterPeng collection, and
`--output-dir PATH` to choose the output folder.

The script creates three figures: EmperorPenguin, GentooPenguin, and
RockhopperPenguin. Each has five start-year panels (2020–2024), and each panel
compares Random, CMA-ES, TPE, GP-EI, and GP-UCB.

At each checkpoint N = 50, 100, …, 500, the script takes the highest saved
`objective_value` among trials 1 through N **within each seed**, then averages
those five maxima. This is cumulative best performance, so a result found before
50 steps remains eligible at every later checkpoint. Years are kept separate.
Training variants are not split because they share the same training search.

The y-axis uses dollars: training profit relative to SPY after the saved activity
penalty. Shading shows ±1 standard error across the seed maxima, calculated using
sample standard deviation (ddof = 1). Seeds are 11, 22, 33, 42, and 55. The script
requires all five complete seed histories; missing trials or seeds cause an error.
Skipped trials count against the step budget but cannot supply an objective.

Outputs are saved alongside the existing summary tables in
`performance_tables/training_progress/`:

- `masterpeng_training_progress.pdf`: all three figures, one per page.
- `masterpeng_training_progress_<strategy>.pdf` and `.png`: individual figures.
- `masterpeng_training_progress_seed_checkpoints.csv`: each seed's cumulative
  maximum, with the source history path.
- `masterpeng_training_progress_means.csv`: plotted means, standard errors, and
  sample sizes.
- `masterpeng_training_progress.json`: plotted statistics and calculation details.

Only existing `artifacts/json/trainable_penguin_parameter_log.json` histories are
read. No simulation or training job is run.
