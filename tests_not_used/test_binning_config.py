import pytest

from config.backtest import _parse_binning


@pytest.mark.parametrize("value", ["1m", "5m", "15m", "1h", "1d", " 15M "])
def test_parse_binning_normalizes_supported_values(value: str) -> None:
    assert _parse_binning(value) in {"1m", "5m", "15m", "1h", "1d"}


def test_parse_binning_rejects_unsupported_values() -> None:
    with pytest.raises(ValueError, match="Unsupported BINNING"):
        _parse_binning("30m")
