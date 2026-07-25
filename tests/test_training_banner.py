import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_simulation import _format_runtime_configuration_banner


def test_runtime_banner_includes_training_configuration() -> None:
    banner = _format_runtime_configuration_banner(
        start_datetime_utc="2025-01-01 00:00:00+00:00",
        end_datetime_utc="2026-07-01 00:00:00+00:00",
        binning="1m",
        initial_capital=100000.0,
        transaction_cost=2.0,
        symbols=["AAPL", "MSFT"],
        active_symbol_list="LIST_5",
        training_step_enabled=True,
        training_relative_to="SPY",
        training_iterations=10,
        training_subset_stocks=30,
        training_subset_months=2,
        training_transaction_cost=5.0,
        training_random_seed=42,
        training_start_datetime_utc="2024-01-01 00:00:00+00:00",
        training_end_datetime_utc="2025-01-01 00:00:00+00:00",
    )

    assert "TRAINING CONFIGURATION" in banner
    assert "Training Step Enabled:" in banner
    assert "Training Steps:" in banner
    assert "Training Transaction Cost:" in banner
    assert "Training Start (UTC):" in banner
    assert "Training End (UTC):" in banner
