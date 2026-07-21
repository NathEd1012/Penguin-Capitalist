import random
import unittest

from backtest.portfolio import Portfolio
from run_simulation import (
    _sample_trainable_params,
    _suggest_bayesian_trainable_params,
    _trainable_parameter_space,
)
from penguins.TrainablePenguin1 import TrainablePenguin1
from penguins.TrainablePenguin2 import TrainablePenguin2
from penguins.TrainablePenguin3 import TrainablePenguin3
from penguins.TrainablePenguin4 import TrainablePenguin4
from penguins.TrainablePenguin5 import TrainablePenguin5
from penguins.trainable_signals import (
    average_relative_strength_return,
    is_volume_explosion,
)


class TrainableSignalTests(unittest.TestCase):
    def test_volume_explosion_compares_current_to_prior_average(self):
        self.assertTrue(is_volume_explosion([100.0] * 20 + [250.0], 20, 2.0))
        self.assertFalse(is_volume_explosion([100.0] * 20 + [199.0], 20, 2.0))

    def test_relative_strength_is_average_change_in_stock_over_spy(self):
        stock = [100.0, 99.0, 98.0, 97.0, 96.0, 95.0]
        spy = [100.0] * 6
        value = average_relative_strength_return(stock, spy, 5)
        self.assertIsNotNone(value)
        self.assertLess(value, 0.0)


class BayesianTrainingSuggestionTests(unittest.TestCase):
    def test_bayesian_suggestion_for_tp4_stays_within_bounds(self):
        strategy_class = TrainablePenguin4
        parameter_space = dict(_trainable_parameter_space(strategy_class))
        observations = []
        for seed, score_value in enumerate((0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5), start=1):
            observations.append(
                {
                    "params": _sample_trainable_params(strategy_class, random.Random(seed)),
                    "score_value": score_value,
                }
            )

        params, proposal_method, acquisition_value = _suggest_bayesian_trainable_params(
            strategy_class,
            random.Random(42),
            observations,
        )

        self.assertEqual(proposal_method, "bayes_expected_improvement")
        self.assertIsNotNone(acquisition_value)
        self.assertEqual(set(params), set(parameter_space))

        for name, value in params.items():
            spec = parameter_space[name]
            self.assertGreaterEqual(value, spec.low)
            self.assertLessEqual(value, spec.high)
            if spec.kind == "int":
                self.assertIsInstance(value, int)


