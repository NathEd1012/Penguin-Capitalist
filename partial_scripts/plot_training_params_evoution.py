"""Plot trainable-parameter history for a completed run."""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MaxNLocator


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
	sys.path.insert(0, str(PROJECT_DIR))

from config.parameter_search_con import (
	strategy_parameter_space_by_name as configured_parameter_space_by_name,
)


RUN_LOG_NAME = ""
RUN_LOG_DIR = PROJECT_DIR / "run_log"
OUTPUT_NAME = "Param_Evo.pdf"
PARAMETER_LOG_NAME = "trainable_penguin_parameter_log.json"


def find_parameter_log(artifacts_dir: Path) -> Path:
	"""Find the structured parameter log in the run's artifacts directory."""
	candidates = (
		artifacts_dir / "json" / PARAMETER_LOG_NAME,
		artifacts_dir / PARAMETER_LOG_NAME,
	)
	for candidate in candidates:
		if candidate.is_file():
			return candidate
	raise FileNotFoundError(
		f"Could not find {PARAMETER_LOG_NAME} in {artifacts_dir} or {artifacts_dir / 'json'}"
	)


def resolve_artifacts_dir(run_log_name: str) -> Path:
	direct_path = RUN_LOG_DIR / run_log_name / "artifacts"
	if direct_path.is_dir():
		return direct_path

	matches = sorted(RUN_LOG_DIR.glob(f"*/{run_log_name}/artifacts"))
	if len(matches) == 1:
		return matches[0]
	if len(matches) > 1:
		raise RuntimeError(f"Run name is ambiguous; specify its full path: {run_log_name}")
	return direct_path


def load_histories(parameter_log: Path) -> dict[str, list[dict[str, object]]]:
	data = json.loads(parameter_log.read_text(encoding="utf-8"))
	histories: dict[str, list[dict[str, object]]] = {}
	for trial in data.get("trial_history", []):
		if trial.get("status") != "completed" or not trial.get("params"):
			continue
		strategy = str(trial.get("strategy", "unknown"))
		histories.setdefault(strategy, []).append(trial)
	if not histories:
		raise ValueError(f"No completed parameter trials found in {parameter_log}")
	return histories


def best_training_step(trials: list[dict[str, object]]) -> int:
	"""Return the trial number with the highest recorded objective value."""
	completed_with_objective = [
		trial for trial in trials if trial.get("objective_value") is not None
	]
	if not completed_with_objective:
		raise ValueError("No objective values found for completed parameter trials")
	best_trial = max(
		completed_with_objective,
		key=lambda trial: float(trial["objective_value"]),
	)
	return int(best_trial["trial"])


def plot_strategy(strategy: str, trials: list[dict[str, object]]) -> plt.Figure:
	bounds = {
		name: (float(minimum), float(maximum))
		for name, _kind, minimum, maximum in strategy_parameter_space_by_name(strategy)
	}
	parameter_names = sorted(
		{name for trial in trials for name in trial["params"] if name in bounds}
	)
	if not parameter_names:
		raise ValueError(f"No configured parameters found for {strategy}")

	x_values = [int(trial["trial"]) for trial in trials]
	best_step = best_training_step(trials)
	figure, axes = plt.subplots(
		len(parameter_names),
		1,
		figsize=(12, max(3.5 * len(parameter_names), 5)),
		squeeze=False,
		sharex=True,
	)
	axes = axes[:, 0]
	for axis, parameter_name in zip(axes, parameter_names):
		minimum, maximum = bounds[parameter_name]
		y_values = [float(trial["params"][parameter_name]) for trial in trials]
		axis.plot(x_values, y_values, marker="o", linewidth=1.4, markersize=3.5)
		axis.set_title(parameter_name, loc="left", fontsize=10)
		axis.set_ylabel("Value")
		axis.set_ylim(minimum, maximum)
		axis.yaxis.set_major_locator(MaxNLocator(nbins=5))
		axis.xaxis.set_major_locator(MaxNLocator(nbins=8, integer=True))
		axis.axvline(
			best_step,
			color="crimson",
			linestyle="--",
			linewidth=1.2,
			label=f"Best step: {best_step}",
		)
		axis.grid(True, alpha=0.25)

	axes[-1].set_xlabel("Training step")
	axes[0].legend(loc="upper right", fontsize=8)
	figure.suptitle(f"{strategy} training parameter evolution")
	figure.tight_layout()
	return figure


def strategy_parameter_space_by_name(strategy: str):
	"""Resolve a configured strategy name without importing strategy modules."""
	return configured_parameter_space_by_name(strategy)


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"run_log_name",
		nargs="?",
		default=RUN_LOG_NAME or None,
		help="Name below run_log (for example AdvSELL_ALL_TS100_m3s50_TC5_Random).",
	)
	parser.add_argument("--output", type=Path, default=None, help="Output PDF path.")
	args = parser.parse_args()
	if not args.run_log_name:
		parser.error("run_log_name is required")

	artifacts_dir = resolve_artifacts_dir(args.run_log_name)
	parameter_log = find_parameter_log(artifacts_dir)
	output_path = args.output or RUN_LOG_DIR / args.run_log_name / OUTPUT_NAME
	output_path.parent.mkdir(parents=True, exist_ok=True)

	histories = load_histories(parameter_log)
	with PdfPages(output_path) as pdf:
		for strategy, trials in sorted(histories.items()):
			figure = plot_strategy(strategy, trials)
			pdf.savefig(figure, bbox_inches="tight")
			plt.close(figure)

	print(f"Saved {output_path}")


if __name__ == "__main__":
	main()
