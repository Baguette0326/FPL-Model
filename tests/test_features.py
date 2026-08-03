from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from fpl_model.features import _forward_sum, _read_csv_compatible  # noqa: E402
from fpl_model.baseline import evaluate_recency_baseline  # noqa: E402


class FeatureSafetyTests(unittest.TestCase):
    def test_forward_target_uses_next_six_rows_only(self) -> None:
        points = pd.Series([100, 1, 2, 3, 4, 5, 6, 999], dtype=float)
        target = _forward_sum(points, 6)
        self.assertEqual(target.iloc[0], 21)
        self.assertNotEqual(target.iloc[0], points.iloc[0])
        self.assertTrue(pd.isna(target.iloc[2]))

    def test_shifted_rolling_feature_excludes_current_week(self) -> None:
        points = pd.Series([1, 2, 100, 4], dtype=float)
        feature = points.shift(1).rolling(3, min_periods=1).sum()
        self.assertEqual(feature.iloc[2], 3)
        self.assertNotEqual(feature.iloc[2], 103)

    def test_baseline_evaluation_excludes_inactive_players(self) -> None:
        table = pd.DataFrame(
            {
                "season": ["A", "A", "A"],
                "gameweek": [10, 10, 10],
                "minutes_last_6": [540, 360, 0],
                "points_last_6": [30, 10, 0],
                "points_next_6": [28, 12, 0],
            }
        )
        metrics = evaluate_recency_baseline(table)
        self.assertEqual(int(metrics.iloc[0]["rows"]), 2)

    def test_legacy_windows_1252_csv_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            path.write_bytes("name,points\nJosé,10\n".encode("cp1252"))
            frame = _read_csv_compatible(path)
        self.assertEqual(frame.iloc[0]["name"], "José")


if __name__ == "__main__":
    unittest.main()
