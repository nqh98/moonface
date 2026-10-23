import csv
import tempfile
import unittest
from pathlib import Path

from tools.lanes.aggressor_trades_rung0 import cmd_nonlockbox


class TestAggressorTradesCli(unittest.TestCase):
    def write_synthetic_csv(self, path: Path) -> None:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["ts_ms", "symbol", "buy_count", "sell_count", "last_price"])
            writer.writeheader()
            for i in range(220):
                writer.writerow(
                    {
                        "ts_ms": i * 300_000,
                        "symbol": "BTCUSDT",
                        "buy_count": 2 if i % 2 == 0 else 1,
                        "sell_count": 1 if i % 2 == 0 else 2,
                        "last_price": 100.0 + i,
                    }
                )

    def test_cmd_nonlockbox_writes_artifacts_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "synthetic_seconds.csv"
            out = root / "out"
            self.write_synthetic_csv(csv_path)

            result = cmd_nonlockbox(csv_path, out)

            self.assertEqual(result["lockbox_touched"], False)
            self.assertTrue((out / "audit.json").exists())
            self.assertTrue((out / "nonlockbox_results.json").exists())
            self.assertTrue((out / "report.md").exists())
            report = (out / "report.md").read_text()
            self.assertIn("No sealed lockbox evaluation was run.", report)
            with self.assertRaises(SystemExit):
                cmd_nonlockbox(csv_path, out)
