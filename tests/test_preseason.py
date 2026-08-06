from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from fpl_model.preseason import _historical_lookup


class PreseasonHistoryTests(unittest.TestCase):
    def test_latest_available_history_wins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for season, points in (("A", 10), ("B", 20)):
                season_root = root / season
                season_root.mkdir()
                pd.DataFrame(
                    {
                        "code": [7],
                        "total_points": [points],
                        "minutes": [900],
                        "element_type": [3],
                        "team_code": [1],
                    }
                ).to_csv(season_root / "players_raw.csv", index=False)
            history = _historical_lookup(root, ["A", "B"])
        self.assertEqual(history.iloc[0]["prior_season"], "B")
        self.assertEqual(history.iloc[0]["total_points"], 20)
        self.assertEqual(history.iloc[0]["seasons_ago"], 1)


if __name__ == "__main__":
    unittest.main()
