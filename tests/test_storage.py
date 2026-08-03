from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from fpl_model.storage import initialize_database  # noqa: E402


class StorageTests(unittest.TestCase):
    def test_initialization_creates_versioned_event_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "league.sqlite3"
            initialize_database(path)
            connection = sqlite3.connect(path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                version = connection.execute(
                    "SELECT value FROM schema_metadata WHERE key='schema_version'"
                ).fetchone()[0]
                managers = connection.execute("SELECT COUNT(*) FROM managers").fetchone()[0]
            finally:
                connection.close()
        self.assertTrue({"players", "draft_picks", "predictions", "roster_events", "trades"} <= tables)
        self.assertEqual(version, "1")
        self.assertEqual(managers, 4)

    def test_foreign_keys_reject_unknown_draft_player(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "league.sqlite3"
            initialize_database(path)
            connection = sqlite3.connect(path)
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO draft_picks VALUES(?, ?, ?, ?, ?, ?)",
                        ("draft", 1, 1, 1, 999999, "2026-08-10T12:00:00Z"),
                    )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
