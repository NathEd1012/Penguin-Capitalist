"""Cache completed Step 1 data loads for exact backtest configurations."""
import hashlib
import json
import os
import pickle
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


CACHE_VERSION = 1


def _datetime_text(value: datetime) -> str:
    return value.isoformat()


def _configuration(
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    binning: str,
    prefilter_stale_symbols: bool,
    enable_data_quality_checks: bool,
    refresh_cache: bool,
) -> dict:
    return {
        "cache_version": CACHE_VERSION,
        "symbols": sorted(symbols),
        "start_date": _datetime_text(start_date),
        "end_date": _datetime_text(end_date),
        "binning": binning,
        "prefilter_stale_symbols": prefilter_stale_symbols,
        "enable_data_quality_checks": enable_data_quality_checks,
        "refresh_cache": refresh_cache,
        "ignore_corporate_actions": os.environ.get(
            "IGNORE_CORPORATE_ACTIONS", ""
        ).lower()
        in ("1", "true", "yes"),
    }


def _paths(
    cache_dir: Path,
    configuration: dict,
) -> Tuple[Path, Path]:
    encoded = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    prefix = cache_dir / f"step1_{digest}"
    return prefix.with_suffix(".json"), prefix.with_suffix(".pkl")


def load(
    cache_dir: Path,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    binning: str,
    prefilter_stale_symbols: bool = True,
    enable_data_quality_checks: bool = True,
    refresh_cache: bool = False,
) -> Optional[dict]:
    """Load a finalized Step 1 result when its configuration matches exactly."""
    configuration = _configuration(
        symbols,
        start_date,
        end_date,
        binning,
        prefilter_stale_symbols,
        enable_data_quality_checks,
        refresh_cache,
    )
    metadata_path, data_path = _paths(cache_dir, configuration)
    try:
        if json.loads(metadata_path.read_text(encoding="utf-8")) != configuration:
            return None
        with data_path.open("rb") as handle:
            result = pickle.load(handle)
        return result if isinstance(result, dict) else None
    except (OSError, ValueError, pickle.PickleError, EOFError, AttributeError):
        return None


def save(
    cache_dir: Path,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    binning: str,
    result: dict,
    prefilter_stale_symbols: bool = True,
    enable_data_quality_checks: bool = True,
    refresh_cache: bool = False,
) -> None:
    """Atomically save a finalized Step 1 result and its configuration."""
    configuration = _configuration(
        symbols,
        start_date,
        end_date,
        binning,
        prefilter_stale_symbols,
        enable_data_quality_checks,
        refresh_cache,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    metadata_path, data_path = _paths(cache_dir, configuration)
    temporary_paths = []
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=cache_dir,
            prefix=f".{metadata_path.name}.",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as metadata_file:
            json.dump(configuration, metadata_file, sort_keys=True, indent=2)
            temporary_paths.append(Path(metadata_file.name))
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=cache_dir,
            prefix=f".{data_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as data_file:
            pickle.dump(result, data_file, protocol=pickle.HIGHEST_PROTOCOL)
            temporary_paths.append(Path(data_file.name))
        os.replace(temporary_paths[0], metadata_path)
        os.replace(temporary_paths[1], data_path)
        temporary_paths.clear()
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
