"""Replay MasterPeng's cumulative winners on their full training windows.

--prepare validates the 125 histories and freezes a plan plus runtime source.
Each of five yearly Slurm jobs evaluates 375 checkpoint/strategy/seed/method
combinations. Repeated winners remain separate evaluations and separate rows.
"""

import argparse
from collections import Counter, defaultdict
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import csv
import fcntl
import gc
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
from statistics import fmean, stdev
import subprocess
import sys
import time
import traceback

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from partial_scripts import grouped_training_vs_validation as shared
from partial_scripts.export_masterpeng_performance import METHODS, SEEDS, YEARS

STRATEGIES = ("EmperorPenguin", "GentooPenguin", "RockhopperPenguin")
CHECKPOINTS = (100, 200, 300, 400, 500)
DEFAULT_ROOT = PROJECT / "run_log/Done_usefull/MasterPeng_ALL_RUNS_TC1.0_TS500"
METRICS = ("return_pct", "total_return", "final_value", "max_drawdown", "sharpe_ratio",
           "buy_trades", "sell_trades", "total_trades", "coverage_blocked_decisions",
           "coverage_blocked_orders", "stale_position_count")
FIELDS = ("year", "method", "seed", "strategy", "training_steps", "winning_trial",
          "training_objective", "training_score", "status", *METRICS,
          "spy_return_pct", "excess_return_pp", "relative_profit_amount",
          "training_start", "training_stop", "initial_capital", "transaction_cost",
          "binning", "symbol_list", "t_plus_x", "params", "trial_window_start",
          "trial_window_end", "execution_seconds", "failure", "source_file",
          "source_sha256", "result_file", "execution_log")
_SHARED = None


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def select_checkpoints(history):
    """Use training's score ranking and earliest-trial ties, without lookahead."""
    trials = {strategy: {} for strategy in STRATEGIES}
    for row in history:
        strategy, trial = row["strategy"], row["trial"]
        if strategy not in trials or type(trial) is not int or not 1 <= trial <= 500:
            raise ValueError(f"Unexpected strategy/trial: {strategy} / {trial}")
        if trial in trials[strategy]:
            raise ValueError(f"Duplicate trial {trial} for {strategy}")
        if row["status"] == "completed":
            value = row["objective_value"]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                raise ValueError(f"Invalid objective for {strategy}, trial {trial}")
            score = shared.report.score_key(row, "score")
            if score[0] != value or not isinstance(row.get("params"), dict) or not row["params"]:
                raise ValueError(f"Invalid score/parameters for {strategy}, trial {trial}")
        elif row["status"] != "skipped":
            raise ValueError(f"Unexpected trial status: {row['status']}")
        trials[strategy][trial] = row
    selected = []
    for strategy, rows in trials.items():
        missing = set(range(1, 501)) - rows.keys()
        if missing:
            raise ValueError(f"Incomplete history for {strategy}; missing trials: {sorted(missing)}")
        best = None
        for trial in range(1, 501):
            row = rows[trial]
            if row["status"] == "completed" and (best is None or
                    shared.report.score_key(row, "score") > shared.report.score_key(best, "score")):
                best = row
            if trial in CHECKPOINTS:
                if best is None:
                    raise ValueError(f"No completed trials for {strategy} by checkpoint {trial}")
                selected.append({"strategy": strategy, "training_steps": trial,
                                 "winning_trial": best["trial"], "params": best["params"],
                                 "training_score": list(shared.report.score_key(best, "score")),
                                 "training_objective": best["objective_value"],
                                 "trial_window_start": best.get("window_start", ""),
                                 "trial_window_end": best.get("window_end", "")})
    return selected


def training_settings(run, year, data):
    settings = shared.report.execution_settings(run)
    fields = {"start": "Training Start (UTC)", "stop": "Training End (UTC)",
              "validation_start": "Validation Start (UTC)",
              "validation_stop": "Validation End (UTC)"}
    dates = {}
    with (run / "artifacts/log.out").open(errors="replace") as log:
        for line in log:
            for key, label in fields.items():
                match = re.match(r"^" + re.escape(label) + r":\s*(.*?)\s*$", line)
                if match:
                    dates.setdefault(key, match.group(1))
            if len(dates) == len(fields):
                break
    if dates.keys() != fields.keys():
        raise ValueError(f"Missing original training dates: {run}")
    for key, month in (("start", 1), ("stop", 10)):
        if shared.report.parse_datetime(dates[key]) != datetime(year, month, 1, tzinfo=timezone.utc):
            raise ValueError(f"Expected nine-month training window for Year{year}: {run}")
    settings.update(dates)
    settings["transaction_cost"] = data["training_transaction_cost"]
    if settings["transaction_cost"] != 1.0 or settings["initial_capital"] != 100000:
        raise ValueError(f"Unexpected original capital/training transaction cost: {run}")
    return settings


