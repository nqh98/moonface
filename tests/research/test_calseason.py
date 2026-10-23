import datetime as dt
import unittest

from moonface.core.models import Candle
from moonface.research.calseason import (
    calseason_verdict,
    cell_names,
    cell_returns,
    pooled_cell,
)


def ts(year, month, day, hour):
    return int(dt.datetime(year, month, day, hour, tzinfo=dt.timezone.utc).timestamp() * 1000)


def candle_at(ts_ms, close):
    return Candle(ts_ms, close, close, close, close, 1000.0)


class TestCalendarCells(unittest.TestCase):
    def test_funding_pre_post_and_weekend_weekday_cells(self):
        # Monday 04:00 UTC is pre-funding and weekday.
        self.assertEqual(cell_names(ts(2026, 6, 15, 4)),
                         ["funding_pre", "weekday"])
        # Monday 08:00 UTC is post-funding and weekday.
        self.assertEqual(cell_names(ts(2026, 6, 15, 8)),
                         ["funding_post", "weekday"])
        # Saturday 12:00 UTC is pre-funding and weekend.
        self.assertEqual(cell_names(ts(2026, 6, 20, 12)),
                         ["funding_pre", "weekend"])

    def test_cell_returns_assign_close_to_close_return_by_current_bar_time(self):
        candles = [
            candle_at(ts(2026, 6, 15, 0), 100.0),
            candle_at(ts(2026, 6, 15, 4), 101.0),
            candle_at(ts(2026, 6, 15, 8), 99.0),
            candle_at(ts(2026, 6, 15, 12), 102.0),
        ]

        got = cell_returns(candles)

        self.assertAlmostEqual(got["funding_pre"][0], 101.0 / 100.0 - 1.0)
        self.assertAlmostEqual(got["funding_post"][0], 99.0 / 101.0 - 1.0)
        self.assertEqual(len(got["weekday"]), 3)
        self.assertEqual(got["weekend"], [])



class TestCalendarVerdict(unittest.TestCase):
    @staticmethod
    def stat(mean, t, n=40):
        return {"n": n, "mean": mean, "t": t}

    def test_pooled_cell_reports_two_sided_evidence_and_same_sign_breadth(self):
        stats = [self.stat(0.01, 1.0)] * 12 + [self.stat(-0.001, -0.1)] * 4
        got = pooled_cell(stats)

        self.assertEqual(got["m"], 16)
        self.assertEqual(got["effect_sign"], 1)
        self.assertEqual(got["same_sign"], 12)
        self.assertGreater(got["abs_stouffer_z"], 2.0)

    def test_verdict_promotes_when_one_cell_clears_gate_and_stability(self):
        strong = [self.stat(0.01, 2.0)] * 12 + [self.stat(-0.001, -0.1)] * 4
        weak = [self.stat(0.0, 0.0)] * 16
        cell_stats = {
            "funding_pre": strong,
            "funding_post": weak,
            "weekend": weak,
            "weekday": weak,
        }
        halves = {
            "funding_pre": {
                "first": {"pooled_mean": 0.004},
                "second": {"pooled_mean": 0.002},
            },
            "funding_post": {
                "first": {"pooled_mean": 0.0},
                "second": {"pooled_mean": 0.0},
            },
            "weekend": {
                "first": {"pooled_mean": 0.0},
                "second": {"pooled_mean": 0.0},
            },
            "weekday": {
                "first": {"pooled_mean": 0.0},
                "second": {"pooled_mean": 0.0},
            },
        }

        verdict = calseason_verdict(cell_stats, halves)

        self.assertEqual(verdict["status"], "closed_positive")
        self.assertEqual(verdict["winner"], "funding_pre")

    def test_verdict_closes_negative_when_no_cell_clears(self):
        weak = [self.stat(0.001, 0.2)] * 10 + [self.stat(-0.001, -0.2)] * 6
        cell_stats = {name: weak for name in
                      ("funding_pre", "funding_post", "weekend", "weekday")}
        halves = {name: {
            "first": {"pooled_mean": 0.001},
            "second": {"pooled_mean": 0.001},
        } for name in cell_stats}

        verdict = calseason_verdict(cell_stats, halves)

        self.assertEqual(verdict["status"], "closed_negative")
        self.assertIsNone(verdict["winner"])

    def test_stability_requires_both_halves_same_sign_as_full_effect(self):
        strong = [self.stat(-0.01, -2.0)] * 12 + [self.stat(0.001, 0.1)] * 4
        weak = [self.stat(0.0, 0.0)] * 16
        cell_stats = {
            "funding_pre": strong,
            "funding_post": weak,
            "weekend": weak,
            "weekday": weak,
        }
        halves = {
            "funding_pre": {
                "first": {"pooled_mean": -0.004},
                "second": {"pooled_mean": 0.001},
            },
            "funding_post": {
                "first": {"pooled_mean": 0.0},
                "second": {"pooled_mean": 0.0},
            },
            "weekend": {
                "first": {"pooled_mean": 0.0},
                "second": {"pooled_mean": 0.0},
            },
            "weekday": {
                "first": {"pooled_mean": 0.0},
                "second": {"pooled_mean": 0.0},
            },
        }

        verdict = calseason_verdict(cell_stats, halves)

        self.assertEqual(verdict["status"], "closed_negative")
