"""Replay missing training/validation reports with one shared dataset per Slurm job.

Only this analysis entry point and its launcher implement the batching. The main
simulation is imported unchanged. A fixed fork pool evaluates individual winners
across all runs, without nested pools or sending market data through a queue.
"""

import argparse
from collections import OrderedDict
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta, timezone
import fcntl
import gc
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import traceback

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
from partial_scripts import reexecute_training_vs_validation as report

DATA_FIELDS = ("start", "stop", "binning", "symbol_list")
JSON_FILES = ("curves_data.json", "curve_timestamps.json", "metrics_summary.json",
              "equity_jump_attribution.json", "valuation_marks.json")
_SHARED = None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".pending-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def report_complete(run):
    path = run / report.REPORT_NAME
    try:
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                return False
            handle.seek(max(0, path.stat().st_size - 1024))
            return b"%%EOF" in handle.read()
    except OSError:
        return False


def relocate_report(run, run_log):
    """Recover reports written by old, already finished jobs after the move.

    The caller must wait for the old task before invoking this. Never overwrite
    conflicting files, and publish the PDF last so it remains a completion marker.
    """
    try:
        relative = run.relative_to(run_log / "Done_usefull")
    except ValueError:
        return False
    old = run_log / relative
    if old == run or not report_complete(old):
        return False
    sources = [p for p in (old / "artifacts/tra_vs_val").rglob("*") if p.is_file()]
    sources.append(old / report.REPORT_NAME)
    for source in sources:
        target = run / source.relative_to(old)
        if target.exists() and source.read_bytes() != target.read_bytes():
            raise FileExistsError(f"Refusing to overwrite different report artifact: {target}")
    for source in sources:
        target = run / source.relative_to(old)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            source.unlink()  # Identical bytes were verified above.
        else:
            source.rename(target)
    for directory in sorted(old.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if directory.is_dir():
            try:
                directory.rmdir()
            except OSError:
                pass
    try:
        old.rmdir()
    except OSError:
        pass
    print(f"Recovered completed report: {run}", flush=True)
    return True


def plan_groups(run_log, pattern="MasterPeng*"):
    run_log = run_log.expanduser().resolve()
    groups = OrderedDict()
    finished = 0
    runs = report.discover_runs(run_log / "Done_usefull", pattern)
    for run in runs:
        if report_complete(run):
            finished += 1
            continue
        settings = report.execution_settings(run)
        report.select_winners(run)  # Validate every pending input before submission.
        dataset = {field: settings[field] for field in DATA_FIELDS}
        key = digest(dataset)[:16]
        groups.setdefault(key, {"id": key, "dataset": dataset, "runs": []})["runs"].append(str(run))
    return {"version": 1, "run_log": str(run_log), "discovered": len(runs),
            "finished": finished, "groups": list(groups.values())}


def configure_environment(settings):
    os.environ.update({
        "ACTIVE_SYMBOL_LIST": settings["symbol_list"],
        "FIXED_START": settings["start"], "FIXED_STOP": settings["stop"],
        "BINNING": settings["binning"], "T_PLUS_X": str(settings["t_plus_x"]),
        "FIXED_EXEC_TC": str(settings["transaction_cost"]),
        "PENGUIN_PARALLEL": "0", "PENGUIN_WORKERS": "1", "MPLBACKEND": "Agg",
    })


def legacy_dependencies(plan):
    """Wait only on old array tasks whose outputs belong to a pending group."""
    listing = subprocess.check_output([
        "squeue", "--noheader", "--user", os.environ["USER"],
        "--name=tra_vs_val_report,tra_vs_val_group", "--format=%i|%j", "--array",
    ], text=True)
    dependencies = {index: [] for index in range(len(plan["groups"]))}
    by_run = {str(Path(run).resolve()): index for index, group in enumerate(plan["groups"])
              for run in group["runs"]}
    root = Path(plan["run_log"]).resolve()
    for line in listing.splitlines():
        job, name = line.strip().split("|", 1)
        if name == "tra_vs_val_group":
            raise RuntimeError(f"Grouped reports already submitted ({job}); inspect them before submitting again")
        description = subprocess.check_output(["scontrol", "show", "job", "-o", job], text=True)
        match = re.search(r"SubmitLine=(.*?) WorkDir=", description)
        task_match = re.search(r"\bArrayTaskId=(\d+)", description)
        if not match or not task_match:
            raise RuntimeError(f"Cannot identify the run for active legacy report job {job}")
        command = shlex.split(match.group(1))
        manifest = Path(command[command.index("--manifest") + 1])
        old = Path(manifest.read_text().splitlines()[int(task_match.group(1))]).resolve()
        moved = root / "Done_usefull" / old.relative_to(root)
        index = by_run.get(str(moved))
        if index is not None:
            dependencies[index].append(job)
    return dependencies


def submit_plan(plan_path, launcher, max_concurrent):
    plan = report.load_json(plan_path)
    waits = legacy_dependencies(plan)
    submitted = []
    for index, group in enumerate(plan["groups"]):
        dependencies = waits[index][:]
        if index >= max_concurrent:
            dependencies.append(submitted[index - max_concurrent]["job_id"])
        command = ["sbatch", "--parsable", "--export=ALL",
                   "--output=" + str(plan_path.parent / "%j_group.out")]
        if dependencies:
            command.extend(["--dependency=afterany:" + ":".join(dependencies), "--kill-on-invalid-dep=yes"])
        command.extend([str(launcher), "--manifest", str(plan_path), "--group-index", str(index)])
        job = subprocess.check_output(command, text=True).strip().split(";")[0]
        submitted.append({"job_id": job, "group_index": index, "dataset": group["dataset"],
                          "reports": len(group["runs"]), "wait_for": dependencies})
        atomic_json(plan_path.with_suffix(".submitted.json"), submitted)
        print(f"Submitted job {job}: group {index}, {len(group['runs'])} missing reports"
              + (f"; waiting for {', '.join(dependencies)}" if dependencies else ""), flush=True)
    return submitted


def instances(winners):
    import penguins
    result = []
    for name, trial in report.report_entries(winners):
        strategy = getattr(penguins, trial["strategy"])(name=name, **trial["params"])
        strategy.name = name
        result.append(strategy)
    result.append(penguins.SP500())
    return result


def dataset_configuration(settings, all_instances):
    """Match the existing simulation's Step 1 cache/window and preparation policy."""
    import run_simulation as simulation
    from backtest.finalized_data_cache import _configuration
    from backtest.history import binning_to_minutes, history_warmup_bars
    from config import SYMBOL_LISTS
    from config.parameter_search_con import max_period_for_strategies
    from scripts.data_fixes.synthetic_spread_model import DEFAULT_SPREAD_WINDOW

    start, stop = (report.parse_datetime(settings[key]).astimezone(timezone.utc)
                   for key in ("start", "stop"))
    minutes = binning_to_minutes(settings["binning"])
    training_start = simulation.parse_datetime_string(simulation.TRAINING_START_DATE)
    canonical_start = min(start, training_start) - timedelta(minutes=1000 * minutes)
    warmup = max(history_warmup_bars(all_instances,
                 max_period_for_strategies(all_instances)), DEFAULT_SPREAD_WINDOW - 1)
    load_start = min(start - timedelta(minutes=warmup * minutes), canonical_start)
    options = {
        "cache_start_date": canonical_start, "training_start_date": training_start,
        "training_end_date": simulation.parse_datetime_string(simulation.TRAINING_STOP_DATE),
        "validation_start_date": simulation.parse_datetime_string(simulation.VALIDATION_START_DATE),
        "validation_end_date": simulation.parse_datetime_string(simulation.VALIDATION_STOP_DATE),
        "warmup_bars": 1000, "symbol_list_name": settings["symbol_list"],
    }
    symbols = SYMBOL_LISTS[settings["symbol_list"]]
    configuration = _configuration(symbols, load_start, stop, settings["binning"],
                                   **options, prefilter_stale_symbols=True,
                                   enable_data_quality_checks=True)
    return symbols, load_start, stop, options, configuration


def load_dataset(settings, configuration):
    from backtest.data_loader import DataLoader
    from backtest.finalized_data_cache import load
    symbols, start, stop, options, _ = configuration
    cache = Path(os.environ.get("PENGUIN_FINALIZED_CACHE_DIR",
                                PROJECT_DIR / "data_cache/finalized_step1"))
    prepared = load(cache, symbols, start, stop, settings["binning"],
                    **options, reuse_saved_snapshot=True)
    if prepared is None:
        loader = DataLoader()
        data, warning = loader.load_bars(symbols, start, stop, settings["binning"],
                                         enable_data_quality_checks=True)
        prepared = {"data": data, "sparse_warning": warning,
                    "price_basis_adjusted": dict(loader.last_price_basis_adjusted),
                    "quality_report_text": loader.get_quality_report_text()}
    else:
        print("Loaded one finalized data snapshot for the entire dataset group.", flush=True)
    valid, _ = DataLoader.detect_stale_data(prepared["data"])
    prepared["valid_symbols"] = [symbol for symbol in symbols if symbol in valid]
    if not prepared["valid_symbols"]:
        raise RuntimeError("No valid symbols in shared dataset")
    print(f"Shared dataset ready: {len(prepared['valid_symbols'])} tradeable symbols. "
          "Workers inherit it through fork; no per-run loading.", flush=True)
    return prepared


def code_fingerprint():
    paths = [PROJECT_DIR / "run_simulation.py", Path(__file__), Path(report.__file__)]
    for folder in ("backtest", "config", "penguins", "scripts", "market_data"):
        paths.extend((PROJECT_DIR / folder).rglob("*.py"))
    return digest({str(p.relative_to(PROJECT_DIR)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted({p.resolve() for p in paths})})


def make_tasks(records, identity, checkpoint_root):
    tasks = OrderedDict()
    for record in records:
        record["tasks"] = {}
        entries = [("SP500", {"strategy": "SP500", "params": {}})] + report.report_entries(record["winners"])
        for name, trial in entries:
            # Names and source trials do not affect the computation. In particular,
            # all runs with the same execution settings share one SP500 replay.
            spec = {"identity": identity, "settings": record["settings"],
                    "strategy": trial["strategy"], "params": trial["params"]}
            key = digest(spec)
            record["tasks"][name] = key
            tasks.setdefault(key, {**spec, "key": key, "directory": str(checkpoint_root / key)})
    return tasks


def task_complete(task):
    directory = Path(task["directory"])
    try:
        marker = report.load_json(directory / "complete.json")
        return (marker["key"] == task["key"] and
                all((directory / path).stat().st_size == size
                    for path, size in marker["files"].items()) and
                set(marker["files"]) == {f"json/{name}" for name in JSON_FILES} | {"trades_log.txt"})
    except (OSError, ValueError, KeyError, TypeError):
        return False


def run_task(task):
    """Return only a checkpoint key; large portfolios never enter the result pipe."""
    import ctypes
    import penguins
    from backtest.evaluator import Evaluator
    from run_simulation import run_backtest

    gc.collect()
    try:
        ctypes.CDLL(None).malloc_trim(0)
    except (AttributeError, OSError):
        pass
    target = Path(task["directory"])
    staging = target.with_name(target.name + f".pending-{os.getpid()}")
    staging.mkdir(parents=True, exist_ok=True)
    name = task["strategy"]
    settings = task["settings"]
    with (staging / "execution.log").open("w", buffering=1) as log, redirect_stdout(log), redirect_stderr(log):
        try:
            strategy = penguins.SP500() if name == "SP500" else getattr(penguins, name)(name=name, **task["params"])
            strategy.name = name
            def progress(percent, elapsed, remaining, rate):
                print(f"{name}: {percent}% elapsed={elapsed:.0f}s remaining={remaining}", flush=True)
            # This is the same single-strategy call used by the original parallel
            # backtest, including its strategy-specific warmup/history semantics.
            symbols = _SHARED["valid_symbols"]
            traded = getattr(strategy, "TRADED_SYMBOLS", None)
            if traded is not None:
                symbols = sorted(set(symbols).intersection(traded))
            results, trades, timestamps, _, _, _ = run_backtest(
                symbols=symbols, start_datetime=report.parse_datetime(settings["start"]),
                end_datetime=report.parse_datetime(settings["stop"]), binning=settings["binning"],
                initial_capital=settings["initial_capital"], transaction_cost=settings["transaction_cost"],
                penguin_classes=[strategy], training_step_allowed=False, collect_trade_details=True,
                t_plus_x=settings["t_plus_x"], loaded_data=_SHARED["data"],
                loaded_valid_symbols=_SHARED["valid_symbols"],
                loaded_price_basis_adjusted=_SHARED["price_basis_adjusted"], progress_callback=progress,
            )
            if set(results) != {name}:
                raise RuntimeError(f"Missing strategy result: {name}")
            Evaluator.save_results(results, None, staging, trades, timestamps, artifacts_dir=staging)
        except BaseException:
            traceback.print_exc()
            raise
    paths = [staging / "json" / filename for filename in JSON_FILES] + [staging / "trades_log.txt"]
    atomic_json(staging / "complete.json", {"key": task["key"],
                "files": {str(p.relative_to(staging)): p.stat().st_size for p in paths}})
    if target.exists():
        raise FileExistsError(f"Checkpoint already exists: {target}")
    staging.rename(target)
    return task["key"]


def finish_report(record, tasks, quality_report):
    run = record["run"]
    artifacts = run / "artifacts/tra_vs_val"
    artifacts.mkdir(parents=True, exist_ok=True)
    combined = {filename: {} for filename in JSON_FILES}
    with (artifacts / "trades_log.txt").open("w") as trade_log:
        for target_name, key in record["tasks"].items():
            task = tasks[key]
            source = Path(task["directory"])
            for filename in JSON_FILES:
                combined[filename][target_name] = report.load_json(source / "json" / filename)[task["strategy"]]
            trade_log.write(f"\n{'=' * 80}\n{target_name}\n{'=' * 80}\n")
            trade_log.write((source / "trades_log.txt").read_text().replace(task["strategy"], target_name))
    for filename, data in combined.items():
        atomic_json(artifacts / "json" / filename, data)
    if quality_report:
        (artifacts / "consistency_warnings.txt").write_text(quality_report + "\n")
    atomic_json(artifacts / "selection.json", {
        "source_run": str(run), "mode": "reexecute_distinct_winners",
        "execution": record["settings"], "winners": record["winners"],
        "shared_strategy_checkpoints": record["tasks"],
    })
    timestamps = {name: [report.parse_datetime(value) for value in values]
                  for name, values in combined["curve_timestamps.json"].items()}
    temporary = artifacts / "tra_vs_val_report.pending.pdf"
    report.render_report(temporary, record["winners"], record["settings"],
                         combined["curves_data.json"], combined["metrics_summary.json"], timestamps)
    temporary.replace(run / report.REPORT_NAME)
    print(f"Saved {run / report.REPORT_NAME}", flush=True)


def worker_count(requested, parent_gb, limit_gb, worker_gb=34, reserve_gb=16):
    if min(requested, limit_gb, worker_gb) <= 0 or reserve_gb < 0:
        raise ValueError("Invalid worker/memory budget")
    available = limit_gb - parent_gb - reserve_gb
    count = min(requested, int(available // worker_gb))
    if count < 1:
        raise RuntimeError(f"Shared dataset leaves insufficient worker memory ({parent_gb:.1f} GiB parent)")
    return count


def execute_group(plan, index, args):
    global _SHARED
    group = plan["groups"][index]
    cache = Path(plan["run_log"]) / ".tra_vs_val_shared" / group["id"]
    cache.mkdir(parents=True, exist_ok=True)
    # Keep the descriptor open throughout the job; duplicate submissions fail
    # before data loading instead of evaluating the same dataset on two nodes.
    with (cache / "group.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        records = []
        for value in group["runs"]:
            run = Path(value)
            relocate_report(run, Path(plan["run_log"]))
            if report_complete(run):
                print(f"Skipping completed report: {run}", flush=True)
                continue
            winners = report.select_winners(run)
            settings = report.execution_settings(run)
            if {key: settings[key] for key in DATA_FIELDS} != group["dataset"]:
                raise ValueError(f"Dataset changed since submission: {run}")
            if all(winner["same_parameters"] for winner in winners):
                try:
                    curves, metrics, timestamps = report.saved_primary_results(run, winners)
                except (OSError, ValueError, KeyError):
                    pass
                else:
                    artifacts = run / "artifacts/tra_vs_val"
                    artifacts.mkdir(parents=True, exist_ok=True)
                    temporary = artifacts / "tra_vs_val_report.pending.pdf"
                    report.render_report(temporary, winners, settings, curves, metrics, timestamps)
                    atomic_json(artifacts / "selection.json", {"source_run": str(run),
                                "mode": "replot_saved_results", "execution": settings, "winners": winners})
                    temporary.replace(run / report.REPORT_NAME)
                    continue
            records.append({"run": run, "winners": winners, "settings": settings})
        if not records:
            print("All reports in this dataset group are complete.")
            return
        configure_environment(records[0]["settings"])
        all_instances = [instance for record in records for instance in instances(record["winners"])]
        configuration = dataset_configuration(records[0]["settings"], all_instances)
        identity = digest({"configuration": configuration[-1], "code": code_fingerprint()})
        tasks = make_tasks(records, identity, cache)
        completed = {key for key, task in tasks.items() if task_complete(task)}
        pending = [task for key, task in tasks.items() if key not in completed]
        print(f"Dataset {group['dataset']}: {len(records)} reports, {len(tasks)} unique strategies; "
              f"{len(completed)} checkpoints reusable, {len(pending)} to execute.", flush=True)
        quality_report = ""
        pool = None
        try:
            if pending:
                if "fork" not in mp.get_all_start_methods():
                    raise RuntimeError("Shared dataset execution requires fork")
                _SHARED = load_dataset(records[0]["settings"], configuration)
                quality_report = _SHARED["quality_report_text"]
                (cache / "consistency_warnings.txt").write_text(quality_report)
                from run_simulation import _process_memory_mb, _memory_limit_gb
                parent_gb = _process_memory_mb() / 1024
                limit_gb = min(230, args.memory_gb, _memory_limit_gb() or args.memory_gb)
                count = min(len(pending), worker_count(args.workers, parent_gb, limit_gb,
                                                     args.worker_memory_gb, args.reserve_memory_gb))
                print(f"Using {count} strategy workers; parent={parent_gb:.1f} GiB, "
                      f"budget={limit_gb:.0f} GiB, worker estimate={args.worker_memory_gb} GiB, "
                      f"reserve={args.reserve_memory_gb} GiB. Nested parallelism disabled.", flush=True)
                del all_instances
                gc.collect()
                gc.freeze()  # Avoid dirtying inherited data pages during GC scans.
                pool = mp.get_context("fork").Pool(count)
                initial_workers = list(pool._pool)
                active = {}
                iterator = iter(pending)
                # Runs are kept adjacent so reports can be published throughout
                # the job rather than waiting until the entire group finishes.
                while len(completed) < len(tasks):
                    while len(active) < count:
                        task = next(iterator, None)
                        if task is None:
                            break
                        active[task["key"]] = (pool.apply_async(run_task, (task,)), time.monotonic())
                        print(f"Started {task['strategy']} checkpoint={task['key'][:12]}", flush=True)
                    for key, (future, started) in list(active.items()):
                        if future.ready():
                            if future.get() != key or not task_complete(tasks[key]):
                                raise RuntimeError(f"Invalid completed checkpoint: {key}")
                            completed.add(key)
                            del active[key]
                            print(f"Completed {len(completed)}/{len(tasks)} strategies: {key[:12]}", flush=True)
                        elif time.monotonic() - started > args.strategy_timeout:
                            raise TimeoutError(f"Strategy exceeded {args.strategy_timeout}s: {key}")
                    if any(process.exitcode is not None for process in initial_workers):
                        raise RuntimeError("A shared-data worker exited unexpectedly")
                    for record in list(records):
                        if set(record["tasks"].values()) <= completed:
                            finish_report(record, tasks, quality_report)
                            records.remove(record)
                            gc.collect()
                    if active:
                        time.sleep(1)
                pool.close()
                pool.join()
                pool = None
            else:
                quality_path = cache / "consistency_warnings.txt"
                quality_report = quality_path.read_text() if quality_path.exists() else ""
            for record in records:
                finish_report(record, tasks, quality_report)
        finally:
            if pool is not None:
                pool.terminate()
                pool.join()
            _SHARED = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-log", type=Path, default=PROJECT_DIR / "run_log")
    parser.add_argument("--folder-pattern", default="MasterPeng*")
    parser.add_argument("--write-plan", type=Path)
    parser.add_argument("--submit-plan", type=Path)
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--group-index", type=int)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--memory-gb", type=float, default=230)
    parser.add_argument("--worker-memory-gb", type=float, default=34)
    parser.add_argument("--reserve-memory-gb", type=float, default=16)
    parser.add_argument("--strategy-timeout", type=float, default=6 * 3600)
    args = parser.parse_args()
    if args.submit_plan:
        if not args.launcher or args.max_concurrent < 1:
            parser.error("--submit-plan requires --launcher and positive --max-concurrent")
        submit_plan(args.submit_plan.resolve(), args.launcher.resolve(), args.max_concurrent)
        return
    if args.manifest:
        if args.group_index is None:
            parser.error("--manifest requires --group-index")
        plan = report.load_json(args.manifest)
        execute_group(plan, args.group_index, args)
    else:
        plan = plan_groups(args.run_log.expanduser().resolve(), args.folder_pattern)
        print(f"Eligible runs: {plan['discovered']}; completed reports: {plan['finished']}; "
              f"missing reports: {sum(len(g['runs']) for g in plan['groups'])}; "
              f"dataset groups: {len(plan['groups'])}")
        for index, group in enumerate(plan["groups"]):
            print(f"  Group {index}: {group['dataset']} | {len(group['runs'])} missing reports")
        if args.write_plan:
            atomic_json(args.write_plan, plan)
            print(f"Manifest: {args.write_plan}")


if __name__ == "__main__":
    main()
