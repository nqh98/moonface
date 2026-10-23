# tests/test_research_report.py
import os
import tempfile
import unittest
from pathlib import Path

from moonface.kernel.report import render_domain_report, write_domain_report
from moonface.kernel.spec import HypothesisSpec, spec_hash
from moonface.kernel.store import Store

ASSET = {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h"}


class ReportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.tmp.name, "r.db"))
        self.store.register_domain("d", 1, "active", {"assets": [ASSET]},
                                   0, 1000, 800)
        self.specs = [self._spec(20), self._spec(55)]
        self.store.insert_grid("d", 1, self.specs)
        h0 = spec_hash(self.specs[0])
        self.store.advance(h0, "screened", {
            "screen_trades": 40, "screen_expectancy_r": 0.2,
            "holdout_trades": 12, "holdout_mar": 1.4,
            "research_trades": 52, "research_mar": 2.0,
            "research_sharpe": 0.3, "research_skew": 0.0,
            "research_kurtosis": 3.0})
        self.store.advance(h0, "oos_pass", {})
        self.store.advance(h0, "corrected_survivor", {"dsr": 0.97})

    @staticmethod
    def _spec(n: int) -> HypothesisSpec:
        return HypothesisSpec(
            domain="d", version=1, asset=ASSET,
            entry={"family": "donchian_break", "params": {"n": n}},
            exit={"name": "horizon_hold", "params": {"n_bars": 24, "atr_period": 14}},
            fraction=0.01)


class TestRender(ReportTestCase):
    def test_contains_funnel_and_leaderboard(self):
        md = render_domain_report(self.store, "d", 1)
        self.assertIn("## Funnel", md)
        self.assertIn("| corrected_survivor | 1 |", md)
        self.assertIn("| pending | 1 |", md)
        self.assertIn("donchian_break", md)
        self.assertIn("0.97", md)

    def test_awaiting_gate_names_the_command(self):
        self.store.set_domain_status("d", 1, "awaiting_gate")
        md = render_domain_report(self.store, "d", 1)
        self.assertIn("gate d --open-lockbox", md)

    def test_closed_negative_verdict(self):
        self.store.set_domain_status("d", 1, "closed_negative")
        md = render_domain_report(self.store, "d", 1)
        self.assertIn("closed negative", md)

    def test_write_creates_file(self):
        path = write_domain_report(self.store, "d", 1, Path(self.tmp.name))
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "report_v1.md")


if __name__ == "__main__":
    unittest.main()
