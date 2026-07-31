from pathlib import Path

import pytest

from config.backtest import get_run_output_dir


def test_get_run_output_dir_reuses_reserved_named_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reserved_dir = tmp_path / "run_log" / "WITH_LOG"
    reserved_dir.mkdir(parents=True)
    monkeypatch.setenv("PENGUIN_RUN_OUTPUT_DIR", str(reserved_dir))

    assert get_run_output_dir(tmp_path, "WITH_LOG") == reserved_dir.resolve()


def test_get_run_output_dir_reuses_named_directory_without_suffix(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run_log" / "WITH_LOG"
    run_dir.mkdir(parents=True)

    assert get_run_output_dir(tmp_path, "WITH_LOG") == run_dir.resolve()


def test_get_run_output_dir_rejects_reserved_directory_outside_run_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reserved_dir = tmp_path / "somewhere_else" / "WITH_LOG"
    monkeypatch.setenv("PENGUIN_RUN_OUTPUT_DIR", str(reserved_dir))

    with pytest.raises(ValueError, match="direct child"):
        get_run_output_dir(tmp_path, "WITH_LOG")
