import datetime
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")

from scripts.plotting import _build_ticks_from_timestamps, plot_capital_curves


def test_month_ticks_keep_calendar_label_when_boundary_bar_is_missing():
    timestamps = [
        datetime.datetime(2025, 5, 1, 9, 30),
        datetime.datetime(2025, 5, 31, 16, 0),
        datetime.datetime(2025, 6, 3, 9, 30),
        datetime.datetime(2025, 7, 1, 9, 30),
        datetime.datetime(2025, 7, 31, 16, 0),
        datetime.datetime(2025, 8, 2, 9, 30),
    ]

    _, labels = _build_ticks_from_timestamps(timestamps, len(timestamps))

    assert labels == ["May", "Jun", "Jul", "Aug", "02 Aug 2025"]


def test_plot_capital_curves_uses_date_range_for_x_limits(tmp_path):
    curves = {
        "SP500": [1000.0, 1100.0, 1200.0],
        "Simpler_Penguin": [1010.0, 1115.0, 1225.0],
    }
    timestamps = [
        datetime.datetime(2025, 1, 1, 9, 30),
        datetime.datetime(2025, 1, 2, 9, 30),
        datetime.datetime(2025, 1, 3, 9, 30),
    ]

    with patch("matplotlib.pyplot.xlim") as mock_xlim:
        plot_capital_curves(
            curves,
            tmp_path / "capital_curves.png",
            bar_timestamps=timestamps,
        )

    assert mock_xlim.call_count >= 1
    kwargs = mock_xlim.call_args.kwargs
    assert kwargs["left"] < 60000
    assert kwargs["right"] > 60000
