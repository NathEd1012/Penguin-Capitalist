"""Cache Step 1 results, with optional reuse of a saved input-data snapshot."""
import hashlib
import gzip
import json
import os
import pickle
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from backtest.data_cleaning import CleaningPolicy, pricing_symbols

from scripts.data_fixes.corporate_actions import (
    PRICE_ADJUSTMENT_POLICY_VERSION,
    corporate_action_registry_fingerprint,
)

CACHE_VERSION = 5


def _datetime_text(value: datetime) -> str:
    return value.isoformat()


def _configuration(
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    binning: str,
    cache_start_date: Optional[datetime],
    training_start_date: Optional[datetime],
    training_end_date: Optional[datetime],
    validation_start_date: Optional[datetime],
    validation_end_date: Optional[datetime],
    warmup_bars: int,
    prefilter_stale_symbols: bool,
    enable_data_quality_checks: bool,
    symbol_list_name: Optional[str],
) -> dict:
    raw_dir = Path(os.environ.get("PENGUIN_DATA_CACHE_DIR", Path(__file__).resolve().parents[1] / "data_cache")).expanduser().resolve()
    raw_files = {}
    for symbol in pricing_symbols(symbols):
        path = raw_dir / f"{symbol}_{binning}.parquet"
        try:
            stat = path.stat()
            raw_files[symbol] = (stat.st_size, stat.st_mtime_ns)
        except FileNotFoundError:
            raw_files[symbol] = None
    return {
        "raw_directory": str(raw_dir),
        "raw_files": raw_files,
        "cleaning_policy": CleaningPolicy.from_environment().configuration(),
        "cache_version": CACHE_VERSION,
        "symbols": sorted(symbols),
        "start_date": _datetime_text(cache_start_date or start_date),
        "end_date": _datetime_text(end_date),
        "binning": binning,
        "training_start_date": _datetime_text(training_start_date) if training_start_date else None,
        "training_end_date": _datetime_text(training_end_date) if training_end_date else None,
        "validation_start_date": _datetime_text(validation_start_date) if validation_start_date else None,
        "validation_end_date": _datetime_text(validation_end_date) if validation_end_date else None,
        "warmup_bars": warmup_bars,
        "prefilter_stale_symbols": prefilter_stale_symbols,
        "enable_data_quality_checks": enable_data_quality_checks,
        "symbol_list_name": symbol_list_name or "custom",
        "ignore_corporate_actions": os.environ.get(
            "IGNORE_CORPORATE_ACTIONS", ""
        ).lower()
        in ("1", "true", "yes"),
        "corporate_action_registry_fingerprint": corporate_action_registry_fingerprint(),
        "price_adjustment_policy": PRICE_ADJUSTMENT_POLICY_VERSION,
    }


def _path(
    cache_dir: Path,
    configuration: dict,
) -> Path:
    encoded = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    start = configuration["start_date"][2:4]
    end = configuration["end_date"][2:4]
    list_name = "".join(
        character
        for character in configuration["symbol_list_name"]
        if character.isalnum() or character in "-_"
    )
    if list_name.upper().startswith("LIST_"):
        list_name = f"List{list_name[5:]}"
    filename = (
        f"From{start}_{configuration['binning']}_{list_name}_To{end}_"
        f"{digest[:10]}.pkl.gz"
    )
    return cache_dir / filename


class _MetadataComplete(Exception):
    pass


class _MetadataReader(pickle.Unpickler):
    def find_class(self, module, name):
        # Configuration contains only builtins and precedes the prepared bars.
        # Stop before reconstructing arrays/objects from a multi-GB snapshot.
        raise _MetadataComplete


def _stored_configuration(path: Path) -> Optional[dict]:
    try:
        with gzip.open(path, "rb") as handle:
            reader = _MetadataReader(handle)
            try:
                reader.load()
            except _MetadataComplete:
                pass
            for value in reader.memo.copy().values():
                if isinstance(value, dict) and {"cache_version", "raw_files", "symbols", "start_date"} <= value.keys():
                    return value
    except (OSError, ValueError, pickle.PickleError, EOFError, AttributeError):
        pass
    return None


