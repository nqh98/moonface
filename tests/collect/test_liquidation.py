import unittest
from pathlib import Path
import tempfile

from moonface.collect.liquidation import (
    LiquidationRow, parse_force_order, append_rows, snapshot_stats,
    write_manifest, rows_from_liquidations, CLUSTER_GAP_MS)


def _msg(symbol, side, qty, price, ts):
    return {"e": "forceOrder", "o": {"s": symbol, "S": side, "q": str(qty),
                                     "ap": str(price), "T": ts}}


class TestParse(unittest.TestCase):
    def test_parse_force_order(self):
        row = parse_force_order(_msg("BTCUSDT", "SELL", 0.5, 60000, 1000), 1001)
        self.assertEqual(row.symbol, "BTCUSDT")
        self.assertEqual(row.side, "SELL")
        self.assertAlmostEqual(row.qty, 0.5)
        self.assertAlmostEqual(row.price, 60000.0)
        self.assertAlmostEqual(row.notional, 30000.0)
        self.assertEqual(row.ts_ms, 1000)

    def test_non_force_order_returns_none(self):
        self.assertIsNone(parse_force_order({"e": "trade"}, 5))
        self.assertIsNone(parse_force_order({"e": "forceOrder", "o": {}}, 5))


class TestStore(unittest.TestCase):
    def test_append_and_stats_with_cascade_clusters(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "liq_BTCUSDT.csv"
            day = 86_400_000
            rows = [
                LiquidationRow(day, "BTCUSDT", "SELL", 60000, 0.1, 6000),
                LiquidationRow(day + 1000, "BTCUSDT", "SELL", 60000, 0.1, 6000),
                LiquidationRow(day + CLUSTER_GAP_MS + 5000, "BTCUSDT", "BUY",
                               61000, 0.2, 12200),               # new cluster
                LiquidationRow(3 * day, "BTCUSDT", "SELL", 59000, 0.3, 17700),
            ]
            self.assertEqual(append_rows(path, rows), 4)
            stats = snapshot_stats(path)
            self.assertEqual(stats["rows"], 4)
            self.assertEqual(stats["days"], 2)
            self.assertEqual(stats["cascade_clusters"], 3)
            self.assertEqual(stats["first_ts_ms"], day)

    def test_cascade_clusters_are_order_independent(self):
        # Rows appended OUT OF ORDER (the real cross-restart scenario). The same
        # 4 events as above must still yield 3 clusters -> guards the sorted()
        # in snapshot_stats against a future regression.
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "liq_BTCUSDT.csv"
            day = 86_400_000
            shuffled = [
                LiquidationRow(3 * day, "BTCUSDT", "SELL", 59000, 0.3, 17700),
                LiquidationRow(day + CLUSTER_GAP_MS + 5000, "BTCUSDT", "BUY",
                               61000, 0.2, 12200),
                LiquidationRow(day, "BTCUSDT", "SELL", 60000, 0.1, 6000),
                LiquidationRow(day + 1000, "BTCUSDT", "SELL", 60000, 0.1, 6000),
            ]
            append_rows(path, shuffled)
            stats = snapshot_stats(path)
            self.assertEqual(stats["cascade_clusters"], 3)
            self.assertEqual(stats["days"], 2)
            self.assertEqual(stats["first_ts_ms"], day)

    def test_manifest_written(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "liq_BTCUSDT.csv"
            append_rows(path, [LiquidationRow(86_400_000, "BTCUSDT", "SELL",
                                              60000, 0.1, 6000)])
            mpath = write_manifest(Path(d), "BTCUSDT", snapshot_stats(path))
            self.assertTrue(mpath.exists())


if __name__ == "__main__":
    unittest.main()


class TestRowsFromLiquidations(unittest.TestCase):
    """The collector subscribes to the all-market !forceOrder@arr firehose (a
    per-symbol channel is too sparse to keep the ws keepalive satisfied — see
    experiments/COLLECTOR_AUDIT_2026-07-29.md), so the firehose carries every
    symbol and the declared BTCUSDT scope must be enforced here."""

    def _liq(self, symbol, side, qty, price, ts):
        return {"info": _msg(symbol, side, qty, price, ts)}

    def test_keeps_only_the_requested_symbol(self):
        liqs = [self._liq("BTCUSDT", "SELL", 1.0, 60000, 1000),
                self._liq("ETHUSDT", "BUY", 10.0, 3000, 1001),
                self._liq("SOLUSDT", "SELL", 100.0, 150, 1002)]
        rows = rows_from_liquidations(liqs, 2000, symbol="BTCUSDT")
        self.assertEqual([r.symbol for r in rows], ["BTCUSDT"])

    def test_symbol_none_keeps_everything(self):
        liqs = [self._liq("BTCUSDT", "SELL", 1.0, 60000, 1000),
                self._liq("ETHUSDT", "BUY", 10.0, 3000, 1001)]
        rows = rows_from_liquidations(liqs, 2000, symbol=None)
        self.assertEqual([r.symbol for r in rows], ["BTCUSDT", "ETHUSDT"])

    def test_unparseable_entries_are_dropped_not_raised(self):
        liqs = [{"info": {"e": "trade"}},
                {},
                self._liq("BTCUSDT", "SELL", 1.0, 60000, 1000)]
        rows = rows_from_liquidations(liqs, 2000, symbol="BTCUSDT")
        self.assertEqual(len(rows), 1)

    def test_empty_batch_is_empty_list(self):
        self.assertEqual(rows_from_liquidations([], 2000, symbol="BTCUSDT"), [])


class TestCcxtInfoShape(unittest.TestCase):
    """ccxt's unified liquidation puts the INNER order object in `info` — no
    "e" key, and its own "o" key means order TYPE ("LIMIT"), not a nested
    order. parse_force_order returns None for this shape; that mismatch is why
    the collector wrote zero rows for 16 days. Real frame captured live
    2026-07-29 from !forceOrder@arr."""

    LIVE = {"s": "SKHYNIXUSDT", "S": "SELL", "o": "LIMIT", "f": "IOC",
            "q": "5.93", "p": "947.74000", "ap": "956.89854", "X": "FILLED",
            "l": "0.28", "z": "5.93", "T": 1785293912808,
            "ps": "SKHYNIXUSDT", "st": 1}

    def test_parse_force_order_rejects_the_ccxt_shape(self):
        # the regression that hid for 16 days
        self.assertIsNone(parse_force_order(self.LIVE, 1))

    def test_rows_from_liquidations_accepts_the_ccxt_shape(self):
        rows = rows_from_liquidations([{"info": self.LIVE}], 1, symbol=None)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.symbol, "SKHYNIXUSDT")
        self.assertEqual(r.side, "SELL")
        self.assertAlmostEqual(r.qty, 5.93)
        self.assertAlmostEqual(r.price, 956.89854)   # ap preferred over p
        self.assertEqual(r.ts_ms, 1785293912808)
        self.assertAlmostEqual(r.notional, 5.93 * 956.89854)

    def test_order_type_key_is_not_mistaken_for_a_nested_order(self):
        # LIVE["o"] == "LIMIT" (a str). Treating it as a nested dict must not raise.
        rows = rows_from_liquidations([{"info": self.LIVE}], 1, symbol="SKHYNIXUSDT")
        self.assertEqual(len(rows), 1)

    def test_both_shapes_in_one_batch(self):
        batch = [{"info": self.LIVE},
                 {"info": _msg("BTCUSDT", "BUY", 2.0, 50000, 900)}]
        rows = rows_from_liquidations(batch, 1, symbol=None)
        self.assertEqual([r.symbol for r in rows], ["SKHYNIXUSDT", "BTCUSDT"])

    def test_ccxt_shape_still_honours_the_symbol_filter(self):
        rows = rows_from_liquidations([{"info": self.LIVE}], 1, symbol="BTCUSDT")
        self.assertEqual(rows, [])
