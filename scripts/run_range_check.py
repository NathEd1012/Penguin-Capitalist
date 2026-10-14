"""Run the complete parameter-search range-check matrix.

The matrix contains one isolated run for every combination of:

* EmperorPenguin, KingPenguin, GentooPenguin, and RockhopperPenguin
* narrow and broad parameter ranges
* CMA-ES, TPE, GP-EI, and GP-UCB search

Each run uses 100 training steps and writes to its own directory below
``run_log/RangeCheck``. Runs are intentionally sequential because each
backtest is memory-intensive.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_SIMULATION = ROOT / "run_simulation.py"
OUTPUT_ROOT = ROOT / "run_log" / "RangeCheck"

PENGUINS = ("EmperorPenguin", "KingPenguin", "GentooPenguin", "RockhopperPenguin")
RANGES = ("broad", "narrow")


@dataclass(frozen=True)
class SearchMode:
    name: str
    sampler: str
    acquisition: str


SEARCH_MODES = (
    SearchMode("cmaes", "cmaes", "ei"),
    SearchMode("tpe", "tpe", "ei"),
    SearchMode("gpei", "gp", "ei"),
    SearchMode("gpucb", "gp", "ucb"),
)


def _job_name(penguin: str, range_set: str, mode: SearchMode) -> str:
    return f"{penguin.removesuffix('Penguin').lower()}_{range_set}_{mode.name}"


def _job_environment(penguin: str, range_set: str, mode: SearchMode) -> dict[str, str]:
    return {
        **os.environ,
        "START_TIME": "2024-01-01 00:00:00",
        "FIXED_TS": "100",
        "ACTIVE_PENGUINS": penguin,
        "PARAMETER_SEARCH_METHOD": "bayesian_rand",
        "PARAMETER_SEARCH_RANGE_SET": range_set,
        "PARAMETER_SEARCH_BAYESIAN_SAMPLER": mode.sampler,
        "PARAMETER_SEARCH_BAYESIAN_ACQUISITION": mode.acquisition,
        "RUN_LOG_NAME": "RangeCheck",
        "PENGUIN_RUN_OUTPUT_DIR": str(OUTPUT_ROOT / _job_name(penguin, range_set, mode)),
        # Keep the training objective benchmark fixed to the S&P 500.
        "FIXED_REL": "SPY",
    }


def _jobs() -> list[tuple[str, str, SearchMode]]:
    return [
        (penguin, range_set, mode)
        for penguin in PENGUINS
        for range_set in RANGES
        for mode in SEARCH_MODES
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the 32 jobs without starting them.",
    )
    args = parser.parse_args()

    if not RUN_SIMULATION.is_file():
        raise FileNotFoundError(f"Could not find simulation entry point: {RUN_SIMULATION}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    jobs = _jobs()
    print(f"Starting {len(jobs)} RangeCheck runs in {OUTPUT_ROOT}", flush=True)

    for index, (penguin, range_set, mode) in enumerate(jobs, start=1):
        job_name = _job_name(penguin, range_set, mode)
        environment = _job_environment(penguin, range_set, mode)
        command = [sys.executable, str(RUN_SIMULATION)]
        print(
            f"[{index}/{len(jobs)}] {job_name}: "
            f"{penguin}, {range_set}, {mode.name}",
            flush=True,
        )

        if args.dry_run:
            continue

        completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
        if completed.returncode != 0:
            print(
                f"RangeCheck job {job_name} failed with exit code "
                f"{completed.returncode}; continuing with the remaining jobs.",
                file=sys.stderr,
                flush=True,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
