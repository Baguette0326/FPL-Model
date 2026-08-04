from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from fpl_model.pipeline import (  # noqa: E402
    LEGACY_MODELING_TABLE,
    ML_V2_AUDIT_REPORT,
    ML_V2_MODELING_TABLE,
)


class PipelineOutputTests(unittest.TestCase):
    def test_ml_v2_outputs_never_reuse_legacy_path(self) -> None:
        self.assertNotEqual(ML_V2_MODELING_TABLE, LEGACY_MODELING_TABLE)
        self.assertEqual(ML_V2_MODELING_TABLE.name, "modeling_table_ml_v2.csv")
        self.assertEqual(ML_V2_AUDIT_REPORT.name, "ml_v2_data_audit.json")


if __name__ == "__main__":
    unittest.main()
