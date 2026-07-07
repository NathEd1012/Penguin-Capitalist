"""Save current run artifacts to a named folder under run_interesting/.

Usage examples:
  python n_save.py --abcd
  python n_save.py abcd
	python n_save.py --rep abcd
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _validate_name(name: str) -> str:
	run_name = name.strip()
	if not run_name:
		raise ValueError("Name is empty.")

	allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
	if any(ch not in allowed for ch in run_name):
		raise ValueError("Name may only contain letters, numbers, '-' and '_'.")

	return run_name


def _parse_args(argv: list[str]) -> tuple[str, str]:
	"""Return (mode, name), where mode is 'snapshot' or 'report'."""
	if len(argv) < 2:
		raise ValueError("Missing arguments. Examples: python n_save.py abcd | python n_save.py --rep abcd")

	if argv[1] == "--rep":
		if len(argv) < 3:
			raise ValueError("Missing report name. Example: python n_save.py --rep abcd")
		return "report", _validate_name(argv[2])

	raw = argv[1].strip()
	if raw.startswith("--"):
		raw = raw[2:]
	return "snapshot", _validate_name(raw)


def _collect_files(run_current_dir: Path) -> list[Path]:
	files: list[Path] = []

	report_file = run_current_dir / "report.pdf"
	if report_file.exists():
		files.append(report_file)

	# Collect PDF artifacts too, including training Pareto plots and any future reports.
	files.extend(sorted(run_current_dir.rglob("*.pdf")))

	# Collect json/txt files from run_current (including nested artifacts folder).
	files.extend(sorted(run_current_dir.rglob("*.json")))
	files.extend(sorted(run_current_dir.rglob("*.txt")))

	# Remove potential duplicates while preserving order.
	deduped: list[Path] = []
	seen = set()
	for file_path in files:
		resolved = str(file_path.resolve())
		if resolved not in seen:
			seen.add(resolved)
			deduped.append(file_path)

	return deduped


def main() -> int:
	try:
		mode, name = _parse_args(sys.argv)
	except ValueError as exc:
		print(f"Error: {exc}")
		return 1

	project_root = Path(__file__).resolve().parent
	run_current_dir = project_root / "run_current"
	if not run_current_dir.exists():
		print(f"Error: Missing source folder: {run_current_dir}")
		return 1

	destination_root = project_root / "run_interesting"

	if mode == "report":
		report_source = run_current_dir / "report.pdf"
		if not report_source.exists():
			print(f"Error: Missing report file: {report_source}")
			return 1

		destination_root.mkdir(parents=True, exist_ok=True)
		report_target = destination_root / f"{name}.pdf"
		if report_target.exists():
			print(f"Error: Destination already exists: {report_target}")
			return 1

		shutil.copy2(report_source, report_target)
		print(f"Saved report to: {report_target}")
		return 0

	destination_dir = destination_root / name

	if destination_dir.exists():
		print(f"Error: Destination already exists: {destination_dir}")
		return 1

	files_to_copy = _collect_files(run_current_dir)
	if not files_to_copy:
		print("Error: No report/json/txt files found in run_current.")
		return 1

	destination_dir.mkdir(parents=True, exist_ok=False)

	copied = 0
	for source_file in files_to_copy:
		relative = source_file.relative_to(run_current_dir)
		target_file = destination_dir / relative
		target_file.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source_file, target_file)
		copied += 1

	print(f"Saved run snapshot to: {destination_dir}")
	print(f"Copied {copied} file(s).")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
