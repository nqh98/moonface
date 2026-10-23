import datetime as dt
import unittest

from moonface.core.metrics import COST_FRACTION
from moonface.core.models import Candle
from moonface.research.macro_event import (
    ALPHA_BONFERRONI,
    CELLS,
    CPI_DATES,
    FOMC_DATES,
    bootstrap_p_le0,
    cell_returns,
    cell_summary,
    event_ts_ms,
    macro_event_verdict,
    price_at,
    window_return,
)

_HOUR_MS = 3_600_000


def _utc_ms(year, month, day, hour=0, minute=0):
    return int(dt.datetime(year, month, day, hour, minute,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)


def _flat_candles(start_ms, hours, close=100.0):
    return [Candle(start_ms + i * _HOUR_MS, close, close, close, close, 1.0)
            for i in range(hours)]


class TestCalendars(unittest.TestCase):
    def test_frozen_event_counts(self):
        self.assertEqual(len(FOMC_DATES), 36)
        self.assertEqual(len(CPI_DATES), 53)
        self.assertEqual(CELLS, ("fomc_pre24h", "fomc_post24h",
                                 "cpi_pre24h", "cpi_post24h"))

    def test_fomc_dst_conversion(self):
        ts = event_ts_ms("fomc")
        # 2022-01-26 (EST): 14:00 ET = 19:00 UTC
        self.assertIn(_utc_ms(2022, 1, 26, 19, 0), ts)
        # 2022-06-15 (EDT): 14:00 ET = 18:00 UTC
        self.assertIn(_utc_ms(2022, 6, 15, 18, 0), ts)

    def test_cpi_dst_conversion(self):
        ts = event_ts_ms("cpi")
        # 2022-01-12 (EST): 08:30 ET = 13:30 UTC
        self.assertIn(_utc_ms(2022, 1, 12, 13, 30), ts)
        # 2022-06-10 (EDT): 08:30 ET = 12:30 UTC
        self.assertIn(_utc_ms(2022, 6, 10, 12, 30), ts)

    def test_events_chronological(self):
        for event_type in ("fomc", "cpi"):
            ts = event_ts_ms(event_type)
            self.assertEqual(ts, sorted(ts))


class TestWindowReturns(unittest.TestCase):
    def test_price_at_uses_only_completed_bars(self):
        c = _flat_candles(_utc_ms(2026, 1, 1), 3)
        c[1] = Candle(c[1].timestamp_ms, 100.0, 100.0, 100.0, 111.0, 1.0)
        # at the open of bar 1 only bar 0 is complete
        self.assertEqual(price_at(c, _utc_ms(2026, 1, 1, 1)), 100.0)
        # once bar 1 completes its close becomes visible
        self.assertEqual(price_at(c, _utc_ms(2026, 1, 1, 2)), 111.0)
        # before any bar completes there is no price
        self.assertIsNone(price_at(c, _utc_ms(2026, 1, 1, 0, 30)))

    def test_window_return_close_to_close(self):
        candles = []
        close = 100.0
        for i in range(72):
            close *= 1.001
            candles.append(Candle(_utc_ms(2026, 1, 1) + i * _HOUR_MS,
                                  close, close, close, close, 1.0))
        a = _utc_ms(2026, 1, 2)
        r = window_return(candles, a, a + 24 * _HOUR_MS)
        self.assertAlmostEqual(r, 1.001 ** 24 - 1.0, places=10)

    def test_missing_data_returns_none(self):
        c = _flat_candles(_utc_ms(2026, 1, 1), 3)
        self.assertIsNone(window_return(c, _utc_ms(2025, 1, 1),
                                        _utc_ms(2025, 1, 2)))


class TestCellReturns(unittest.TestCase):
    def test_pre_and_post_windows_and_cost(self):
        # +1% every hour during 2022-01-26 (FOMC day, 19:00 UTC), flat after
        t0 = _utc_ms(2022, 1, 26, 19)
        start = t0 - 30 * _HOUR_MS
        candles = []
        close = 100.0
        for i in range(60):
            ts = start + i * _HOUR_MS
            if ts < t0:
                close *= 1.01
            candles.append(Candle(ts, close, close, close, close, 1.0))
        pre = cell_returns(candles, "fomc", "pre24h")
        post = cell_returns(candles, "fomc", "post24h")
        self.assertEqual(len(pre), 1)  # only this event has data
        self.assertEqual(len(post), 1)
        self.assertAlmostEqual(pre[0], 1.01 ** 24 - 1.0 - COST_FRACTION, places=9)
        self.assertAlmostEqual(post[0], -COST_FRACTION, places=9)


class TestGate(unittest.TestCase):
    def test_bootstrap_deterministic_and_sane(self):
        strong = [0.01] * 25
        self.assertEqual(bootstrap_p_le0(strong), 0.0)
        noise = [0.01, -0.01] * 15
        p1 = bootstrap_p_le0(noise)
        p2 = bootstrap_p_le0(noise)
        self.assertEqual(p1, p2)  # frozen seed
        self.assertGreater(p1, ALPHA_BONFERRONI)
        self.assertEqual(bootstrap_p_le0([]), 1.0)

    def test_cell_summary_gate_conjunctive(self):
        good = cell_summary([0.01] * 30)
        self.assertTrue(good["clears_gate"])
        self.assertEqual(good["n"], 30)
        # underpowered: same effect, n below the floor
        self.assertFalse(cell_summary([0.01] * 10)["clears_gate"])
        # halves flip: strong first half, negative second
        flip = cell_summary([0.02] * 15 + [-0.001] * 15)
        self.assertFalse(flip["halves_sign_ok"])
        self.assertFalse(flip["clears_gate"])
        # negative mean never clears
        self.assertFalse(cell_summary([-0.01] * 30)["clears_gate"])

    def test_verdict_kill_rule_and_winner(self):
        dead = {name: cell_summary([-0.001] * 30) for name in CELLS}
        v = macro_event_verdict(dead)
        self.assertEqual(v["status"], "closed_negative")
        self.assertIsNone(v["winner"])
        self.assertIn("family CLOSED", v["reason"])

        cells = dict(dead)
        cells["cpi_post24h"] = cell_summary([0.012] * 30)
        cells["fomc_pre24h"] = cell_summary([0.008] * 30)
        v = macro_event_verdict(cells)
        self.assertEqual(v["status"], "forward_candidate")
        self.assertEqual(v["winner"], "cpi_post24h")  # largest net mean
