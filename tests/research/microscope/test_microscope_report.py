import csv
import tempfile
import unittest
from pathlib import Path

from moonface.research.microscope.report import (
    HEADER, render_study_report, write_csv,
)

BUCKETS = [
    {"label": "GOOD", "n": 80, "verdict": "DESCRIPTIVE",
     "fwd_r_12_mean": 1.01, "fwd_r_12_ci": (0.94, 1.08),
     "mfe_r_median": 1.2, "mae_r_median": 0.5,
     "n_resolved": 80, "p_stop_first": 0.1, "fwd_vol_mean": 0.01},
    {"label": "TINY", "n": 5, "verdict": "INSUFFICIENT_DATA"},
]
NULL_OK = {"real_effect": 2.0, "null_p95": 0.3, "pct_beaten": 1.0,
           "verdict": "EXCEEDS_NULL"}
NULL_BAD = {"real_effect": 0.2, "null_p95": 0.3, "pct_beaten": 0.6,
            "verdict": "INDISTINGUISHABLE_FROM_NULL"}


class RenderTest(unittest.TestCase):
    def test_header_and_rows(self):
        text = render_study_report(BUCKETS, NULL_OK, 100, 85, 3)
        self.assertIn(HEADER, text.splitlines()[0])
        self.assertIn("GOOD", text)
        self.assertIn("INSUFFICIENT_DATA", text)
        self.assertIn("EXCEEDS_NULL", text)
        self.assertIn("pre-registered", text)
        self.assertNotIn("SELECTION ARTIFACT", text)

    def test_artifact_warning_when_null_wins(self):
        text = render_study_report(BUCKETS, NULL_BAD, 100, 85, 3)
        self.assertIn("SELECTION ARTIFACT", text)

    def test_counts_reported(self):
        text = render_study_report(BUCKETS, NULL_OK, 100, 85, 3)
        self.assertIn("100", text)
        self.assertIn("85", text)


class WriteCsvTest(unittest.TestCase):
    def test_roundtrip_and_parent_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "out.csv"
            write_csv(path, [{"a": 1, "b": None, "extra": 9}], ["a", "b"])
            with path.open() as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows, [{"a": "1", "b": ""}])


if __name__ == "__main__":
    unittest.main()
