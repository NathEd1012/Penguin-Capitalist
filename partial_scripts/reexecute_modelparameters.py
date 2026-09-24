"""Re-execute saved trainable parameter sets on a new execution window."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
	sys.path.insert(0, str(PROJECT_DIR))

from backtest.evaluator import Evaluator
from config import ACTIVE_SYMBOL_LIST, BINNING, INITIAL_CAPITAL, SYMBOLS
from penguins import SP500
from run_simulation import _replace_trainable_penguin_params, parse_datetime_string, run_backtest


def _resolve_run_dir(value: str) -> Path:
	path = Path(value).expanduser()
	if not path.is_absolute():
		path = PROJECT_DIR / "run_log" / path
	return path.resolve()


def _load_trials(source_run: Path) -> list:
	parameter_log = source_run / "artifacts" / "json" / "trainable_penguin_parameter_log.json"
	if not parameter_log.is_file():
		raise FileNotFoundError(f"Parameter log not found: {parameter_log}")

	data = json.loads(parameter_log.read_text(encoding="utf-8"))
	trials_by_strategy = {}
	for trial in data.get("trial_history", []):
		if trial.get("status") != "completed" or not trial.get("params"):
			continue
		trials_by_strategy.setdefault(str(trial.get("strategy", "unknown")), []).append(trial)

	return [
		(strategy, trial)
		for strategy, trials in sorted(trials_by_strategy.items())
		for trial in trials
	]


def _select_trials(all_trials: list, limit: int) -> list:
	trials_by_strategy = {}
	for strategy, trial in all_trials:
		trials_by_strategy.setdefault(strategy, []).append(trial)

	selected = []
	for strategy, trials in sorted(trials_by_strategy.items()):
		trials.sort(key=lambda trial: float(trial.get("objective_value", "-inf")), reverse=True)
		selected.extend((strategy, trial) for trial in trials[:limit])
	return selected


def _select_trial(all_trials: list, model: str, parameter_number: int) -> list:
	selected = [
		(strategy, trial)
		for strategy, trial in all_trials
		if strategy == model and int(trial.get("trial", -1)) == parameter_number
	]
	if not selected:
		raise ValueError(
			f"No completed parameter trial {parameter_number} found for model {model!r}"
		)
	return selected


def _strategy_instances(selected_trials: list) -> list:
	instances = []
	for strategy_name, trial in selected_trials:
		strategy_class = getattr(__import__("penguins", fromlist=[strategy_name]), strategy_name, None)
		if strategy_class is None:
			print(f"Skipping unknown strategy in parameter log: {strategy_name}")
			continue
		trial_number = int(trial.get("trial", len(instances) + 1))
		base = strategy_class()
		instance = _replace_trainable_penguin_params(
			base,
			trial["params"],
			name=f"{strategy_name}_Rerun{trial_number:03d}",
		)
		instances.append(instance)

	if not instances:
		raise ValueError("No executable completed parameter trials were found")
	instances.append(SP500())
	return instances


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--source-run", required=True, help="Existing run name or path containing the saved parameter log")
	parser.add_argument("--output-run", required=True, help="Existing run name or path where the rerun report will be saved")
	parser.add_argument("--report-name", default="rerunPDF.pdf", help="PDF filename to add to the output run")
	parser.add_argument("--start", required=True, help="Execution start datetime")
	parser.add_argument("--stop", required=True, help="Execution stop datetime")
	parser.add_argument("--transaction-cost", type=float, required=True)
	parser.add_argument(
		"--parameters-executed",
		type=int,
		help="Run the top N parameter sets per strategy (legacy mode)",
	)
	parser.add_argument("--model", help="Run one exact model from the parameter log")
	parser.add_argument(
		"--parameter-number",
		type=int,
		help="Run one exact trial number for --model",
	)
	args = parser.parse_args()
	if args.parameters_executed is not None and args.parameters_executed < 1:
		raise ValueError("--parameters-executed must be at least 1")
	if (args.model is None) != (args.parameter_number is None):
		raise ValueError("--model and --parameter-number must be provided together")
	if args.parameter_number is not None and args.parameter_number < 1:
		raise ValueError("--parameter-number must be at least 1")
	if args.parameters_executed is None and args.model is None:
		raise ValueError(
		"Provide --model and --parameter-number, or use --parameters-executed"
	)

	start = parse_datetime_string(args.start)
	stop = parse_datetime_string(args.stop)
	if stop <= start:
		raise ValueError("Execution stop must be later than execution start")

	source_run = _resolve_run_dir(args.source_run)
	output_run = _resolve_run_dir(args.output_run)
	report_name = Path(args.report_name).name
	if not report_name.lower().endswith(".pdf"):
		report_name += ".pdf"
	artifacts_dir = output_run / "artifacts"
	artifacts_dir.mkdir(parents=True, exist_ok=True)
	all_trials = _load_trials(source_run)
	if args.model is not None:
		trials = _select_trial(all_trials, args.model, args.parameter_number)
	else:
		trials = _select_trials(all_trials, args.parameters_executed)
	strategies = _strategy_instances(trials)

	print("\n" + "=" * 80)
	print("RERUN CONFIGURATION")
	print("=" * 80)
	print(f"Source Run:                 {source_run}")
	print(f"Output Run:                 {output_run}")
	print(f"Report:                     {output_run / report_name}")
	print(f"Available Completed Trials: {len(all_trials)}")
	if args.model is not None:
		print(f"Model:                      {args.model}")
		print(f"Parameter Number:           {args.parameter_number}")
	else:
		print(f"Parameters Executed:        {args.parameters_executed} per strategy")
	print(f"Selected Parameter Sets:    {len(trials)}")
	print(f"Execution Start (UTC):      {start}")
	print(f"Execution Stop (UTC):       {stop}")
	print(f"Transaction Cost:            ${args.transaction_cost:.2f}")
	print("Training Step Enabled:       false")
	print("=" * 80)
	print(f"Found {len(all_trials)} completed training iteration(s) in {source_run}")
	if args.model is not None:
		print(f"Re-executing {args.model} parameter trial {args.parameter_number}")
	else:
		print(f"Re-executing {len(trials)} parameter set(s) ({args.parameters_executed} per strategy)")
	print(f"Execution window: {start} to {stop}")
	print(f"Execution transaction cost: ${args.transaction_cost:.2f}")
	results, trades_by_bar, timestamps, _, _, quality_report = run_backtest(
		symbols=SYMBOLS,
		start_datetime=start,
		end_datetime=stop,
		binning=BINNING,
		initial_capital=INITIAL_CAPITAL,
		transaction_cost=args.transaction_cost,
		penguin_classes=strategies,
		artifacts_dir=artifacts_dir,
		training_step_allowed=False,
	)

	if quality_report:
		(artifacts_dir / "consistency_warnings.txt").write_text(quality_report + "\n", encoding="utf-8")
	(artifacts_dir / "rerun_parameters.json").write_text(
		json.dumps(
			{
				"source_run": str(source_run),
				"model": args.model,
				"parameter_number": args.parameter_number,
				"parameters_executed": args.parameters_executed,
				"available_completed_iterations": len(all_trials),
				"selected_trials": [trial for _, trial in trials],
			},
			indent=2,
			default=str,
		)
		+ "\n",
		encoding="utf-8",
	)
	Evaluator.save_results(results, None, output_run, trades_by_bar, timestamps, artifacts_dir=artifacts_dir)
	num_bars = len(next(iter(results.values()))[0].value_history)
	plot_path = artifacts_dir / "capital_curves.png"
	Evaluator.plot_capital_curves(results, plot_path, num_bars, BINNING, args.start, args.stop, timestamps, ACTIVE_SYMBOL_LIST)
	Evaluator.generate_pdf_report(
		results, output_run / report_name, plot_path, num_bars, BINNING,
		args.start, args.stop, timestamps, artifacts_dir, ACTIVE_SYMBOL_LIST,
	)
	print(f"Saved rerun report to {output_run / report_name}")


if __name__ == "__main__":
	main()