def _same_snapshot_settings(saved: dict, requested: dict) -> bool:
    # Snapshot mode freezes the saved data. Dates, symbols and processing rules
    # must still match; raw-file changes do not replace that saved experiment input.
    return ({key: value for key, value in saved.items() if key != "raw_files"}
            == {key: value for key, value in requested.items() if key != "raw_files"})


def _snapshot_path(cache_dir: Path, configuration: dict) -> Optional[Path]:
    candidates = sorted(cache_dir.glob("*.pkl.gz"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
    for path in candidates:
        saved = _stored_configuration(path)
        if saved is not None and _same_snapshot_settings(saved, configuration):
            return path
    return None


def load(
    cache_dir: Path,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    binning: str,
    cache_start_date: Optional[datetime] = None,
    training_start_date: Optional[datetime] = None,
    training_end_date: Optional[datetime] = None,
    validation_start_date: Optional[datetime] = None,
    validation_end_date: Optional[datetime] = None,
    warmup_bars: int = 1000,
    prefilter_stale_symbols: bool = True,
    enable_data_quality_checks: bool = True,
    refresh_cache: bool = False,
    symbol_list_name: Optional[str] = None,
    reuse_saved_snapshot: bool = False,
) -> Optional[dict]:
    """Load exact inputs, or explicitly reuse saved data with matching settings.

    Snapshot reuse ignores subsequent raw-file changes, preserving the saved
    experiment input. refresh_cache=True always bypasses both lookup modes.
    """
    configuration = _configuration(
        symbols,
        start_date,
        end_date,
        binning,
        cache_start_date,
        training_start_date,
        training_end_date,
        validation_start_date,
        validation_end_date,
        warmup_bars,
        prefilter_stale_symbols,
        enable_data_quality_checks,
        symbol_list_name,
    )
    if refresh_cache:
        return None
    cache_path = _path(cache_dir, configuration)
    if not cache_path.is_file() and reuse_saved_snapshot:
        cache_path = _snapshot_path(cache_dir, configuration)
        if cache_path is None:
            return None
    try:
        with gzip.open(cache_path, "rb") as handle:
            cache = pickle.load(handle)
        if (
            not isinstance(cache, dict)
            or not isinstance(cache.get("configuration"), dict)
            or not (cache["configuration"] == configuration or (
                reuse_saved_snapshot and _same_snapshot_settings(cache["configuration"], configuration)
            ))
            or not isinstance(cache.get("result"), dict)
        ):
            return None
        if cache["configuration"] != configuration:
            print(f"  Reusing finalized Step 1 snapshot: {cache_path.name}; raw-cache changes are excluded from this run's saved inputs.")
        return cache["result"]
    except (OSError, ValueError, pickle.PickleError, EOFError, AttributeError):
        return None


def save(
    cache_dir: Path,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    binning: str,
    result: dict,
    cache_start_date: Optional[datetime] = None,
    training_start_date: Optional[datetime] = None,
    training_end_date: Optional[datetime] = None,
    validation_start_date: Optional[datetime] = None,
    validation_end_date: Optional[datetime] = None,
    warmup_bars: int = 1000,
    prefilter_stale_symbols: bool = True,
    enable_data_quality_checks: bool = True,
    refresh_cache: bool = False,
    symbol_list_name: Optional[str] = None,
) -> None:
    """Atomically save a finalized Step 1 result and its configuration."""
    configuration = _configuration(
        symbols,
        start_date,
        end_date,
        binning,
        cache_start_date,
        training_start_date,
        training_end_date,
        validation_start_date,
        validation_end_date,
        warmup_bars,
        prefilter_stale_symbols,
        enable_data_quality_checks,
        symbol_list_name,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = _path(cache_dir, configuration)
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=cache_dir,
            prefix=f".{cache_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as data_file:
            with gzip.GzipFile(fileobj=data_file, mode="wb", compresslevel=6) as compressed:
                pickle.dump(
                    {"configuration": configuration, "result": result},
                    compressed,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            temporary_path = Path(data_file.name)
        os.replace(temporary_path, cache_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
