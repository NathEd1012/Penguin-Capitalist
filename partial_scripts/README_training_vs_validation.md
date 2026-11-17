# Grouped training vs. validation reports

Submit from the workspace:

```bash
bash slurm_scripts/partial_scripts_run/tra_vs_val_report.sh --dry-run
bash slurm_scripts/partial_scripts_run/tra_vs_val_report.sh
```

The launcher now discovers `run_log/Done_usefull/MasterPeng*`, skips complete
`tra_vs_val_report.pdf` files, and submits one single-node job per combination of
test start, test stop, binning, and symbol list. Other collections can be selected
with `MASTER_PATTERN` and `RUN_LOG_ROOT` (the latter contains `Done_usefull`).
The original single-run `reexecute_training_vs_validation.py` is unchanged.

Each job requests 230 GiB, six CPUs, and 48 hours. Data preparation/cache loading
happens once in the parent. Up to five forked strategy workers share the prepared
bars. Worker count decreases when parent memory plus the 34 GiB worker estimate
and 16 GiB reserve would exceed the allocation. There are no nested worker pools;
BLAS/OpenMP threads are limited to one. `GROUP_WORKERS` and `MAX_CONCURRENT`
(default four dataset jobs) can lower concurrency.

A strategy task uses the existing `run_backtest` with its original parameters,
test window, capital, execution cost, and order delay. Training is disabled.
Individual-strategy calls preserve the old parallel runner's history/warmup
behavior. Identical parameters/settings share a checkpoint; each dataset's
benchmark is calculated once. Completed strategies are saved directly to disk,
so large portfolios and market data are not sent through multiprocessing pipes.

Reports and replay artifacts are written only into the source run's
`artifacts/tra_vs_val` and `tra_vs_val_report.pdf`. Original training, validation,
and test artifacts are preserved. Checkpoints live in
`run_log/.tra_vs_val_shared/<dataset-id>/<strategy-hash>/`. A completion marker is
published only after all strategy result files are saved. Checkpoint identity
includes source-code and prepared-data configuration fingerprints.

Job manifests and submission receipts are in
`slurm_scripts/logs/tra_vs_val/groups_*.json`; node logs are `<job-id>_group.out`.
While a strategy runs, its detailed progress is in the checkpoint's
`<strategy-hash>.pending-<pid>/execution.log`; completion renames that directory
to `<strategy-hash>/`. Re-running the launcher preserves completed reports and
reuses valid strategy checkpoints. It rejects duplicate submission while a
previous grouped batch remains in the queue.

Active tasks from the old `tra_vs_val_report` array are not canceled. The matching
dataset job waits for those tasks with `afterany` dependencies, then recovers
finished reports from the previous folder location and skips their computation.
The move merges only report files, checks conflicts first, and publishes the PDF
last. Failed old tasks are replayed with the rest of the missing reports.

Regression checks, including a real fork pool and serial-result comparison:

```bash
cd Penguin-Capitalist
module load devel/python/3.13.1
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover \
  -s tests -p 'test_*training_vs_validation*.py' -v
```
