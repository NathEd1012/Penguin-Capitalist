"""Run the backtest under cProfile and write readable timing reports."""

from __future__ import annotations

import argparse
import cProfile
import io
import os
import pstats
import runpy
import signal
import sys
import traceback
from pathlib import Path


def _write_report(stats: pstats.Stats, output_path: Path, sort_key: str, limit: int | None) -> None:
    stream = io.StringIO()
    if isinstance(stats, pstats.Stats):
        report_stats = stats
        report_stats.stream = stream
    else:
        report_stats = pstats.Stats(stats, stream=stream)
    report_stats.strip_dirs().sort_stats(sort_key)
    if limit is None:
        report_stats.print_stats()
    else:
        report_stats.print_stats(limit)
    output_path.write_text(stream.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile run_simulation.py with cProfile.")
    parser.add_argument("--script", default="run_simulation.py", help="Script to execute.")
    parser.add_argument(
        "--output-dir",
        default="run_current/artifacts",
        help="Directory for profile.prof and text reports.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Number of functions in the top timing reports.",
    )
    parser.add_argument(
        "--snapshot-seconds",
        type=int,
        default=20,
        help="Write an intermediate raw profile this often; 0 disables snapshots.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only regenerate text reports from an existing profile.prof.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    mpl_config_dir = Path(os.environ.get("MPLCONFIGDIR", "/private/tmp/penguin_mplconfig"))
    xdg_cache_dir = Path(os.environ.get("XDG_CACHE_HOME", "/private/tmp/penguin_xdg_cache"))
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))

    script_path = (repo_root / args.script).resolve()
    raw_profile_path = output_dir / "profile.prof"
    cumulative_report_path = output_dir / "profile_cumulative.txt"
    self_time_report_path = output_dir / "profile_self_time.txt"
    full_report_path = output_dir / "profile_full_cumulative.txt"

    if args.report_only:
        stats = pstats.Stats(str(raw_profile_path))
        _write_report(stats, cumulative_report_path, "cumulative", args.limit)
        _write_report(stats, self_time_report_path, "tottime", args.limit)
        _write_report(stats, full_report_path, "cumulative", None)
        print(f"Top cumulative report: {cumulative_report_path}", flush=True)
        print(f"Top self-time report: {self_time_report_path}", flush=True)
        print(f"Full cumulative report: {full_report_path}", flush=True)
        return 0

    profiler = cProfile.Profile()
    exit_code = 0
    snapshot_active = False
    profiling_enabled = False

    def write_raw_profile() -> None:
        nonlocal snapshot_active, profiling_enabled
        if snapshot_active:
            return

        snapshot_active = True
        was_enabled = profiling_enabled
        try:
            if was_enabled:
                profiler.disable()
                profiling_enabled = False
            profiler.dump_stats(str(raw_profile_path))
        finally:
            if was_enabled:
                profiler.enable()
                profiling_enabled = True
            snapshot_active = False

    def handle_snapshot_signal(signum: int, _frame) -> None:
        write_raw_profile()
        if args.snapshot_seconds > 0:
            signal.setitimer(signal.ITIMER_REAL, args.snapshot_seconds)

    def handle_stop_signal(signum: int, _frame) -> None:
        print(f"\nReceived signal {signum}; writing profiler snapshot before exit.", flush=True)
        write_raw_profile()
        raise SystemExit(128 + signum)

    if args.snapshot_seconds > 0:
        signal.signal(signal.SIGALRM, handle_snapshot_signal)
        signal.setitimer(signal.ITIMER_REAL, args.snapshot_seconds)

    for stop_signal in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(stop_signal, handle_stop_signal)

    profiler.enable()
    profiling_enabled = True
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, int):
            exit_code = exc.code
        else:
            print(exc.code, file=sys.stderr)
            exit_code = 1
    except BaseException:
        traceback.print_exc()
        exit_code = 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if profiling_enabled:
            profiler.disable()
            profiling_enabled = False
        profiler.dump_stats(str(raw_profile_path))
        stats = pstats.Stats(profiler)
        _write_report(stats, cumulative_report_path, "cumulative", args.limit)
        _write_report(stats, self_time_report_path, "tottime", args.limit)
        _write_report(stats, full_report_path, "cumulative", None)
        print(f"\nProfiler raw data: {raw_profile_path}", flush=True)
        print(f"Top cumulative report: {cumulative_report_path}", flush=True)
        print(f"Top self-time report: {self_time_report_path}", flush=True)
        print(f"Full cumulative report: {full_report_path}", flush=True)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
