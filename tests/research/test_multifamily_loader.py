import unittest

from moonface.core.models import Candle
from moonface.research.multifamily_loader import (default_readers,
                                                  load_pool_bundles)

import pytest

pytestmark = pytest.mark.slow

H4 = 4 * 3_600_000


def _candles(n):
    return [Candle(i * H4, 100, 101, 99, 100 + i, 1000.0) for i in range(n)]


class TestLoadPoolBundles(unittest.TestCase):
    def _readers(self):
        candles = _candles(40)
        return {
            "candles": lambda sym, tf: candles,
            "funding": lambda sym: [0.01] * 40,
            "metrics": lambda sym, field: [5.0] * 40,
            "bookdepth": lambda sym: [0.5] * 40,
        }

    def test_builds_bundle_per_symbol(self):
        pool = load_pool_bundles(
            ["DOGEUSDT", "XRPUSDT"], metrics_field="sum_open_interest",
            **self._readers())
        self.assertEqual(set(pool), {"DOGEUSDT", "XRPUSDT"})
        b = pool["DOGEUSDT"]
        self.assertEqual(len(b.candles), 40)
        self.assertIsNotNone(b.funding)
        self.assertIsNotNone(b.feature)
        self.assertIsNotNone(b.bookdepth)

    def test_symbol_without_candles_is_omitted(self):
        readers = self._readers()
        readers["candles"] = lambda sym, tf: ([] if sym == "BAD"
                                              else _candles(40))
        pool = load_pool_bundles(["GOOD", "BAD"],
                                 metrics_field="sum_open_interest", **readers)
        self.assertIn("GOOD", pool)
        self.assertNotIn("BAD", pool)

    def test_missing_optional_series_left_none(self):
        readers = self._readers()
        readers["funding"] = lambda sym: None
        readers["bookdepth"] = lambda sym: None
        pool = load_pool_bundles(["DOGEUSDT"],
                                 metrics_field="sum_open_interest", **readers)
        b = pool["DOGEUSDT"]
        self.assertIsNone(b.funding)
        self.assertIsNone(b.bookdepth)
        self.assertIsNotNone(b.feature)

    def test_symbol_with_only_candles_still_in_pool(self):
        # omit ONLY on empty candles: a symbol with a price series but every
        # optional series None must still appear, so the per-family screen can
        # drop it for the families it lacks data for (not lose the symbol).
        readers = self._readers()
        readers["funding"] = lambda sym: None
        readers["metrics"] = lambda sym, field: None
        readers["bookdepth"] = lambda sym: None
        pool = load_pool_bundles(["DOGEUSDT"],
                                 metrics_field="sum_open_interest", **readers)
        self.assertIn("DOGEUSDT", pool)
        b = pool["DOGEUSDT"]
        self.assertEqual(len(b.candles), 40)
        self.assertIsNone(b.funding)
        self.assertIsNone(b.feature)
        self.assertIsNone(b.bookdepth)


class TestDefaultReaders(unittest.TestCase):
    def test_returns_four_callables(self):
        r = default_readers(cache_dir=".backtest_cache",
                            start_ms=0, end_ms=H4 * 10)
        for key in ("candles", "funding", "metrics", "bookdepth"):
            self.assertTrue(callable(r[key]))

    def test_optional_readers_swallow_missing_files(self):
        r = default_readers(cache_dir="/tmp/does-not-exist-xyz",
                            start_ms=0, end_ms=H4 * 10)
        # missing cache dir -> optional readers return None, never raise
        self.assertIsNone(r["funding"]("NOPEUSDT"))
        self.assertIsNone(r["metrics"]("NOPEUSDT", "sum_open_interest"))
        self.assertIsNone(r["bookdepth"]("NOPEUSDT"))
