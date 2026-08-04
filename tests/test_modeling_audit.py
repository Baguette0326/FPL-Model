from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from fpl_model.modeling import audit_modeling_table, purged_training_mask  # noqa: E402


def _valid_table() -> pd.DataFrame:
    rows = 7
    points = pd.Series([1, 2, 3, 4, 5, 6, 7], dtype=float)
    minutes = pd.Series([90, 0, 45, 90, 60, 90, 30], dtype=float)
    starts = pd.Series([1, 0, 0, 1, 1, 1, 0], dtype=float)

    def forward(values: pd.Series, horizon: int) -> pd.Series:
        shifted = pd.concat(
            [values.shift(-step) for step in range(horizon)], axis=1
        )
        return shifted.sum(axis=1, min_count=horizon)

    frame = pd.DataFrame(
        {
            "season": ["A"] * rows,
            "gameweek": range(1, rows + 1),
            "event_sequence": range(1, rows + 1),
            "player_code": [10] * rows,
            "player_event_observed": [1] * rows,
            "prediction_cutoff": pd.date_range("2025-01-08", periods=rows, freq="7D", tz="UTC"),
            "available_at": [pd.NaT]
            + list(pd.date_range("2025-01-01", periods=rows - 1, freq="7D", tz="UTC")),
            "total_points": points,
            "minutes": minutes,
            "starts": starts,
            "has_starts_source": [1] * rows,
            "points_next_1": points,
            "minutes_next_1": minutes,
            "appearance_next_1": minutes.gt(0).astype(int),
            "start_next_1": starts.gt(0).astype(int),
            "points_next_6": forward(points, 6),
            "minutes_next_6": forward(minutes, 6),
            "target_1_observed_event": range(1, rows + 1),
            "target_6_observed_event": range(6, rows + 6),
        }
    )
    frame["points_last_3"] = points.shift(1).rolling(3, min_periods=1).sum().fillna(0)
    frame["minutes_last_6"] = minutes.shift(1).rolling(6, min_periods=1).sum().fillna(0)
    return frame


class PurgedTrainingMaskTests(unittest.TestCase):
    def test_pre_deadline_six_event_target_allows_origin_t_minus_six(self) -> None:
        table = pd.DataFrame(
            {"season": ["A"] * 10, "event_sequence": range(1, 11)}
        )
        mask = purged_training_mask(
            table,
            validation_season="A",
            validation_event_sequence=10,
            horizon=6,
        )
        self.assertEqual(table.loc[mask, "event_sequence"].tolist(), [1, 2, 3, 4])

    def test_season_order_is_not_lexical(self) -> None:
        table = pd.DataFrame(
            {
                "season": ["season-2", "season-10", "season-1"],
                "event_sequence": [1, 1, 1],
            }
        )
        mask = purged_training_mask(
            table,
            validation_season="season-1",
            validation_event_sequence=1,
            horizon=1,
            season_order=["season-2", "season-10", "season-1"],
        )
        self.assertEqual(table.loc[mask, "season"].tolist(), ["season-2", "season-10"])


class ModelingTableAuditTests(unittest.TestCase):
    def test_valid_table_passes(self) -> None:
        audit = audit_modeling_table(_valid_table())
        self.assertTrue(audit.passed, audit.violations)

    def test_current_event_one_week_target_is_recomputed(self) -> None:
        table = _valid_table()
        table.loc[2, "points_next_1"] = table.loc[3, "total_points"]
        audit = audit_modeling_table(table)
        self.assertEqual(audit.violations["incorrect_points_next_1"], 1)

    def test_six_event_target_and_tail_nullness_are_recomputed(self) -> None:
        table = _valid_table()
        table.loc[0, "points_next_6"] += 1
        table.loc[6, "points_next_6"] = 7
        audit = audit_modeling_table(table)
        self.assertEqual(audit.violations["incorrect_points_next_6"], 2)

    def test_unshifted_rolling_feature_is_rejected(self) -> None:
        table = _valid_table()
        table["points_last_3"] = table["total_points"].rolling(3, min_periods=1).sum()
        audit = audit_modeling_table(table)
        self.assertGreater(audit.violations["rolling_feature_mismatch"], 0)

    def test_unobserved_first_or_last_registration_row_is_rejected(self) -> None:
        table = _valid_table()
        table.loc[[0, 6], "player_event_observed"] = 0
        audit = audit_modeling_table(table)
        self.assertEqual(audit.violations["unobserved_registration_bounds"], 2)

    def test_bad_timestamp_and_start_without_appearance_are_rejected(self) -> None:
        table = _valid_table()
        table["available_at"] = table["available_at"].astype(object)
        table.loc[1, "available_at"] = "not-a-time"
        table.loc[1, "start_next_1"] = 1
        audit = audit_modeling_table(table)
        self.assertEqual(audit.violations["invalid_timestamps"], 1)
        self.assertEqual(audit.violations["start_without_appearance"], 1)

    def test_duplicate_player_event_is_rejected(self) -> None:
        table = pd.concat([_valid_table(), _valid_table().iloc[[0]]], ignore_index=True)
        audit = audit_modeling_table(table)
        self.assertEqual(audit.violations["duplicate_player_events"], 1)


if __name__ == "__main__":
    unittest.main()
