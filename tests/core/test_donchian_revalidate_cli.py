# tests/test_donchian_revalidate_cli.py
import unittest
from pathlib import Path
import tempfile

from moonface.core.models import Candle
import tools.lanes.donchian_revalidate as cli


def _candles(n=900):
    cs = []
    price = 100.0
    for k in range(n):
        price *= 1.012 if (k % 23) < 20 else 0.95
        cs.append(Candle(timestamp_ms=1_000_000 + k * 14_400_000,
                         open=round(price / 1.003, 4), high=round(price * 1.006, 4),
                         low=round(price * 0.99, 4), close=round(price, 4), volume=10.0))
    return cs


class CliSmoke(unittest.TestCase):
    def test_run_writes_result_with_verdict(self):
        cli.fetch_perp_candles = lambda *a, **k: _candles()
        cli.fetch_funding_rates = lambda *a, **k: None
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "RESULT.md"
            rc = cli.main(["--symbol", "BTCUSDT", "--interval", "4h",
                           "--start-ms", "1577836800000", "--end-ms", "1781251200000",
                           "--cache-dir", d, "--out", str(out)])
            self.assertEqual(rc, 0)
            text = out.read_text()
            self.assertIn("# BTC Donchian Revalidation", text)
            self.assertTrue(any(t in text for t in
                ("REAFFIRM PAPER", "DOWNGRADE TO PARKED / NEEDS-FIX",
                 "INCONCLUSIVE / PAPER-SUSPENDED")))


if __name__ == "__main__":
    unittest.main()