def collect_plan(root):
    groups = []
    for year in YEARS:
        records, yearly_settings = [], None
        for method, _ in METHODS:
            for seed in SEEDS:
                run = root / f"Year{year}/RS_{seed}/MR_{year}_broad_{method}_500_RS_{seed}"
                source = run / "artifacts/json/trainable_penguin_parameter_log.json"
                raw = source.read_bytes()
                data = json.loads(raw)
                if data.get("iterations") != 500 or data.get("relative_to") != "SPY":
                    raise ValueError(f"Expected 500 trials trained relative to SPY: {source}")
                settings = training_settings(run, year, data)
                if yearly_settings is not None and settings != yearly_settings:
                    raise ValueError(f"Inconsistent execution settings in Year{year}: {run}")
                yearly_settings = settings
                try:
                    selected = select_checkpoints(data["trial_history"])
                except (ValueError, KeyError) as error:
                    raise ValueError(f"{source}: {error}") from error
                for point in selected:
                    records.append({"year": year, "method": method, "seed": seed,
                                    **point, "source_file": str(source),
                                    "source_sha256": hashlib.sha256(raw).hexdigest()})
        groups.append({"year": year, "settings": yearly_settings, "records": records})
    return {"version": 1, "root": str(root), "data_cache": str(PROJECT / "data_cache"),
            "checkpoints": CHECKPOINTS,
            "seeds": SEEDS, "methods": METHODS, "strategies": STRATEGIES, "groups": groups,
            "selection": "max saved score among trials 1..N; earliest trial on exact ties",
            "evaluation": "full original nine-month training window, full symbol list; no retraining"}


def runtime_paths(project):
    paths = [project / "run_simulation.py", project / "requirements.txt"]
    for folder in ("backtest", "config", "indicators", "market_data", "penguins", "scripts"):
        paths.extend((project / folder).rglob("*.py"))
    paths.extend(project / "partial_scripts" / name for name in (
        Path(__file__).name, "grouped_training_vs_validation.py",
        "reexecute_training_vs_validation.py", "export_masterpeng_performance.py"))
    return sorted(set(paths))


def runtime_digest(project):
    return shared.digest({str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in runtime_paths(project)})


