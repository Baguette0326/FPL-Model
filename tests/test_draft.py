from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from fpl_model.draft import DraftBoard, PlayerProjection  # noqa: E402
from fpl_model.weekly import WeeklyProjection, recommend_waivers  # noqa: E402


def player(name: str, position: str, points: float, uncertainty: float = 0) -> PlayerProjection:
    return PlayerProjection(name, position, points, uncertainty)


class DraftBoardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.players = [
            player("Forward A", "FWD", 220),
            player("Forward B", "FWD", 190),
            player("Forward C", "FWD", 160),
            player("Forward D", "FWD", 130),
            player("Midfielder A", "MID", 210),
            player("Midfielder B", "MID", 180),
            player("Defender A", "DEF", 175),
            player("Goalkeeper A", "GK", 150),
        ]

    def test_other_manager_pick_removes_player(self) -> None:
        board = DraftBoard(self.players)
        board.record_pick("Forward A")
        names = {item.player.name for item in board.recommendations(10)}
        self.assertNotIn("Forward A", names)

    def test_our_pick_updates_roster_and_open_slots(self) -> None:
        board = DraftBoard(self.players)
        board.record_pick("Goalkeeper A", mine=True)
        self.assertEqual(board.open_slots("GK"), 1)

    def test_full_position_is_not_recommended(self) -> None:
        players = self.players + [player("Goalkeeper B", "GK", 145)]
        board = DraftBoard(players)
        board.record_pick("Goalkeeper A", mine=True)
        board.record_pick("Goalkeeper B", mine=True)
        positions = {item.player.position for item in board.recommendations(20)}
        self.assertNotIn("GK", positions)

    def test_unavailable_player_cannot_be_selected_twice(self) -> None:
        board = DraftBoard(self.players)
        board.record_pick("Forward A")
        with self.assertRaisesRegex(ValueError, "unavailable or unknown"):
            board.record_pick("Forward A", mine=True)

    def test_risk_penalty_can_break_close_projection_tie(self) -> None:
        players = [
            player("Risky Mid", "MID", 200, uncertainty=40),
            player("Safe Mid", "MID", 198, uncertainty=5),
        ]
        board = DraftBoard(players)
        self.assertEqual(board.recommendations(1)[0].player.name, "Safe Mid")

    def test_weekly_waiver_is_same_position_and_improves_roster(self) -> None:
        owned = WeeklyProjection(player("Owned Mid", "MID", 140), 8, 18, 90)
        available = WeeklyProjection(
            player("Breakout Mid", "MID", 160),
            15,
            32,
            115,
            minutes_trend=3,
            involvement_trend=2,
        )
        result = recommend_waivers([owned], [available])
        self.assertEqual(result[0].add.player.name, "Breakout Mid")
        self.assertEqual(result[0].drop.player.name, "Owned Mid")
        self.assertGreater(result[0].expected_gain, 0)


if __name__ == "__main__":
    unittest.main()
