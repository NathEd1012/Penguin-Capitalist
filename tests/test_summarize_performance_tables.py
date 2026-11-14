"""Regression checks for seed averages, uncertainty, and missing results."""
import csv
import math
import tempfile
import unittest
from pathlib import Path

from partial_scripts.summarize_performance_tables import read_table, seed_statistics, summarize


def seed_row(seed, value, *, variant=1, status="Completed"):
    return {"strategy": "EmperorPenguin", "variant": str(variant), "year": "2020",
            "method": "random", "seed": str(seed), "status": status,
            "excess_return_pp": str(value)}


class SeedStatisticsTests(unittest.TestCase):
    def test_sample_standard_error_and_small_sample_t_interval(self):
        result = seed_statistics(dict(zip([11, 22, 33, 42, 55], [1, 2, 3, 4, 5])))
        self.assertEqual(result["mean_pp"], 3)
        self.assertAlmostEqual(result["sample_sd_pp"], math.sqrt(2.5))
        self.assertAlmostEqual(result["sem_pp"], math.sqrt(0.5))
        # Student-t df=4 is materially wider than a normal 1.96*SEM interval.
        self.assertAlmostEqual(result["ci95_low_pp"], 1.036756838522439, places=10)
        self.assertAlmostEqual(result["ci95_high_pp"], 4.963243161477561, places=10)
        self.assertEqual(result["quality"], "above_spy")

    def test_missing_seed_changes_denominator_and_degrees_of_freedom(self):
        result = seed_statistics({11: 1, 22: 2, 33: 3, 42: 4})
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["missing_seeds"], [55])
        self.assertEqual(result["mean_pp"], 2.5)
        self.assertAlmostEqual(result["sem_pp"], math.sqrt(5 / 12))
        self.assertAlmostEqual(result["ci95_half_width_pp"], 2.054260256760879, places=9)

    def test_quality_depends_on_confidence_interval_not_mean_sign(self):
        uncertain = seed_statistics({11: -20, 22: -10, 33: 0, 42: 10, 55: 25})
        self.assertGreater(uncertain["mean_pp"], 0)
        self.assertEqual(uncertain["quality"], "unclear")
        self.assertEqual(seed_statistics({11: -5, 22: -4, 33: -3, 42: -2, 55: -1})["quality"], "below_spy")
        self.assertEqual(seed_statistics({11: 0, 22: 0})["quality"], "unclear")

    def test_one_or_no_results_have_no_estimable_error(self):
        for values in [{}, {11: 7}]:
            with self.subTest(values=values):
                result = seed_statistics(values)
                self.assertIsNone(result["sem_pp"])
                self.assertIsNone(result["ci95_low_pp"])
                self.assertEqual(result["quality"], "insufficient")
        self.assertIsNone(seed_statistics({})["mean_pp"])
        self.assertEqual(seed_statistics({11: 7})["mean_pp"], 7)

    def test_nonfinite_values_are_rejected(self):
        for value in [float("nan"), float("inf"), -float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                seed_statistics({11: value})


class TableGroupingTests(unittest.TestCase):
    def test_failed_rows_are_excluded_zero_returns_and_variants_are_preserved(self):
        rows = [seed_row(11, 0), seed_row(22, 10), seed_row(33, "", status="Failed"),
                seed_row(11, 100, variant=2)]
        result = summarize(rows)
        self.assertEqual(len(result), 150)
        first, second = [s for s in result if s["year"] == 2020 and s["method"] == "random"
                         and s["strategy"] == "EmperorPenguin"]
        self.assertEqual((first["mean_pp"], first["n"]), (5, 2))
        self.assertEqual((second["mean_pp"], second["n"]), (100, 1))
        self.assertFalse(any(s["strategy"] == "SP500" for s in result))

    def test_duplicate_seed_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate seed"):
            summarize([seed_row(11, 1), seed_row(11, 2)])

    def test_completed_row_without_a_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no relative return"):
            summarize([seed_row(11, "")])

    def test_failed_row_with_a_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unfinished row"):
            summarize([seed_row(11, 1, status="Failed")])

    def test_csv_input_preserves_missing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            rows = [seed_row(11, 0), seed_row(22, "", status="Failed")]
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
            self.assertEqual(read_table(path), rows)


if __name__ == "__main__":
    unittest.main()
