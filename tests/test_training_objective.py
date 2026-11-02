import pytest

from scripts.training_objective import (
    activity_penalty,
    score_training_candidate,
    training_profit_amount,
)


def metrics(buys, profit=0):
    return {"buy_trades": buys, "total_trades": 2 * buys, "total_return": profit}


def score(buys, profit=0, benchmark_profit=0, relative_to="SPY", capital=100_000):
    return score_training_candidate(
        metrics(buys, profit),
        {"total_return": benchmark_profit},
        2.0,
        relative_to,
        capital,
        minimum_buys=20,
    )


@pytest.mark.parametrize("buys,penalty", [
    (0, 150_000), (1, 142_500), (5, 112_500), (10, 75_000),
    (19, 7_500), (20, 0), (21, 0), (100, 0),
])
def test_activity_penalty_has_the_agreed_magnitude(buys, penalty):
    assert activity_penalty(buys, 100_000, 20) == penalty


def test_a_single_buy_does_not_escape_the_inactivity_penalty():
    assert score(0)[0] == -150_000
    assert score(1)[0] == -142_502
    assert score(5)[0] == -112_510
    assert score(10)[0] == -75_020


def test_twenty_buys_removes_only_the_activity_penalty():
    assert score(19, profit=5_000, benchmark_profit=1_000) == (-3_538, -19, -38)
    assert score(20, profit=5_000, benchmark_profit=1_000) == (3_960, -20, -40)
    assert score(21, profit=5_000, benchmark_profit=1_000) == (3_958, -21, -42)


def test_profitable_but_inactive_candidate_is_ranked_below_an_active_candidate():
    assert score(20, profit=0) > score(1, profit=10_000)
    assert score(20, profit=0) > score(5, profit=10_000)


@pytest.mark.parametrize("benchmark_profit,expected", [
    (10_000, -160_000), (0, -150_000), (-10_000, -140_000),
])
def test_zero_buys_has_full_penalty_and_correct_benchmark_direction(benchmark_profit, expected):
    assert score(0, benchmark_profit=benchmark_profit)[0] == expected


@pytest.mark.parametrize("relative_to", [0, "0", None, False])
def test_absolute_mode_does_not_include_benchmark_profit(relative_to):
    assert score(5, profit=2_000, benchmark_profit=10_000, relative_to=relative_to)[0] == -110_510


def test_activity_penalty_scales_with_capital():
    assert activity_penalty(5, 10_000, 20) == 11_250
    assert score(0, capital=10_000)[0] == -15_000


def test_configured_minimum_changes_when_the_penalty_disappears():
    assert activity_penalty(20, 100_000, 40) == 75_000
    assert activity_penalty(40, 100_000, 40) == 0


@pytest.mark.parametrize("minimum", [0, -1])
def test_nonpositive_minimum_is_rejected(minimum):
    with pytest.raises(ValueError, match="minimum_buys must be positive"):
        activity_penalty(0, 100_000, minimum)


def test_reported_profit_is_separate_from_the_activity_penalty():
    assert training_profit_amount(metrics(0), {"total_return": 10_000}, "SPY") == -10_000
    assert training_profit_amount(metrics(1, 2_000), {"total_return": 500}, "SPY") == 1_500


def test_legacy_metrics_without_buy_count_still_receive_a_penalty():
    result = score_training_candidate(
        {"total_trades": 5, "total_return": 0}, {}, 2.0, 0, 100_000,
        minimum_buys=20,
    )
    assert result == (-112_510, -5, -5)
