"""The mtf_long paper adapter must (a) fire LONG exactly where the frozen
research cell fires a LONG entry, (b) NEVER emit SHORT (long-only), (c) WAIT on
no-entry / thin history, and (d) validate only the frozen spec. Reusing the
research entry generator directly is the whole point — the live decision cannot
drift from the registered backtest."""
import math
import unittest

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.mtf.evaluate import cell_gen
from moonface.research.mtf.grid import broaden_best_cell
from moonface.strategies.spec import PromotedStrategy
from moonface.strategies.impls.mtf_long import MtfLongStrategy


def _c(close: float, i: int) -> Candle:
    return Candle(timestamp_ms=i * 900_000, open=close, high=close + 1.5,
                  low=close - 1.5, close=close, volume=1.0)


def _osc(n: int) -> list[Candle]:
    # slow sine = a full up-THEN-down regime cycle over the series (so both the
    # 4h up- and down-quality gates fire); fast sine = the 15m RSI dips/rips
    return [_c(100.0 + 40.0 * math.sin(i / 1400.0) + 8.0 * math.sin(i / 50.0), i)
            for i in range(n)]


def _bundle(candles) -> DataBundle:
    return DataBundle(candles=list(candles), funding=None, basis=None,
                      feature=None)


def _strat(**over) -> PromotedStrategy:
    base = dict(
        family="mtf_long",
        params={"cell": "broaden_best", "long_only": True},
        exit={"name": "horizon_hold", "params": {"n_bars": 192, "atr_period": 14}},
        fraction=0.0034, status="paper",
        asset={"exchange": "binance", "symbol": "BTC/USDT:USDT",
               "timeframe": "15m"},
        provenance={}, max_drawdown_p95=0.30)
    base.update(over)
    return PromotedStrategy(**base)


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.mod = MtfLongStrategy()

    def test_accepts_frozen_spec(self):
        self.assertTrue(self.mod.validate(_strat()))

    def test_rejects_drift(self):
        self.assertFalse(self.mod.validate(
            _strat(params={"cell": "broaden_best", "long_only": False})))
        self.assertFalse(self.mod.validate(
            _strat(params={"cell": "headline", "long_only": True})))
        self.assertFalse(self.mod.validate(
            _strat(exit={"name": "horizon_wide_stop",
                         "params": {"n_bars": 192, "atr_period": 14}})))
        self.assertFalse(self.mod.validate(
            _strat(exit={"name": "horizon_hold",
                         "params": {"n_bars": 96, "atr_period": 14}})))


class DecisionMatchesResearchTest(unittest.TestCase):
    """The adapter's per-bar decision must equal the frozen cell's entry side,
    with SHORT projected to WAIT."""

    @classmethod
    def setUpClass(cls):
        cls.candles = _osc(9000)
        cls.entries = dict(cell_gen(broaden_best_cell())(cls.candles))
        cls.mod = MtfLongStrategy()
        cls.strat = _strat()
        cls.longs = [i for i, s in cls.entries.items() if s == "LONG"]
        cls.shorts = [i for i, s in cls.entries.items() if s == "SHORT"]

    def test_fixture_has_both_sides(self):
        self.assertGreater(len(self.longs), 0)
        self.assertGreater(len(self.shorts), 0)

    def test_long_bars_emit_long(self):
        for j in self.longs[5:15]:                       # interior LONG entries
            sig = self.mod.evaluate(self.strat, _bundle(self.candles[:j + 1]))
            self.assertEqual(sig.decision, "LONG", f"bar {j}")
            self.assertEqual(sig.price, self.candles[j].close)
            self.assertIsNone(sig.invalidation)          # no-stop cell
            self.assertEqual(sig.tier, "paper")

    def test_short_bars_never_emit_short(self):
        for j in self.shorts[5:15]:
            sig = self.mod.evaluate(self.strat, _bundle(self.candles[:j + 1]))
            self.assertEqual(sig.decision, "WAIT", f"short bar {j} must be WAIT")

    def test_no_entry_bar_is_wait(self):
        non = next(i for i in range(2000, 3000) if i not in self.entries)
        sig = self.mod.evaluate(self.strat, _bundle(self.candles[:non + 1]))
        self.assertEqual(sig.decision, "WAIT")

    def test_never_emits_short_across_whole_series(self):
        decisions = set()
        for j in range(900, 4000, 37):
            decisions.add(
                self.mod.evaluate(self.strat, _bundle(self.candles[:j + 1]))
                .decision)
        self.assertNotIn("SHORT", decisions)


class GuardsTest(unittest.TestCase):
    def test_thin_history_waits(self):
        sig = MtfLongStrategy().evaluate(_strat(), _bundle(_osc(500)))
        self.assertEqual(sig.decision, "WAIT")
        self.assertIn("history", sig.reason)


if __name__ == "__main__":
    unittest.main()
