from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import train_trainable_penguins as training
from scripts import plotting
from scripts.training_objective import score_training_candidate


@pytest.mark.parametrize("trial_buys,one_buy_profit,best_buys,expected_scores,expected_penalties", [
    ([0, 1, 20], 10_000, 20, [-150_000, -132_502, -40], [150_000, 142_500, 0]),
    ([0, 1], -20_000, 0, [-150_000, -162_502], [150_000, 142_500]),
])
def test_training_passes_penalized_scores_to_sampler_and_candidate_selection(
    monkeypatch, trial_buys, one_buy_profit, best_buys, expected_scores, expected_penalties,
):
    class ActivityStrategy:
        def __init__(self, buys):
            self.name = "ActivityStrategy"
            self.params = SimpleNamespace(buys=buys)

    sampler_history = []

    def suggest(strategy_class, completed_trials, rng, np_rng):
        sampler_history.append(list(completed_trials))
        return {"buys": trial_buys[len(completed_trials)]}, "test"

    def backtest(**kwargs):
        candidate = kwargs["penguin_classes"][0]
        buys = candidate.params.buys
        profit = one_buy_profit if buys == 1 else 0
        metrics = {
            "buy_trades": buys, "total_trades": buys * 2,
            "total_return": profit, "final_value": 100_000 + profit,
        }
        results = {
            candidate.name: (None, metrics),
            training.SP500().name: (None, {"total_return": 0}),
        }
        return results, {}, [], {}, {}, ""

    monkeypatch.setattr(training, "TRAINING_ITERATIONS", len(trial_buys))
    monkeypatch.setattr(training, "TRAINING_MIN_BUY_TRADES", 20)
    monkeypatch.setattr(training, "TRAINING_RELATIVE_TO", 0)
    monkeypatch.setattr(training, "TRAINING_TRANSACTION_COST", 2.0)
    monkeypatch.setattr(training, "suggest_parameters", suggest)
    monkeypatch.setattr(training, "run_backtest", backtest)
    monkeypatch.setattr(training, "_release_training_trial_memory", lambda: None)

    trained, logs, history, pareto = training._train_trainable_penguins(
        [ActivityStrategy], ["SPY"], [datetime(2024, 1, 2, tzinfo=timezone.utc)],
        "1m", 100_000, 2.0, 1,
    )

    assert trained["ActivityStrategy"]["best_params"] == {"buys": best_buys}
    assert trained["ActivityStrategy"]["best_metrics"]["buy_trades"] == best_buys
    assert trained["ActivityStrategy"]["top_params"][0]["params"] == {"buys": best_buys}
    assert trained["ActivityStrategy"]["validation_params"][0]["params"] == {"buys": best_buys}
    assert [item["objective_value"] for item in history] == expected_scores
    assert sampler_history[-1][-1]["objective_value"] == expected_scores[-2]
    assert [item["activity_penalty"] for item in history] == expected_penalties
    assert pareto["ActivityStrategy"][1]["activity_penalty"] == 142_500
    assert any("activity_penalty=$142,500.00" in line for line in logs)


def test_pareto_zero_score_line_matches_the_penalized_objective(monkeypatch, tmp_path):
    from matplotlib.axes import Axes

    zero_lines = []
    original_plot = Axes.plot

    def capture_plot(self, *args, **kwargs):
        if kwargs.get("label") == "net score = 0":
            zero_lines.append((args[0], args[1]))
        return original_plot(self, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", capture_plot)
    output = tmp_path / "pareto.pdf"
    plotting.create_training_pareto_pdf(
        {"Strategy": [{
            "status": "completed", "trial": 1, "buy_trades": 25,
            "relative_profit_amount": 100, "score": [50, -25, -50],
        }]},
        [], {}, output, transaction_cost=2.0,
        minimum_buy_trades=20, activity_penalty_capital=100_000,
    )

    assert output.is_file()
    assert len(zero_lines) == 1
    buys, profits = zero_lines[0]
    assert buys == [20, 25]
    for count, profit in zip(buys, profits):
        score = score_training_candidate(
            {"buy_trades": count, "total_trades": count * 2, "total_return": profit},
            {}, 2.0, 0, 100_000, minimum_buys=20,
        )
        assert score[0] == pytest.approx(0)
