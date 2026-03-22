#!/usr/bin/env python3
"""Save current run artifacts to a named folder under run_interesting/.

Usage examples:
  python save.py --abcd
  python save.py abcd
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _parse_run_name(argv: list[str]) -> str:
	if len(argv) < 2:
		raise ValueError("Missing run name. Example: python save.py --abcd")

	raw = argv[1].strip()
	if raw.startswith("--"):
		raw = raw[2:]

	run_name = raw.strip()
	if not run_name:
		raise ValueError("Run name is empty. Example: python save.py --abcd")

	allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
	if any(ch not in allowed for ch in run_name):
		raise ValueError("Run name may only contain letters, numbers, '-' and '_'.")

	return run_name


def _collect_files(run_current_dir: Path) -> list[Path]:
	files: list[Path] = []

	report_file = run_current_dir / "report.pdf"
	if report_file.exists():
		files.append(report_file)

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
		run_name = _parse_run_name(sys.argv)
	except ValueError as exc:
		print(f"Error: {exc}")
		return 1

	project_root = Path(__file__).resolve().parent
	run_current_dir = project_root / "run_current"
	if not run_current_dir.exists():
		print(f"Error: Missing source folder: {run_current_dir}")
		return 1

	destination_root = project_root / "run_interesting"
	destination_dir = destination_root / run_name

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
	print(f"Copied files: {copied}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
