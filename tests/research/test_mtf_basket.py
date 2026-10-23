import unittest

from moonface.research.mtf.attribute import path_max_dd
from moonface.research.mtf.basket import (diversification, merge_streams,
                                          yearly_robustness)

# 2021-01 and 2022-01 timestamps (ms) for two synthetic assets.
_2021 = 1_609_459_200_000
_2022 = 1_640_995_200_000


class BasketMergeTest(unittest.TestCase):
    def test_merge_is_time_ordered_and_weighted(self):
        streams = {
            "A": [(_2021 + 2, "LONG", 3.0), (_2021, "SHORT", 1.0)],
            "B": [(_2021 + 1, "LONG", 2.0)],
        }
        merged = merge_streams(streams, 0.5)
        # union of all 3 trades, sorted by timestamp, each R halved
        self.assertEqual([ts for ts, _, _ in merged],
                         [_2021, _2021 + 1, _2021 + 2])
        self.assertEqual([r for _, _, r in merged], [0.5, 1.0, 1.5])

    def test_diversification_detects_decorrelation(self):
        # A draws down early, B draws down late -> merged path never sees both
        # troughs at once, so merged DD is shallower than the summed reference.
        streams = {
            "A": [(_2021, "LONG", -5.0), (_2021 + 1, "LONG", 6.0),
                  (_2022, "LONG", 1.0)],
            "B": [(_2021, "LONG", 1.0), (_2021 + 1, "LONG", 1.0),
                  (_2022, "LONG", -5.0)],
        }
        div = diversification(streams, 1.0)
        self.assertEqual(div["ref_dd_r"], -10.0)        # -5 (A) + -5 (B)
        self.assertGreater(div["merged_dd_r"], -10.0)   # shallower when merged
        self.assertGreater(div["dd_cut_frac"], 0.0)

    def test_perfectly_correlated_streams_have_no_cut(self):
        s = [(_2021, "LONG", -2.0), (_2021 + 1, "LONG", 1.0)]
        streams = {"A": list(s), "B": list(s)}
        div = diversification(streams, 1.0)
        # identical lockstep streams: merged DD == summed reference, zero cut
        self.assertEqual(div["merged_dd_r"], div["ref_dd_r"])
        self.assertEqual(div["dd_cut_frac"], 0.0)

    def test_yearly_robustness_counts_positive_years(self):
        merged = [
            (_2021, "LONG", 5.0), (_2021 + 1, "LONG", 1.0),   # 2021 net +6
            (_2022, "LONG", -3.0), (_2022 + 1, "LONG", 1.0),  # 2022 net -2
        ]
        rows, frac = yearly_robustness(merged)
        self.assertEqual([r["year"] for r in rows], [2021, 2022])
        self.assertTrue(rows[0]["positive"])
        self.assertFalse(rows[1]["positive"])
        self.assertEqual(frac, 0.5)


class PathMaxDdSanityTest(unittest.TestCase):
    def test_merge_dd_matches_manual_path(self):
        streams = {"A": [(1, "LONG", -4.0)], "B": [(2, "LONG", -4.0)]}
        merged = merge_streams(streams, 0.5)
        # scaled to -2, -2 -> cumulative -2, -4 -> worst drawdown -4
        self.assertEqual(path_max_dd([r for _, _, r in merged]), -4.0)


if __name__ == "__main__":
    unittest.main()
