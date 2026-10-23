from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.core.models import Candle


def _candles(n: int) -> list[Candle]:
    h4 = 14_400_000
    return [Candle(timestamp_ms=i * h4, open=1.0, high=1.05, low=0.95,
                   close=1.0, volume=1.0) for i in range(n)]


class BuildRegistryTest(unittest.TestCase):
    def test_three_named_signals(self) -> None:
        from tools.lanes.funding_probe import build_registry
        reg = build_registry([0.0] * 10)
        self.assertEqual(set(reg), {"funding_fade", "funding_confirm", "funding_flip"})
        for generator, grid in reg.values():
            self.assertTrue(callable(generator))
            self.assertIsInstance(grid, list)
            self.assertTrue(grid)


class WriteReportTest(unittest.TestCase):
    def test_writes_json_and_md_over_real_probe(self) -> None:
        from moonface.research.edge.score import run_probe_battery
        from tools.lanes.funding_probe import build_registry, write_report
        candles = _candles(300)
        funding = [0.0001 if (i // 5) % 2 else -0.0001 for i in range(300)]
        rows = run_probe_battery(
            candles, build_registry(funding), k=1.0, m=2.0, n_bars=24,
            atr_period=14, fee_rate=0.001, slippage=0.0, oos_tail_bars=50,
            warmup=10, future_bars=10)
        with TemporaryDirectory() as d:
            out = write_report(Path(d) / "run", rows, timeframe="4h",
                               funding_symbol="BTC/USDT:USDT")
            self.assertTrue((out / "funding_probe.json").exists())
            self.assertTrue((out / "funding_probe.md").exists())
            payload = json.loads((out / "funding_probe.json").read_text())
            self.assertEqual({r["signal"] for r in payload},
                             {"funding_fade", "funding_confirm", "funding_flip"})
            md = (out / "funding_probe.md").read_text()
            self.assertIn("funding_fade", md)
            self.assertIn("Funding-Rate Edge Probe", md)
