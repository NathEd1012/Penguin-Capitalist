"""Shared file handling for standalone analyses of saved run artifacts."""
import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]


def resolve_run_dir(value):
    supplied = Path(value).expanduser()
    candidates = (supplied, PROJECT_DIR / supplied, PROJECT_DIR / "run_log" / supplied)
    for candidate in candidates:
        if candidate.name == "artifacts":
            candidate = candidate.parent
        if (candidate / "artifacts").is_dir():
            return candidate.resolve()
    raise FileNotFoundError(f"Run directory not found: {value}. Supply the full run path or its path below run_log.")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def output_path(run_dir, supplied, filename):
    path = Path(supplied).expanduser() if supplied else run_dir / "artifacts" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
