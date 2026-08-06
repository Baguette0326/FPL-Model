from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from fpl_model.minutes_model import (  # noqa: E402
    PHASE1_FEATURE_COLUMNS,
    SigmoidCalibrator,
    _predict_residual_minutes,
    prepare_phase1_table,
)


class Phase1PreparationTests(unittest.TestCase):
    def _table(self) -> pd.DataFrame:
        rows = 4
        frame = pd.DataFrame(
            {
                "season": ["A"] * rows,
                "event_sequence": range(1, rows + 1),
                "player_code": [7] * rows,
                "position": ["MID"] * rows,
                "minutes": [0, 90, 30, 0],
                "starts": [0, 1, 0, 0],
                "has_starts_source": [1] * rows,
                "appearance_next_1": [0, 1, 1, 0],
                "start_next_1": [0, 1, 0, 0],
                "minutes_next_1": [0, 90, 30, 0],
                "fixtures_next_1": [1] * rows,
            }
        )
        for feature in (
            "minutes_last_3", "minutes_last_6", "minutes_last_12",
            "points_last_3", "points_last_6", "points_last_12",
            "goals_scored_last_6", "assists_last_6", "bonus_last_6",
            "team_goals_for_last_6", "team_goals_against_last_6",
        ):
            frame[feature] = 0.0
        frame["minutes_last_6"] = [0, 0, 90, 120]
        return frame

    def test_appearance_history_is_shifted(self) -> None:
        result = prepare_phase1_table(self._table())
        self.assertEqual(result["appearances_last_6"].tolist(), [0, 0, 1, 2])

    def test_model_features_exclude_current_outcomes_and_targets(self) -> None:
        forbidden = {"minutes", "starts", "appearance_next_1", "start_next_1"}
        self.assertTrue(forbidden.isdisjoint(PHASE1_FEATURE_COLUMNS))

    def test_invalid_position_fails_closed(self) -> None:
        table = self._table()
        table.loc[0, "position"] = "AM"
        with self.assertRaisesRegex(ValueError, "Unsupported player positions"):
            prepare_phase1_table(table)

    def test_calibrator_keeps_probabilities_bounded(self) -> None:
        calibrated = SigmoidCalibrator().predict([0.0, 0.5, 1.0])
        self.assertTrue(((calibrated > 0) & (calibrated < 1)).all())

    def test_residual_minutes_are_anchored_and_capacity_clipped(self) -> None:
        table = prepare_phase1_table(self._table())

        class FixedResidual:
            def predict(self, features):
                return [20.0] * len(features)

        prediction = _predict_residual_minutes(FixedResidual(), table)
        expected = (table["recent_minutes_baseline"] + 20).clip(upper=90)
        self.assertEqual(prediction.tolist(), expected.tolist())


if __name__ == "__main__":
    unittest.main()
