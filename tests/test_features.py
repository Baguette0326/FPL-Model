from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from fpl_model.features import (  # noqa: E402
    _complete_player_gameweeks,
    _deduplicate_player_fixtures,
    _event_calendar,
    _forward_sum,
    _read_csv_compatible,
    _season_frame,
)
from fpl_model.baseline import evaluate_recency_baseline  # noqa: E402
from fpl_model.modeling import purged_training_mask  # noqa: E402


class FeatureSafetyTests(unittest.TestCase):
    def test_exact_duplicate_player_fixture_is_counted_once(self) -> None:
        frame = pd.DataFrame(
            {
                "GW": [1, 1],
                "element": [7, 7],
                "fixture": [11, 11],
                "minutes": [74, 74],
                "total_points": [5, 5],
            }
        )
        result, removed = _deduplicate_player_fixtures(frame, "A")
        self.assertEqual(len(result), 1)
        self.assertEqual(removed, 1)
        self.assertEqual(result.iloc[0]["minutes"], 74)

    def test_conflicting_duplicate_player_fixture_fails_closed(self) -> None:
        frame = pd.DataFrame(
            {
                "GW": [1, 1],
                "element": [7, 7],
                "fixture": [11, 11],
                "minutes": [74, 75],
                "total_points": [5, 5],
            }
        )
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            _deduplicate_player_fixtures(frame, "A")

    def test_metadata_position_excludes_manager_and_canonicalizes_goalkeeper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            season_root = Path(directory) / "A"
            season_root.mkdir()
            pd.DataFrame(
                {
                    "id": [1, 2],
                    "code": [101, 999],
                    "element_type": [1, 5],
                    "team": [1, 1],
                    "web_name": ["Keeper", "Manager"],
                }
            ).to_csv(season_root / "players_raw.csv", index=False)
            rows = []
            for gameweek, fixture in ((1, 11), (38, 388)):
                for element, position in ((1, "GKP"), (2, "AM")):
                    rows.append(
                        {
                            "GW": gameweek,
                            "element": element,
                            "fixture": fixture,
                            "was_home": True,
                            "kickoff_time": (
                                "2025-08-01T12:00:00Z"
                                if gameweek == 1
                                else "2026-05-20T12:00:00Z"
                            ),
                            "team_h_score": 1,
                            "team_a_score": 0,
                            "position": position,
                            "total_points": 2,
                            "minutes": 90,
                        }
                    )
            pd.DataFrame(rows).to_csv(season_root / "merged_gw.csv", index=False)

            player_week, _, _ = _season_frame(Path(directory), "A")

        self.assertEqual(player_week["name"].unique().tolist(), ["Keeper"])
        self.assertEqual(player_week["position"].unique().tolist(), ["GK"])

    def test_forward_target_uses_next_six_rows_only(self) -> None:
        points = pd.Series([100, 1, 2, 3, 4, 5, 6, 999], dtype=float)
        target = _forward_sum(points, 6)
        self.assertEqual(target.iloc[0], 115)
        self.assertEqual(target.iloc[1], 21)
        self.assertTrue(pd.isna(target.iloc[3]))

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

    def test_disrupted_gameweek_labels_map_to_contiguous_events(self) -> None:
        raw = pd.DataFrame(
            {
                "GW": [1, 2, 39, 40],
                "kickoff_time": [
                    "2019-08-10T12:00:00Z",
                    "2019-08-17T12:00:00Z",
                    "2020-06-17T17:00:00Z",
                    "2020-06-23T17:00:00Z",
                ],
            }
        )
        calendar = _event_calendar(raw, "2019-20")
        self.assertEqual(calendar["event_sequence"].tolist(), [1, 2, 3, 4])
        self.assertEqual(calendar["gameweek"].tolist(), [1, 2, 39, 40])
        self.assertTrue(calendar["disrupted_schedule"].eq(1).all())

    def test_standard_blank_gameweek_is_retained(self) -> None:
        raw = pd.DataFrame(
            {
                "GW": [1, 2, 4, 38],
                "kickoff_time": [
                    "2022-08-06T12:00:00Z",
                    "2022-08-13T12:00:00Z",
                    "2022-09-17T12:00:00Z",
                    "2023-05-28T15:00:00Z",
                ],
            }
        )
        calendar = _event_calendar(raw, "2022-23")
        blank = calendar.loc[calendar["event_sequence"].eq(3)].iloc[0]
        self.assertEqual(blank["gameweek"], 3)
        self.assertFalse(pd.isna(blank["prediction_cutoff"]))

    def test_event_availability_is_after_final_fixture_and_before_next_cutoff(self) -> None:
        raw = pd.DataFrame(
            {
                "GW": [1, 2],
                "kickoff_time": [
                    "2025-08-16T15:00:00Z",
                    "2025-08-23T12:00:00Z",
                ],
            }
        )
        calendar = _event_calendar(raw, "2025-26")
        first = calendar.iloc[0]
        second = calendar.iloc[1]
        self.assertEqual(
            first["event_end_time"], pd.Timestamp("2025-08-16T18:00:00Z")
        )
        self.assertEqual(second["available_at"], first["event_end_time"])
        self.assertLess(second["available_at"], second["prediction_cutoff"])

    def test_player_rows_are_limited_to_observed_registration_window(self) -> None:
        calendar = pd.DataFrame(
            {
                "season": ["A"] * 6,
                "gameweek": range(1, 7),
                "event_sequence": range(1, 7),
                "prediction_cutoff": pd.date_range("2025-01-01", periods=6, tz="UTC"),
                "available_at": pd.date_range("2024-12-31", periods=6, tz="UTC"),
                "event_end_time": pd.date_range("2025-01-01", periods=6, tz="UTC"),
                "disrupted_schedule": [0] * 6,
            }
        )
        frame = pd.DataFrame(
            {
                "season": ["A", "A"],
                "gameweek": [3, 5],
                "event_sequence": [3, 5],
                "player_code": [10, 10],
                "name": ["Player", "Player"],
                "position": ["MID", "MID"],
                "team": ["Club", "Club"],
                "expected_stats_available": [0, 0],
                "has_expected_stats_source": [0, 0],
                "has_starts_source": [0, 0],
                "has_availability_source": [0, 0],
                "has_fixture_strength_source": [0, 0],
                "schema_era": ["core", "core"],
                "disrupted_schedule": [0, 0],
                "total_points": [1, 2],
                "minutes": [10, 20],
                "starts": [None, None],
                "goals_scored": [0, 0],
                "assists": [0, 0],
                "bonus": [0, 0],
                "clean_sheets": [0, 0],
                "saves": [0, 0],
                "yellow_cards": [0, 0],
                "red_cards": [0, 0],
                "expected_goals": [None, None],
                "expected_assists": [None, None],
            }
        )

        completed = _complete_player_gameweeks(frame, calendar)

        self.assertEqual(completed["event_sequence"].tolist(), [3, 4, 5])
        self.assertEqual(completed["player_event_observed"].tolist(), [1, 0, 1])
        self.assertNotIn(1, completed["event_sequence"].tolist())
        self.assertNotIn(6, completed["event_sequence"].tolist())

    def test_team_grid_retains_blank_event_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            season_root = Path(directory) / "A"
            season_root.mkdir()
            players = pd.DataFrame(
                {
                    "id": [1, 2],
                    "code": [101, 202],
                    "element_type": [3, 3],
                    "team": [1, 2],
                    "web_name": ["Home", "Away"],
                }
            )
            gameweeks = pd.DataFrame(
                {
                    "GW": [1, 1, 2, 2, 4, 4, 38, 38],
                    "element": [1, 2] * 4,
                    "fixture": [11, 11, 22, 22, 44, 44, 388, 388],
                    "was_home": [True, False] * 4,
                    "kickoff_time": [
                        "2025-08-01T12:00:00Z",
                        "2025-08-01T12:00:00Z",
                        "2025-08-08T12:00:00Z",
                        "2025-08-08T12:00:00Z",
                        "2025-08-22T12:00:00Z",
                        "2025-08-22T12:00:00Z",
                        "2026-05-20T12:00:00Z",
                        "2026-05-20T12:00:00Z",
                    ],
                    "team_h_score": [2, 2, 1, 1, 3, 3, 0, 0],
                    "team_a_score": [0, 0, 1, 1, 1, 1, 0, 0],
                    "total_points": [1] * 8,
                    "minutes": [90] * 8,
                    "goals_scored": [0] * 8,
                    "assists": [0] * 8,
                    "bonus": [0] * 8,
                    "clean_sheets": [0] * 8,
                    "saves": [0] * 8,
                    "yellow_cards": [0] * 8,
                    "red_cards": [0] * 8,
                }
            )
            players.to_csv(season_root / "players_raw.csv", index=False)
            gameweeks.to_csv(season_root / "merged_gw.csv", index=False)

            _, team_week, _ = _season_frame(Path(directory), "A")

        home_blank = team_week.loc[
            team_week["team"].eq(1) & team_week["event_sequence"].eq(3)
        ].iloc[0]
        self.assertEqual(home_blank["goals_for"], 0)
        self.assertEqual(home_blank["goals_against"], 0)
        self.assertEqual(home_blank["team_event_observed"], 0)

    def test_six_event_labels_are_purged_before_validation(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
