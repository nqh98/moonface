import random
import unittest

from moonface.core.models import Candle
from moonface.research.mtf.combine import (TF_MS, derive_htf, htf_bias_series)
from moonface.research.mtf.evaluate import (cell_gen, prescreen, run_cell,
                                            search, search_diagnostic)
from moonface.research.mtf.grid import (HEADLINE_LABEL, all_cells,
                                        bias_price_vs_sma, bias_roc,
                                        headline_cell)
from moonface.research.mtf.attribute import (path_max_dd, period_stats,
                                             trade_stream)

import pytest

pytestmark = pytest.mark.slow


def _series(n: int, drift: float = 0.0003, vol: float = 0.004,
            seed: int = 7) -> list[Candle]:
    rng = random.Random(seed)
    out: list[Candle] = []
    p = 100.0
    for i in range(n):
        p *= 1 + rng.gauss(drift, vol)
        out.append(Candle(timestamp_ms=1_577_836_800_000 + i * TF_MS["15m"],
                          open=p, high=p * (1 + abs(rng.gauss(0, 0.003))),
                          low=p * (1 - abs(rng.gauss(0, 0.003))),
                          close=p, volume=1.0))
    return out


class TestCombine(unittest.TestCase):
    def test_derive_htf_counts_and_close(self):
        base = _series(960)                       # exactly 10 days of 15m
        d1 = derive_htf(base, "15m", "1d")
        self.assertEqual(len(d1), 10)
        # the daily close is the last 15m close of its group
        self.assertAlmostEqual(d1[0].close, base[95].close)
        self.assertEqual(d1[0].high, max(c.high for c in base[:96]))

    def test_derive_htf_rejects_non_multiple_or_finer(self):
        base = _series(100)
        with self.assertRaises(ValueError):
            derive_htf(base, "1h", "15m")          # finer than base

    def test_bias_no_lookahead(self):
        # The bias at base bar i must equal the bias computed on the HTF series
        # truncated to bars closed by base[i]. Rebuilding from a prefix that
        # stops at i must not change bias[i].
        base = _series(2000)
        full = htf_bias_series(base, "15m", "1d", bias_price_vs_sma, {"n": 5})
        cut = 1500
        prefix = htf_bias_series(base[:cut], "15m", "1d",
                                 bias_price_vs_sma, {"n": 5})
        self.assertEqual(full[:cut], prefix)

    def test_mtf_entries_respect_bias(self):
        base = _series(4000)
        cells = all_cells()
        cell = next(c for c in cells if c.htf == "1d"
                    and c.trigger_fn == "bb_breakout")
        bias = htf_bias_series(base, "15m", cell.htf, bias_price_vs_sma,
                               cell.bias_params)
        entries = cell_gen(cell)(base)
        for i, side in entries:
            want = 1 if side == "LONG" else -1
            self.assertEqual(bias[i], want)


class TestBias(unittest.TestCase):
    def test_price_vs_sma_sign(self):
        # strictly rising series -> price above its SMA -> +1 after warmup
        rising = [Candle(timestamp_ms=i, open=100 + i, high=100 + i,
                         low=100 + i, close=100 + i, volume=1.0)
                  for i in range(60)]
        b = bias_price_vs_sma(rising, {"n": 10})
        self.assertEqual(b[59], 1)
        self.assertEqual(b[0], 0)                  # warmup -> flat

    def test_roc_sign(self):
        rising = [Candle(timestamp_ms=i, open=100 + i, high=100 + i,
                         low=100 + i, close=100 + i, volume=1.0)
                  for i in range(60)]
        b = bias_roc(rising, {"n": 10})
        self.assertEqual(b[59], 1)


class TestEvaluate(unittest.TestCase):
    def test_grid_well_formed(self):
        cells = all_cells()
        self.assertEqual(len(cells), 24)
        self.assertEqual(len({c.label for c in cells}), 24)  # unique labels
        triggers = {c.trigger_fn for c in cells}
        self.assertIn("rsi_reversion", triggers)   # counter-trend present
        self.assertIn("ma_reclaim", triggers)
        exits = {c.exit_name for c in cells}
        self.assertIn("horizon_wide_stop", exits)  # drawdown lever present
        for c in cells:
            self.assertIn("atr_period", c.exit_params)
            self.assertGreater(c.h, 0)

    def test_prescreen_kill_on_noise(self):
        # zero-drift noise must not pass the gross Z gate
        noise = _series(8000, drift=0.0, vol=0.004, seed=3)
        cell = all_cells()[0]
        s1 = prescreen(noise, cell)
        self.assertFalse(s1["passed"])

    def test_run_cell_stops_at_failed_stage(self):
        noise = _series(8000, drift=0.0, vol=0.004, seed=3)
        cell = all_cells()[0]
        res = run_cell(cell, noise[:6400], noise, [0.0] * 12, 12)
        self.assertEqual(res["verdict"], "negative")
        # a stage-1 failure leaves later stages unrun
        if not res["stage1"]["passed"]:
            self.assertIsNone(res["stage2"])
            self.assertIsNone(res["stage3"])

    def test_diagnostic_always_computes_econ(self):
        # even a cell that fails stage 1 must have stage3 econ metrics computed
        s = _series(12000, seed=11)
        cells = all_cells()
        rows = search_diagnostic(cells, s[:9600], s)
        self.assertEqual(len(rows), len(cells))
        for r in rows:
            self.assertIsNotNone(r["stage3"])
            self.assertIn("mar", r["stage3"]["metrics"])
            self.assertIn(r["econ_pass"], (True, False))

    def test_search_sorts_and_runs(self):
        s = _series(12000, seed=11)
        cells = all_cells()
        rows = search(cells, s[:9600], s)
        self.assertEqual(len(rows), len(cells))
        dsrs = [r["stage2"]["dsr"] for r in rows if r["stage2"]]
        self.assertEqual(dsrs, sorted(dsrs, reverse=True))


class TestAttribute(unittest.TestCase):
    def test_headline_cell_is_in_grid(self):
        cell = headline_cell()
        self.assertEqual(cell.label, HEADLINE_LABEL)
        self.assertEqual(cell.exit_name, "horizon_wide_stop")
        self.assertEqual(cell.trigger_fn, "rsi_reversion")

    def test_path_max_dd(self):
        # +1,+1,-3,+1 -> equity 1,2,-1,0 ; peak 2 ; trough at -1 -> dd -3
        self.assertEqual(path_max_dd([1.0, 1.0, -3.0, 1.0]), -3.0)
        self.assertEqual(path_max_dd([]), 0.0)

    def test_trade_stream_and_period_split(self):
        s = _series(12000, seed=5)
        cell = headline_cell()
        trades = trade_stream(s, cell)
        self.assertTrue(all(len(t) == 3 for t in trades))
        ts_sorted = [t[0] for t in trades]
        self.assertEqual(ts_sorted, sorted(ts_sorted))   # time-ordered
        # a period split partitions the trades (counts add up)
        mid = s[len(s) // 2].timestamp_ms
        early = period_stats(trades, end_ms=mid)
        late = period_stats(trades, start_ms=mid)
        self.assertEqual(early["n"] + late["n"], len(trades))


if __name__ == "__main__":
    unittest.main()
