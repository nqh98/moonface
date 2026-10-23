import unittest

from moonface.core.models import Candle
from moonface.research import funding_fade_fwd as fwd


def _candles(n: int, start_ms: int = 1_600_000_000_000) -> list[Candle]:
    """4h candles trending +0.1/bar with 1.0 range, so ATR(14) == 1.0."""
    out = []
    for i in range(n):
        close = 100.0 + 0.1 * i
        out.append(Candle(timestamp_ms=start_ms + i * 14_400_000,
                          open=close - 0.05, high=close + 0.5,
                          low=close - 0.5, close=close, volume=1.0))
    return out


def _funding_with_spikes(n: int, spikes: list[int]) -> list[float | None]:
    """Alternating ±1e-4 (z==±1, below z_thr 1.5) with +1e-2 spikes (z >> 1.5)."""
    base = [1e-4 if i % 2 == 0 else -1e-4 for i in range(n)]
    for i in spikes:
        base[i] = 1e-2
    return base


class CutoffClampTest(unittest.TestCase):
    def test_rejects_post_cutoff_candle(self):
        good = _candles(3, start_ms=fwd.CUTOFF_MS - 10 * 14_400_000)
        bad = _candles(3, start_ms=fwd.CUTOFF_MS)
        with self.assertRaises(fwd.CutoffViolation):
            fwd.assert_pre_cutoff(good + bad, [])

    def test_rejects_post_cutoff_funding(self):
        with self.assertRaises(fwd.CutoffViolation):
            fwd.assert_pre_cutoff([], [(fwd.CUTOFF_MS, 1e-4)])

    def test_accepts_pre_cutoff(self):
        candles = _candles(3, start_ms=fwd.CUTOFF_MS - 10 * 14_400_000)
        fwd.assert_pre_cutoff(candles, [(fwd.CUTOFF_MS - 1, 1e-4)])  # no raise


class RegenerateTest(unittest.TestCase):
    def test_synthetic_entries_split_and_r_values(self):
        n = 1300  # tail_start = 1300 - 1095 = 205
        candles = _candles(n)
        funding = _funding_with_spikes(n, spikes=[200, 250])
        streams = fwd.regenerate(candles, funding)
        # spike 200 -> research (200 < 205); spike 250 -> tail. SHORT into a
        # rising series stops out at exactly -k_stop = -2.0 R (ATR units).
        self.assertEqual(len(streams.research), 1)
        self.assertEqual(len(streams.tail), 1)
        self.assertEqual(streams.research[0][0], candles[200].timestamp_ms)
        self.assertEqual(streams.research[0][1], -2.0)
        self.assertEqual(streams.tail[0][0], candles[250].timestamp_ms)
        self.assertEqual(streams.tail[0][1], -2.0)

    def test_reproduction_report_mismatch_and_match(self):
        streams = fwd.Streams(research=[(0, 1.0)], tail=[(1, 1.0)])
        ok, got = fwd.reproduction_report(streams)
        self.assertFalse(ok)
        self.assertEqual(got["research_trades"], 1)
        self.assertEqual(set(got), set(fwd.BASELINE))


class AmendmentOneTest(unittest.TestCase):
    def test_baseline_differs_from_archived_only_in_oos_aggregates(self):
        # Amendment 1 (2026-07-14): completed-candle re-baseline touches ONLY
        # the two figures the forming-candle snapshot contaminated.
        diff = {k for k in fwd.ARCHIVED if fwd.ARCHIVED[k] != fwd.BASELINE[k]}
        self.assertEqual(diff, {"oos_net_r", "oos_expectancy_r"})
        self.assertEqual(fwd.BASELINE["oos_net_r"], 77.3435)
        self.assertEqual(fwd.BASELINE["oos_expectancy_r"], 1.1374)

    def test_forward_window_opens_0800z(self):
        # First bar with open time >= 2026-06-10T08:00:00Z; excludes the
        # 04:00-08:00Z bar assigned to the baseline side.
        self.assertEqual(fwd.FORWARD_START_MS - fwd.CUTOFF_MS,
                         (8 * 3600 - (6 * 3600 + 51 * 60 + 46)) * 1000)
        self.assertEqual(fwd.FORWARD_START_MS % 14_400_000, 8 * 3600 * 1000 % 14_400_000)


class IdentityHashTest(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(fwd.identity_hash(-50.0, 123, 12),
                         fwd.identity_hash(-50.0, 123, 12))

    def test_sensitive_to_budget_and_trigger(self):
        base = fwd.identity_hash(-50.0, 123, 12)
        self.assertNotEqual(base, fwd.identity_hash(-40.0, 123, 12))
        self.assertNotEqual(base, fwd.identity_hash(-50.0, 124, 12))

    def test_is_hex_sha256(self):
        h = fwd.identity_hash(-50.0, 123, 12)
        self.assertEqual(len(h), 64)
        int(h, 16)  # parses as hex
