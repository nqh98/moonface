import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import urllib.error

from tools.recon_stablecoin_peg import (
    _run_probe,
    build_parser,
    coinbase_candles_span,
    coverage_report,
    kraken_pairs_present,
    ohlc_bar_span,
    premium_stats,
    trades_page_span,
    trades_to_bars,
)


class TestKrakenPairsPresent(unittest.TestCase):
    def test_maps_present_and_absent_pairs(self):
        result = {
            "USDTZUSD": {"altname": "USDTUSD"},
            "USDCUSD": {"altname": "USDCUSD"},
            "XXBTZUSD": {"altname": "XBTUSD"},
        }
        wanted = {
            "USDT/USD": ("USDTZUSD", "USDTUSD"),
            "USDC/USD": ("USDCZUSD", "USDCUSD"),
            "DAI/USD": ("DAIUSD",),
        }
        out = kraken_pairs_present(result, wanted)
        self.assertEqual(out["USDT/USD"], "USDTZUSD")
        self.assertEqual(out["USDC/USD"], "USDCUSD")
        self.assertIsNone(out["DAI/USD"])


if __name__ == "__main__":
    unittest.main()


class TestHistoryCap(unittest.TestCase):
    def test_ohlc_bar_span_ignores_last_cursor(self):
        result = {
            "USDTZUSD": [
                [1000, "1.0", "1.0", "1.0", "1.0", "1.0", "5", 3],
                [1060, "1.0", "1.0", "1.0", "1.0", "1.0", "7", 4],
                [1120, "1.0", "1.0", "1.0", "1.0", "1.0", "2", 1],
            ],
            "last": 1120,
        }
        out = ohlc_bar_span(result)
        self.assertEqual(out["pair"], "USDTZUSD")
        self.assertEqual(out["bars"], 3)
        self.assertEqual(out["first_ts"], 1000)
        self.assertEqual(out["last_ts"], 1120)
        self.assertEqual(out["span_s"], 120)

    def test_coinbase_candles_span_and_volume(self):
        candles = [
            [1783566240, 0.99891, 0.99905, 0.99891, 0.99905, 3253.63],
            [1783566180, 0.99880, 0.99900, 0.99885, 0.99891, 1200.0],
        ]
        out = coinbase_candles_span(candles)
        self.assertEqual(out["bars"], 2)
        self.assertEqual(out["newest_ts"], 1783566240)
        self.assertEqual(out["oldest_ts"], 1783566180)
        self.assertEqual(out["span_s"], 60)
        self.assertTrue(out["all_have_volume"])

    def test_coinbase_flags_zero_volume(self):
        candles = [[1783566240, 1.0, 1.0, 1.0, 1.0, 0.0]]
        self.assertFalse(coinbase_candles_span(candles)["all_have_volume"])


class TestQualityAnalyzers(unittest.TestCase):
    def test_coverage_perfect_grid(self):
        ts = [0, 60, 120, 180]
        out = coverage_report(ts, 60)
        self.assertTrue(out["monotonic"])
        self.assertEqual(out["expected"], 4)
        self.assertEqual(out["present"], 4)
        self.assertEqual(out["coverage"], 1.0)
        self.assertEqual(out["gaps"], 0)
        self.assertEqual(out["longest_gap_bars"], 0)

    def test_coverage_with_gap(self):
        ts = [0, 60, 300]
        out = coverage_report(ts, 60)
        self.assertEqual(out["expected"], 6)
        self.assertEqual(out["present"], 3)
        self.assertEqual(out["gaps"], 1)
        self.assertEqual(out["longest_gap_bars"], 3)
        self.assertEqual(out["coverage"], 0.5)

    def test_coverage_flags_non_monotonic(self):
        self.assertFalse(coverage_report([0, 120, 60], 60)["monotonic"])

    def test_premium_stats_bps_and_crosses(self):
        prices = [1.0000, 1.0002, 0.9999]
        out = premium_stats(prices)
        self.assertEqual(out["n"], 3)
        self.assertEqual(out["max_bps"], 2.0)
        self.assertEqual(out["min_bps"], -1.0)
        self.assertEqual(out["peg_crosses"], 1)

    def test_premium_stats_empty(self):
        self.assertEqual(premium_stats([])["n"], 0)


class TestTradesPath(unittest.TestCase):
    def test_trades_to_bars_buckets_ohlcv(self):
        trades = [
            ["1.0001", "10", 100.0, "b", "l", "", 1],
            ["1.0003", "5", 110.0, "s", "m", "", 2],
            ["0.9999", "2", 190.0, "b", "l", "", 3],
        ]
        bars = trades_to_bars(trades, 60)
        self.assertEqual(len(bars), 2)
        first = bars[0]
        self.assertEqual(first["ts"], 60)
        self.assertEqual(first["open"], 1.0001)
        self.assertEqual(first["close"], 1.0003)
        self.assertEqual(first["high"], 1.0003)
        self.assertEqual(first["low"], 1.0001)
        self.assertEqual(first["volume"], 15.0)
        self.assertEqual(bars[1]["ts"], 180)

    def test_trades_page_span_reads_cursor(self):
        result = {
            "USDTZUSD": [
                ["1.0", "1", 100.0, "b", "l", "", 1],
                ["1.0", "1", 400.0, "s", "l", "", 2],
            ],
            "last": "1783566240123456789",
        }
        out = trades_page_span(result)
        self.assertEqual(out["trades"], 2)
        self.assertEqual(out["first_ts"], 100.0)
        self.assertEqual(out["last_ts"], 400.0)
        self.assertEqual(out["span_s"], 300.0)
        self.assertEqual(out["cursor"], "1783566240123456789")


class TestCLI(unittest.TestCase):
    def test_probe_defaults(self):
        args = build_parser().parse_args(["probe"])
        self.assertEqual(args.cmd, "probe")
        self.assertEqual(args.interval, 1)
        self.assertEqual(args.granularity, 60)

    def test_probe_accepts_overrides(self):
        args = build_parser().parse_args(["probe", "--interval", "5"])
        self.assertEqual(args.interval, 5)

    def test_probe_continues_when_coinbase_product_is_absent(self):
        out = StringIO()

        def fake_coinbase(product, granularity):
            if product == "USDC-USD":
                raise urllib.error.HTTPError(product, 404, "Not Found", None, None)
            return [
                [1783566240, 0.99891, 0.99905, 0.99891, 0.99905, 3253.63],
                [1783566180, 0.99880, 0.99900, 0.99885, 0.99891, 1200.0],
            ]

        with (
            patch("tools.recon_stablecoin_peg.fetch_kraken_assetpairs", return_value={}),
            patch("tools.recon_stablecoin_peg.fetch_coinbase_candles", side_effect=fake_coinbase),
            redirect_stdout(out),
        ):
            _run_probe(1, 60)

        printed = out.getvalue()
        self.assertIn("Coinbase USDT-USD g=60s: 2 bars", printed)
        self.assertIn("Coinbase USDC-USD: ABSENT (HTTP 404)", printed)
