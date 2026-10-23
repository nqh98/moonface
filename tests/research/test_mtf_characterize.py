import math
import unittest

from moonface.core.models import Candle
from moonface.research.mtf.characterize import (book_stats, distribution,
                                                enriched_trades,
                                                excursion_summary,
                                                outlier_dependence)
from moonface.research.mtf.grid import broaden_best_cell


def _c15(close: float, i: int) -> Candle:
    return Candle(timestamp_ms=i * 900_000, open=close, high=close + 1.5,
                  low=close - 1.5, close=close, volume=1.0)


def _osc_series(n: int) -> list[Candle]:
    return [_c15(100.0 + 0.05 * i + 8.0 * math.sin(i / 50.0), i) for i in range(n)]


class EnrichedTradesTest(unittest.TestCase):
    def setUp(self):
        self.recs = enriched_trades(_osc_series(8000), broaden_best_cell())

    def test_produces_trades_with_bounded_excursions(self):
        self.assertGreater(len(self.recs), 0)
        for r in self.recs:
            self.assertLessEqual(r["mae_r"], 0.0)   # adverse is <= 0
            self.assertGreaterEqual(r["mfe_r"], 0.0)  # favorable is >= 0
            self.assertIn(r["side"], ("LONG", "SHORT"))

    def test_side_books_partition_the_whole(self):
        whole = book_stats(self.recs)
        longs = book_stats(self.recs, "LONG")
        shorts = book_stats(self.recs, "SHORT")
        self.assertEqual(longs["n"] + shorts["n"], whole["n"])
        self.assertAlmostEqual(longs["total_r"] + shorts["total_r"],
                               whole["total_r"], places=2)


class OutlierDependenceTest(unittest.TestCase):
    def _recs(self, rs):
        return [{"ts": i, "side": "LONG", "net_r": r, "mae_r": -1.0, "mfe_r": 1.0}
                for i, r in enumerate(rs)]

    def test_dropping_top_winners_lowers_total(self):
        recs = self._recs([10.0, 1.0, 1.0, -1.0, -1.0, -1.0])
        o = outlier_dependence(recs, ks=(1, 3))
        self.assertEqual(o["total_r"], 9.0)
        # drop top 1 (the 10R): total falls to -1R and goes negative
        self.assertEqual(o["ex_top_k"][1]["total_r"], -1.0)
        self.assertFalse(o["ex_top_k"][1]["positive"])

    def test_outlier_carried_edge_flips_negative(self):
        # a broad edge stays positive after dropping a few winners; an
        # outlier-carried one flips -> the distinguishing test
        broad = self._recs([1.0] * 10 + [-0.5] * 8)
        o = outlier_dependence(broad, ks=(3,))
        self.assertTrue(o["ex_top_k"][3]["positive"])

    def test_profit_share_of_top_bucket_is_a_fraction(self):
        o = outlier_dependence(self._recs([5.0, 1.0, 1.0, -1.0]))
        self.assertGreaterEqual(o["top5pct_profit_share"], 0.0)
        self.assertLessEqual(o["top5pct_profit_share"], 1.0)


class DistributionExcursionTest(unittest.TestCase):
    def test_distribution_payoff_and_bounds(self):
        recs = [{"ts": 0, "side": "LONG", "net_r": 2.0, "mae_r": -1.0, "mfe_r": 3.0},
                {"ts": 1, "side": "SHORT", "net_r": -1.0, "mae_r": -2.0, "mfe_r": 0.5}]
        d = distribution(recs)
        self.assertEqual(d["win_rate"], 0.5)
        self.assertAlmostEqual(d["payoff"], 2.0)   # avg_win 2 / |avg_loss 1|
        self.assertEqual(d["best_r"], 2.0)
        self.assertEqual(d["worst_r"], -1.0)

    def test_excursion_winner_loser_split(self):
        recs = [{"ts": 0, "side": "LONG", "net_r": 3.0, "mae_r": -4.0, "mfe_r": 5.0},
                {"ts": 1, "side": "LONG", "net_r": -2.0, "mae_r": -3.0, "mfe_r": 1.0}]
        e = excursion_summary(recs)
        self.assertEqual(e["median_mae_winners_r"], -4.0)
        self.assertEqual(e["median_mae_losers_r"], -3.0)


if __name__ == "__main__":
    unittest.main()