class TrainablePenguinExitTests(unittest.TestCase):
    @staticmethod
    def portfolio_with_position(quantity: int = 7) -> Portfolio:
        portfolio = Portfolio(10_000.0)
        portfolio.positions["AAPL"] = quantity
        portfolio.cost_basis["AAPL"] = 100.0
        return portfolio

    def test_tp1_holds_positions_before_any_exit_logic(self):
        prices = [100.0] * 115 + [101.0, 100.0, 99.0, 98.0, 97.0, 96.0]
        exploding_volumes = {"AAPL": [100.0] * 17 + [250.0, 260.0, 270.0, 280.0, 290.0, 300.0]}

        strategy = TrainablePenguin1()
        strategy.set_market_context({"AAPL": prices}, exploding_volumes)
        strategy._entry_bar_index["AAPL"] = len(prices) - 1

        self.assertEqual(
            strategy.decide("AAPL", prices, 95.0, 96.0, self.portfolio_with_position()),
            ("HOLD", 0),
        )

    def test_tp1_sells_on_stop_loss_take_profit_and_confirmed_volume_reversal(self):
        prices = [100.0] * 115 + [101.0, 100.0, 99.0, 98.0, 97.0, 96.0]
        exploding_volumes = {"AAPL": [100.0] * 17 + [250.0, 260.0, 270.0, 280.0, 290.0, 300.0]}

        scenarios = (
            ("stop_loss", 95.0, 96.0, ("SELL", 7)),
            ("take_profit", 109.0, 110.0, ("SELL", 7)),
            ("volume_reversal", 95.0, 96.0, ("SELL", 7)),
        )

        for label, bid, ask, expected in scenarios:
            with self.subTest(case=label):
                strategy = TrainablePenguin1()
                strategy.set_market_context({"AAPL": prices}, exploding_volumes)
                strategy._entry_bar_index["AAPL"] = len(prices) - 6
                portfolio = self.portfolio_with_position()

                if label == "take_profit":
                    portfolio.cost_basis["AAPL"] = 100.0
                elif label == "stop_loss":
                    portfolio.cost_basis["AAPL"] = 100.0

                self.assertEqual(
                    strategy.decide("AAPL", prices, bid, ask, portfolio),
                    expected,
                )

    def test_tp5_matches_tp1_refined_exit_behavior(self):
        prices = [100.0] * 115 + [101.0, 100.0, 99.0, 98.0, 97.0, 96.0]
        volumes = {"AAPL": [100.0] * 17 + [250.0, 260.0, 270.0, 280.0, 290.0, 300.0]}

        strategy = TrainablePenguin5()
        strategy.set_market_context({"AAPL": prices}, volumes)
        strategy._entry_bar_index["AAPL"] = len(prices) - 6

        self.assertEqual(
            strategy.decide("AAPL", prices, 95.0, 96.0, self.portfolio_with_position()),
            ("SELL", 7),
        )

    def test_tp2_holds_before_exit_logic(self):
        prices = [100.0] * 120
        volumes = {"AAPL": [100.0] * 23}

        strategy = TrainablePenguin2()
        strategy.set_market_context({"AAPL": prices}, volumes)
        strategy._entry_bar_index["AAPL"] = len(prices) - 1

        self.assertEqual(
            strategy.decide("AAPL", prices, 99.0, 101.0, self.portfolio_with_position()),
            ("HOLD", 0),
        )

    def test_tp2_sells_on_stop_loss_take_profit_and_confirmed_volume_reversal(self):
        scenarios = (
            (
                "stop_loss",
                [100.0] * 120,
                {"AAPL": [100.0] * 23},
                95.0,
                96.0,
            ),
            (
                "take_profit",
                [100.0] * 120,
                {"AAPL": [100.0] * 23},
                109.0,
                110.0,
            ),
            (
                "volume_reversal",
                [100.0] * 115 + [101.0, 100.0, 99.0, 98.0, 97.0, 96.0],
                {"AAPL": [100.0] * 17 + [250.0, 260.0, 270.0, 280.0, 290.0, 300.0]},
                95.0,
                96.0,
            ),
        )

        for label, prices, volumes, bid, ask in scenarios:
            with self.subTest(case=label):
                strategy = TrainablePenguin2()
                strategy.set_market_context({"AAPL": prices}, volumes)
                strategy._entry_bar_index["AAPL"] = len(prices) - 6

                self.assertEqual(
                    strategy.decide("AAPL", prices, bid, ask, self.portfolio_with_position()),
                    ("SELL", 7),
                )

    def test_tp3_and_tp4_sell_only_when_stock_underperforms_spy(self):
        spy = [100.0] * 120
        underperforming = [100.0] * 114 + [100.0, 99.0, 98.0, 97.0, 96.0, 95.0]
        outperforming = [100.0] * 114 + [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]

        for strategy_class in (TrainablePenguin3, TrainablePenguin4):
            with self.subTest(strategy=strategy_class.__name__):
                strategy = strategy_class()
                strategy.set_market_context(
                    {"AAPL": underperforming, "SPY": spy},
                    {},
                )
                strategy._entry_bar_index["AAPL"] = len(underperforming) - 6
                self.assertEqual(
                    strategy.decide(
                        "AAPL", underperforming, 94.0, 96.0, self.portfolio_with_position()
                    ),
                    ("SELL", 7),
                )

                strategy.set_market_context(
                    {"AAPL": outperforming, "SPY": spy},
                    {},
                )
                strategy._entry_bar_index["AAPL"] = len(outperforming) - 6
                self.assertEqual(
                    strategy.decide(
                        "AAPL", outperforming, 104.0, 106.0, self.portfolio_with_position()
                    ),
                    ("HOLD", 0),
                )

    def test_tp3_and_tp4_sell_on_stop_loss_and_take_profit_after_hold(self):
        spy = [100.0] * 120
        prices = [100.0] * 114 + [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]

        for strategy_class in (TrainablePenguin3, TrainablePenguin4):
            with self.subTest(strategy=strategy_class.__name__):
                strategy = strategy_class()
                strategy.set_market_context({"AAPL": prices, "SPY": spy}, {})
                strategy._entry_bar_index["AAPL"] = len(prices) - 6

                stop_loss_portfolio = self.portfolio_with_position()
                self.assertEqual(
                    strategy.decide("AAPL", prices, 95.0, 96.0, stop_loss_portfolio),
                    ("SELL", 7),
                )

                strategy = strategy_class()
                strategy.set_market_context({"AAPL": prices, "SPY": spy}, {})
                strategy._entry_bar_index["AAPL"] = len(prices) - 6

                take_profit_portfolio = self.portfolio_with_position()
                self.assertEqual(
                    strategy.decide("AAPL", prices, 109.0, 110.0, take_profit_portfolio),
                    ("SELL", 7),
                )

    def test_tp3_uses_adx_for_entry_and_sizing(self):
        prices = [100.0] * 29 + [90.0]
        spy = [100.0] * 30
        strategy = TrainablePenguin3()
        strategy.set_market_context({"AAPL": prices, "SPY": spy}, {})

        action, quantity = strategy.decide(
            "AAPL",
            prices,
            bid=89.0,
            ask=91.0,
            portfolio=Portfolio(10_000.0),
        )

        self.assertEqual(action, "BUY")
        self.assertGreater(quantity, 0)
        self.assertTrue(hasattr(strategy.params, "adx_threshold"))
        self.assertFalse(hasattr(strategy, "_trend_quality"))


if __name__ == "__main__":
    unittest.main()
