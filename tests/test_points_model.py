from __future__ import annotations

import unittest

import pandas as pd

from fpl_model.points_model import POINTS_FEATURE_COLUMNS, _predict_points


class PointsModelTests(unittest.TestCase):
    def test_features_exclude_current_outcomes_and_targets(self) -> None:
        forbidden = {"total_points", "points_next_1", "minutes_next_1"}
        self.assertTrue(forbidden.isdisjoint(POINTS_FEATURE_COLUMNS))

    def test_prediction_is_zero_for_blank_and_can_be_negative(self) -> None:
        class FixedModel:
            def predict(self, features):
                return [-10.0] * len(features)

        table = pd.DataFrame(
            {column: [0.0, 0.0] for column in POINTS_FEATURE_COLUMNS}
        )
        table["fixtures_next_1"] = [0, 1]
        table["recent_points_baseline"] = [0.0, 2.0]
        prediction = _predict_points(FixedModel(), table)
        self.assertEqual(prediction.tolist(), [0.0, -8.0])


if __name__ == "__main__":
    unittest.main()
