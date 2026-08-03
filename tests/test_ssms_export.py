import csv
import re
import tempfile
import unittest
from pathlib import Path

from fpl_model.ssms_export import export_ssms_csv, normalize_team_identifier


class SsmsExportTests(unittest.TestCase):
    def test_team_identifier_is_always_textual_and_idempotent(self) -> None:
        self.assertEqual(normalize_team_identifier("12.0"), "team_id_12")
        self.assertEqual(normalize_team_identifier("Man Utd"), "team_name_Man Utd")
        self.assertEqual(normalize_team_identifier(""), "team_unknown")
        self.assertEqual(normalize_team_identifier("team_id_12"), "team_id_12")

    def test_export_uses_bom_crlf_and_preserves_blank_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            output = Path(directory) / "output.csv"
            source.write_text(
                "season,team,points_next_6\n"
                "2019-20,12.0,4.0\n"
                "2025-26,Man Utd,\n",
                encoding="utf-8",
            )

            self.assertEqual(export_ssms_csv(source, output), 2)
            payload = output.read_bytes()
            self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", payload)

            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["team"], "team_id_12")
            self.assertEqual(rows[1]["team"], "team_name_Man Utd")
            self.assertEqual(rows[1]["points_next_6"], "")

    def test_sql_server_staging_schema_matches_published_csv(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with (repository / "data/processed/modeling_table.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            csv_columns = next(csv.reader(stream))

        sql = (repository / "sql/sql_server/import_modeling_table.sql").read_text(
            encoding="utf-8"
        )
        create_table = sql.split("CREATE TABLE dbo.player_gameweeks_raw (", 1)[1].split(
            ");", 1
        )[0]
        sql_columns = re.findall(r"^\s{4}([a-z0-9_]+)\s+nvarchar\(", create_table, re.MULTILINE)
        self.assertEqual(sql_columns, csv_columns)
        self.assertEqual(create_table.count(" NULL"), len(csv_columns))
