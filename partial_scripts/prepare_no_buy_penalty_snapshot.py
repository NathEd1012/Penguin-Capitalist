"""Freeze a no-buy-penalty experiment without modifying the live run code."""

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

RUNTIME_DIRECTORIES = ("backtest", "config", "indicators", "market_data", "penguins", "scripts")


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f"Expected one patch target in {path}: {old!r}")
    path.write_text(text.replace(old, new, 1))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_snapshot(project, destination, long_script):
    project, destination = Path(project).resolve(), Path(destination).resolve()
    long_script = Path(long_script).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    for directory in RUNTIME_DIRECTORIES:
        shutil.copytree(project / directory, destination / directory,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    for name in ("run_simulation.py", "requirements.txt"):
        shutil.copy2(project / name, destination / name)
    (destination / "partial_scripts").mkdir()
    plotter = "partial_scripts/plot_training_params_evoution.py"
    shutil.copy2(project / plotter, destination / plotter)
    originals = {str(p.relative_to(destination)): digest(p)
                 for p in destination.rglob("*") if p.is_file()}

    # Zero means no buy-count minimum; the live default remains 20.
    config = destination / "config/training_step.py"
    replace_once(config, 'os.getenv("TRAINING_MIN_BUY_TRADES", "20")',
                 'os.getenv("TRAINING_MIN_BUY_TRADES", "0")')
    replace_once(config, "if TRAINING_MIN_BUY_TRADES < 1:",
                 "if TRAINING_MIN_BUY_TRADES < 0:")
    replace_once(config, "TRAINING_MIN_BUY_TRADES must be positive",
                 "TRAINING_MIN_BUY_TRADES must be nonnegative (0 disables the penalty)")
    replace_once(config,
                 "# Below this buy count, subtract 1.5 times starting capital times the missing-buy fraction.",
                 "# Isolated experiment: 0 disables the low-buy activity penalty.")

    objective = destination / "scripts/training_objective.py"
    replace_once(objective,
                 '    if minimum_buys < 1:\n        raise ValueError("minimum_buys must be positive")',
                 '    if minimum_buys < 0:\n        raise ValueError("minimum_buys must be nonnegative")\n'
                 '    if minimum_buys == 0:\n        return 0.0')
    replace_once(objective,
                 '"""Penalize missing buys linearly, up to 1.5 times starting capital."""',
                 '"""Zero minimum disables the penalty; positive minima retain linear scoring."""')

    training = destination / "scripts/train_trainable_penguins.py"
    replace_once(training,
                 '(linear penalty up to 1.5x capital below this)',
                 '(low-buy activity penalty disabled)')
    # Do not hide zero-buy candidates in the experiment's training plot.
    replace_once(training, "exclude_zero_buy_trials=True,",
                 "exclude_zero_buy_trials=TRAINING_MIN_BUY_TRADES > 0,")
    replace_once(destination / "run_simulation.py",
                 '(linear penalty up to 1.5x capital below this)',
                 '(low-buy activity penalty disabled)')

    # Output validation resolves the same archive root; market data is shared.
    # The launcher waits for existing jobs before allowing this experiment to run.
    for name in ("run_log", "data_cache", ".env"):
        if (project / name).exists():
            (destination / name).symlink_to(project / name,
                                          target_is_directory=(project / name).is_dir())

    runner = destination / "run_long_no_buy_penalty.sh"
    shutil.copy2(long_script, runner)
    replace_once(runner, 'FIXED_TS="${FIXED_TS:-500}"',
                 'set -euo pipefail\n\nFIXED_TS="${FIXED_TS:-500}"')
    replace_once(runner, 'BASE_DIR="/home/hd/hd_hd/hd_qp268/Penguin-Capitalist"',
                 'BASE_DIR="${PENGUIN_SOURCE_DIR:?Frozen experiment source directory is required}"\n'
                 'export TRAINING_MIN_BUY_TRADES=0\n'
                 'export PYTHONDONTWRITEBYTECODE=1\n'
                 'export PYTHONPATH="$BASE_DIR${PYTHONPATH:+:$PYTHONPATH}"')
    replace_once(runner, 'cd /home/hd/hd_hd/hd_qp268/Penguin-Capitalist', 'cd "$BASE_DIR"')
    replace_once(runner, 'source /home/hd/hd_hd/hd_qp268/venvPeng/bin/activate',
                 '# Use the existing Python module; do not modify shared environments.')
    replace_once(runner, 'python -m pip install -q -r requirements.txt',
                 "printf 'Objective: net profit relative to %s; low-buy penalty disabled; source=%s\\n' \"$FIXED_REL\" \"$BASE_DIR\"")

    # Hash explicit copied directories; never traverse the shared cache/archive links.
    hashes = {relative: digest(destination / relative) for relative in originals}
    changed = [relative for relative in originals if hashes[relative] != originals[relative]]
    commit = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_project": str(project), "source_commit": commit,
        "snapshot": str(destination),
        "objective": "net profit relative to FIXED_REL; no low-buy penalty in training or validation",
        "minimum_buy_trades": 0,
        "tie_breaking": "fewer buy trades, then fewer total trades (unchanged)",
        "execution_fees": "included in net profit (unchanged)",
        "modified_files": changed,
        "source_sha256": originals, "snapshot_sha256": hashes,
        "runner_source": str(long_script), "runner_source_sha256": digest(long_script),
        "runner_sha256": digest(runner),
    }
    (destination / "snapshot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--long-script", type=Path, required=True)
    args = parser.parse_args()
    manifest = create_snapshot(args.project, args.destination, args.long_script)
    print(json.dumps({"snapshot": manifest["snapshot"],
                      "modified_files": manifest["modified_files"]}, indent=2))


if __name__ == "__main__":
    main()
