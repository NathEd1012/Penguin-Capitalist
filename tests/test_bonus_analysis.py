"""Check that standalone bonus plots use complete trades and parameter-only features."""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import numpy as np

from partial_scripts.bonus_analysis import UMAP, histogram


class BuyHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = Path(self.directory.name) / "trades_log.txt"

    def write(self, text):
        self.log.write_text(text, encoding="utf-8")

    def test_repeat_purchases_sum_value_and_ignore_repeated_summaries(self):
        self.write("""EXECUTION DETAILS
At 2025-01-01T10:00:00+00:00:
  Penguin: BUY 10.25 XYZ @ $12.00
  Penguin: BUY 0.125 XYZ @ $13.00
  Penguin: SELL 3 XYZ @ $14.00
  Penguin: BUY 1 ABC @ $150.00
LIQUIDATION TRADES (End)
  Penguin: SELL 7.375 XYZ @ $15.00
STRATEGY SUMMARY
Recent Trades
  Penguin: BUY 10.25 XYZ @ $12.00
""")
        values, orders = histogram.read_buys(self.log, {"Penguin": 3, "NoBuys": 0})
        self.assertEqual(values["Penguin"], {"XYZ": Decimal("124.625"), "ABC": Decimal(150)})
        self.assertEqual(orders["Penguin"], {"XYZ": 2, "ABC": 1})
        self.assertEqual(values["NoBuys"], {})
        self.assertEqual(histogram.ranked_symbols(values["Penguin"])[0][0], "ABC")

    def test_mismatched_buy_counts_reject_incomplete_logs(self):
        self.write("EXECUTION DETAILS\n  Penguin: BUY 10 XYZ @ $12.00\n")
        with self.assertRaisesRegex(ValueError, "parsed 1 BUY orders.*records 2"):
            histogram.read_buys(self.log, {"Penguin": 2})

    def test_recent_trades_alone_are_not_treated_as_full_history(self):
        self.write("STRATEGY SUMMARY\nRecent Trades\n  Penguin: BUY 10 XYZ @ $12.00\n")
        with self.assertRaisesRegex(ValueError, "no complete EXECUTION DETAILS"):
            histogram.read_buys(self.log, {"Penguin": 1})

    def test_malformed_buy_cannot_silently_disappear(self):
        self.write("EXECUTION DETAILS\n  Penguin: BUY unknown XYZ @ $12.00\n")
        with self.assertRaisesRegex(ValueError, "Unrecognized BUY record"):
            histogram.read_buys(self.log)

    def test_zero_buy_strategy_is_retained_without_execution_section(self):
        self.write("STRATEGY SUMMARY\nNo trades\n")
        values, orders = histogram.read_buys(self.log, {"Idle": 0})
        self.assertEqual(values, {"Idle": {}})
        self.assertEqual(orders, {"Idle": {}})

    def test_invalid_execution_price_cannot_produce_a_purchase_value(self):
        for price in ("unknown", "0", "-1"):
            with self.subTest(price=price):
                self.write(f"EXECUTION DETAILS\n  Penguin: BUY 1 XYZ @ ${price}\n")
                with self.assertRaises(ValueError):
                    histogram.read_buys(self.log)


def trial(number, params, buys=20, status="completed", objective=10):
    return {"trial": number, "params": params, "buy_trades": buys,
            "status": status, "objective_value": objective}


class ParameterSpaceTests(unittest.TestCase):
    def test_trials_below_twenty_buys_are_excluded_even_with_a_lower_saved_minimum(self):
        history = [trial(1, {"a": 999}, buys=0), trial(2, {"a": 888}, buys=1),
                   trial(3, {"a": 777}, buys=19), trial(4, {"a": 1}, buys=20),
                   trial(5, {"a": 2}, buys=21)]
        selected, _, details = UMAP.prepare_trials(history, 0)
        self.assertEqual([entry["trial"] for entry in selected], [4, 5])
        self.assertEqual(details["bounds"]["a"], [1, 2])

    def test_activity_filter_scaling_and_performance_exclusion(self):
        history = [
            trial(2, {"small": 4, "large": 1000, "fixed": 7}, objective=-10000),
            trial(1, {"small": 2, "large": 100, "fixed": 7}, objective=20000),
            trial(3, {"small": 999, "large": 99999, "fixed": 7}, buys=19),
            trial(4, {"small": 999, "large": 99999, "fixed": 7}, status="failed"),
        ]
        selected, values, details = UMAP.prepare_trials(history, 20)
        self.assertEqual([entry["trial"] for entry in selected], [1, 2])
        self.assertEqual(details["varying_parameters"], ["large", "small"])
        np.testing.assert_allclose(values, [[0, 0], [1, 1]])
        self.assertEqual(details["bounds"]["large"], [100, 1000])

    def test_inconsistent_parameter_schema_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different parameter schema"):
            UMAP.prepare_trials([trial(1, {"a": 1}), trial(2, {"b": 1})], 20)

    def test_nonfinite_parameters_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            UMAP.prepare_trials([trial(1, {"a": np.nan})], 20)

    def test_too_few_distinct_configurations_have_no_embedding(self):
        for values in (np.empty((0, 0)), np.array([[0], [1]]),
                       np.array([[0], [0], [1]]), np.empty((3, 0))):
            with self.subTest(shape=values.shape):
                self.assertEqual(UMAP.embed_parameters(values), (None, None))

    def test_no_eligible_trials_keep_valid_empty_feature_matrix(self):
        selected, values, details = UMAP.prepare_trials([trial(1, {"a": 1}, buys=0)], 20)
        self.assertEqual(selected, [])
        self.assertEqual(values.shape, (0, 0))
        self.assertEqual(details["varying_parameters"], [])


if __name__ == "__main__":
    unittest.main()