def prepare(root, output):
    plan = collect_plan(root)
    import penguins
    for group in plan["groups"]:
        for record in group["records"]:
            getattr(penguins, record["strategy"])(**record["params"])
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "code_snapshot"
    for path in runtime_paths(PROJECT):
        target = snapshot / path.relative_to(PROJECT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    plan.update({"output": str(output), "snapshot": str(snapshot),
                 "code_sha256": runtime_digest(snapshot)})
    plan["plan_id"] = shared.digest(plan)
    shared.atomic_json(output / "plan.json", plan)
    for group in plan["groups"]:
        (output / f"Year{group['year']}").mkdir()
        publish_year(plan, group)
    return plan


def task_spec(plan, group, record):
    key = shared.digest({"plan_id": plan["plan_id"], "year": group["year"], "record": record})
    folder = Path(plan["output"]) / f"Year{group['year']}"
    name = f"{record['method']}_RS{record['seed']}_{record['strategy']}_TS{record['training_steps']}"
    return {"key": key, "settings": group["settings"], "strategy": record["strategy"],
            "params": record["params"], "result_file": str(folder / "results" / f"{name}.json"),
            "execution_log": str(folder / "logs" / f"{name}.out")}


def saved_result(task):
    try:
        result = read_json(Path(task["result_file"]))
    except FileNotFoundError:
        return None
    if result["key"] != task["key"]:
        raise ValueError(f"Checkpoint identity changed: {task['result_file']}")
    return result


def atomic_csv(path, rows, fields):
    temporary = path.with_name(path.name + f".pending-{os.getpid()}")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def publish_year(plan, group):
    folder = Path(plan["output"]) / f"Year{group['year']}"
    benchmark_path = folder / "benchmark.json"
    benchmark = read_json(benchmark_path) if benchmark_path.exists() else None
    settings, rows = group["settings"], []
    for record in group["records"]:
        task = task_spec(plan, group, record)
        result = saved_result(task)
        row = {field: "" for field in FIELDS}
        row.update(record)
        row.update({"training_start": settings["start"], "training_stop": settings["stop"],
                    **{key: settings[key] for key in ("initial_capital", "transaction_cost",
                         "binning", "symbol_list", "t_plus_x")},
                    "params": json.dumps(record["params"], sort_keys=True),
                    "training_score": json.dumps(record["training_score"]),
                    "status": "Pending", "result_file": task["result_file"],
                    "execution_log": task["execution_log"]})
        if result:
            row.update({"status": result["status"], "failure": result.get("failure", ""),
                        "execution_seconds": result["execution_seconds"]})
            row.update({key: result.get("metrics", {}).get(key, "") for key in METRICS})
        if benchmark and benchmark["status"] == "Completed":
            spy = benchmark["metrics"]
            row["spy_return_pct"] = spy["return_pct"]
            if row["status"] == "Completed":
                row["excess_return_pp"] = round(row["return_pct"] - spy["return_pct"], 2)
                row["relative_profit_amount"] = round(row["total_return"] - spy["total_return"], 2)
        rows.append(row)
    atomic_csv(folder / "performances.csv", rows, FIELDS)
    refresh_tables(plan)


def refresh_tables(plan):
    output = Path(plan["output"])
    with (output / "tables.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = []
        for group in plan["groups"]:
            path = output / f"Year{group['year']}/performances.csv"
            if path.exists():
                with path.open(newline="") as stream:
                    rows.extend(csv.DictReader(stream))
        atomic_csv(output / "masterpeng_full_training_performances.csv", rows, FIELDS)
        groups = defaultdict(list)
        for row in rows:
            groups[tuple(row[k] for k in ("year", "strategy", "method", "training_steps"))].append(row)
        means = []
        for key, seeds in sorted(groups.items()):
            complete = [row for row in seeds if row["status"] == "Completed"]
            cell = dict(zip(("year", "strategy", "method", "training_steps"), key))
            cell.update(n_completed=len(complete), n_expected=len(SEEDS))
            for metric in ("return_pct", "excess_return_pp", "max_drawdown", "sharpe_ratio", "buy_trades"):
                values = [float(row[metric]) for row in complete if row[metric] != ""]
                cell["mean_" + metric] = fmean(values) if values else ""
                cell["sem_" + metric] = stdev(values) / math.sqrt(len(values)) if len(values) > 1 else ""
            means.append(cell)
        if means:
            atomic_csv(output / "masterpeng_full_training_means.csv", means, list(means[0]))
        shared.atomic_json(output / "progress.json", {
            "plan_id": plan["plan_id"], "expected": sum(len(g["records"]) for g in plan["groups"]),
            "statuses": dict(Counter(row["status"] for row in rows)),
            "updated_utc": datetime.now(timezone.utc).isoformat()})


def configure_environment(plan, settings):
    shared.configure_environment(settings)
    os.environ.update({"START_TIME": settings["start"], "TRAINING_PERIOD": "9",
        "VALIDATION_PERIOD": "3", "TEST_PERIOD": "18", "FIXED_TRAIN_START": settings["start"],
        "FIXED_TRAIN_STOP": settings["stop"], "FIXED_TRAIN_TC": str(settings["transaction_cost"]),
        "PARAMETER_SEARCH_RANGE_SET": "broad", "DATA_LOADER_MAX_WORKERS": "2",
        "PENGUIN_DATA_CACHE_DIR": plan["data_cache"],
        "PENGUIN_FINALIZED_CACHE_DIR": str(Path(plan["data_cache"]) / "finalized_step1")})


def run_task(task):
    """Save a small result after each replay; market data stays inherited in workers."""
    import penguins
    from run_simulation import run_backtest
    started = time.monotonic()
    settings, name = task["settings"], task["strategy"]
    log_path = Path(task["execution_log"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", buffering=1) as log, redirect_stdout(log), redirect_stderr(log):
        try:
            strategy = penguins.SP500() if name == "SP500" else getattr(penguins, name)(name=name, **task["params"])
            strategy.name = name
            symbols = _SHARED["valid_symbols"]
            traded = getattr(strategy, "TRADED_SYMBOLS", None)
            if traded is not None:
                symbols = sorted(set(symbols).intersection(traded))
            results, _, _, _, _, _ = run_backtest(
                symbols=symbols, start_datetime=shared.report.parse_datetime(settings["start"]),
                end_datetime=shared.report.parse_datetime(settings["stop"]), binning=settings["binning"],
                initial_capital=settings["initial_capital"], transaction_cost=settings["transaction_cost"],
                penguin_classes=[strategy], training_step_allowed=False, collect_trade_details=False,
                backtest_label="full training", t_plus_x=settings["t_plus_x"],
                loaded_data=_SHARED["data"], loaded_valid_symbols=_SHARED["valid_symbols"],
                loaded_price_basis_adjusted=_SHARED["price_basis_adjusted"])
            portfolio, metrics = results[name]
            if not portfolio.value_history or not all(math.isfinite(metrics[key]) for key in METRICS):
                raise ValueError("Empty portfolio history or invalid performance metrics")
            result = {"key": task["key"], "status": "Completed", "metrics": metrics}
            del portfolio, results
        except Exception as error:
            traceback.print_exc()
            result = {"key": task["key"], "status": "Failed", "failure": f"{type(error).__name__}: {error}"}
        result["execution_seconds"] = round(time.monotonic() - started, 3)
        shared.atomic_json(Path(task["result_file"]), result)
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL(None).malloc_trim(0)
    except (AttributeError, OSError):
        pass
    return task["key"]


def execute_year(plan, year, args):
    global _SHARED
    group = next(g for g in plan["groups"] if g["year"] == year)
    folder = Path(plan["output"]) / f"Year{year}"
    with (folder / "year.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if runtime_digest(PROJECT) != plan["code_sha256"]:
            raise ValueError("Runtime source differs from the frozen plan; use code_snapshot's entry point")
        configure_environment(plan, group["settings"])
        tasks = [task_spec(plan, group, r) for r in group["records"]]
        pending = [task for task in tasks if (saved_result(task) or {}).get("status") != "Completed"]
        benchmark = {"key": shared.digest({"plan_id": plan["plan_id"], "benchmark_year": year}),
                     "settings": group["settings"], "strategy": "SP500", "params": {},
                     "result_file": str(folder / "benchmark.json"),
                     "execution_log": str(folder / "logs/SP500.out")}
        if (saved_result(benchmark) or {}).get("status") != "Completed":
            pending.insert(0, benchmark)
        if not pending:
            publish_year(plan, group)
            print(f"Year{year}: all {len(tasks)} evaluations already complete.", flush=True)
            return
        import penguins
        instances = [getattr(penguins, t["strategy"])(**t["params"]) for t in tasks]
        instances.append(penguins.SP500())
        configuration = shared.dataset_configuration(group["settings"], instances)
        shared.atomic_json(folder / "dataset_configuration.json", configuration[-1])
        _SHARED = shared.load_dataset(group["settings"], configuration)
        (folder / "data_quality.txt").write_text(_SHARED["quality_report_text"])
        from run_simulation import _process_memory_mb, _memory_limit_gb
        limit = min(args.memory_gb, _memory_limit_gb() or args.memory_gb)
        count = min(len(pending), shared.worker_count(args.workers, _process_memory_mb() / 1024,
                    limit, args.worker_memory_gb, args.reserve_memory_gb))
        print(f"Year{year}: {len(tasks)} checkpoint evaluations; {len(pending)} pending including SPY; "
              f"{count} workers, one shared dataset.", flush=True)
        del instances
        gc.collect()
        gc.freeze()
        pool = mp.get_context("fork").Pool(count)
        processes = list(pool._pool)
        active, completed, iterator = {}, 0, iter(pending)
        try:
            while completed < len(pending):
                while len(active) < count:
                    task = next(iterator, None)
                    if task is None:
                        break
                    active[task["key"]] = (task, pool.apply_async(run_task, (task,)), time.monotonic())
                for key, (task, future, started) in list(active.items()):
                    if future.ready():
                        if future.get() != key or saved_result(task) is None:
                            raise RuntimeError(f"Invalid completed checkpoint: {key}")
                        completed += 1
                        del active[key]
                        publish_year(plan, group)
                        print(f"Year{year}: finished {completed}/{len(pending)}: "
                              f"{Path(task['result_file']).stem} ({saved_result(task)['status']})", flush=True)
                    elif time.monotonic() - started > args.strategy_timeout:
                        raise TimeoutError(f"Strategy exceeded {args.strategy_timeout}s: {task['execution_log']}")
                if any(process.exitcode is not None for process in processes):
                    raise RuntimeError("An evaluation worker exited unexpectedly; completed results are resumable")
                if active:
                    time.sleep(1)
            pool.close()
            pool.join()
        except BaseException:
            pool.terminate()
            pool.join()
            raise
        finally:
            gc.unfreeze()
            _SHARED = None
            publish_year(plan, group)
        failed = [t for t in [benchmark, *tasks] if (saved_result(t) or {}).get("status") != "Completed"]
        if failed:
            raise RuntimeError(f"Year{year}: {len(failed)} failed evaluations; see CSV failure/log columns")
        shared.atomic_json(folder / "complete.json", {"plan_id": plan["plan_id"], "evaluations": len(tasks)})


def submit(plan_path, launcher):
    plan = read_json(plan_path)
    output = Path(plan["output"])
    with (output / "submission.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        listing = subprocess.check_output(["squeue", "--me", "--noheader", "--format=%i|%j"], text=True)
        jobs = read_json(output / "submitted.json") if (output / "submitted.json").exists() else []
        active_ids = {line.split("|", 1)[0].strip() for line in listing.splitlines()}
        for group in plan["groups"]:
            year = group["year"]
            marker = output / f"Year{year}/complete.json"
            if marker.exists() and read_json(marker).get("plan_id") == plan["plan_id"]:
                print(f"Year{year}: already completed; skipping", flush=True)
                continue
            if any(j["year"] == year and j["job_id"] in active_ids for j in jobs):
                print(f"Year{year}: job already queued/running; skipping", flush=True)
                continue
            command = ["sbatch", "--parsable", "--export=ALL", f"--job-name=MasterPeng_Train_{year}",
                       f"--output={output}/Year{year}/slurm_%j.out", str(launcher),
                       "--manifest", str(plan_path), "--year", str(year)]
            job = subprocess.check_output(command, text=True).strip().split(";")[0]
            jobs.append({"year": year, "job_id": job})
            shared.atomic_json(output / "submitted.json", jobs)
            print(f"Submitted {job}: Year{year}, {len(group['records'])} checkpoint evaluations", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--prepare", type=Path, metavar="OUTPUT_DIRECTORY")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--submit", type=Path, metavar="LAUNCHER")
    parser.add_argument("--year", type=int, choices=YEARS)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--memory-gb", type=float, default=230)
    parser.add_argument("--worker-memory-gb", type=float, default=34)
    parser.add_argument("--reserve-memory-gb", type=float, default=16)
    parser.add_argument("--strategy-timeout", type=float, default=6 * 3600)
    args = parser.parse_args()
    if args.manifest:
        plan = read_json(args.manifest)
        if args.submit:
            submit(args.manifest.resolve(), args.submit.resolve())
        elif args.refresh:
            for group in plan["groups"]:
                publish_year(plan, group)
        elif args.year is not None:
            execute_year(plan, args.year, args)
        else:
            parser.error("--manifest requires --year, --submit, or --refresh")
    else:
        root = args.root.expanduser().resolve()
        plan = prepare(root, args.prepare.expanduser().resolve()) if args.prepare else collect_plan(root)
        for group in plan["groups"]:
            print(f"Year{group['year']}: {len(group['records'])} evaluations; "
                  f"{group['settings']['start']} to {group['settings']['stop']}")
        print(f"Total: {sum(len(g['records']) for g in plan['groups'])} evaluations, plus five SPY benchmarks")
        if args.prepare:
            print(f"Prepared {args.prepare.resolve() / 'plan.json'}")


if __name__ == "__main__":
    main()
