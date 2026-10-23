import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.universe_data import DailyRow
from tools.sse.sse import load_gate0_inputs, run_gate0, run_lockbox, run_prewarm

DAY = 86_400_000
H4 = 14_400_000


def _pool_and_daily():
    start = 1_577_836_800_000
    daily = {
        f"S{i:02d}USDT": [DailyRow(start - 120 * DAY + j * DAY, 100.0, 10_000.0 - i) for j in range(240)]
        for i in range(34)
    }
    prices = []
    price = 100.0
    labels = []
    for block in range(80):
        label = block % 2
        for step in range(8):
            labels.append(label)
            if step < 4:
                price += 2.0 if label == 1 else -2.0
            prices.append(price)
    btc = [
        Candle(start + i * H4, c, c + 1.0, c - 1.0, c, 1000.0)
        for i, c in enumerate(prices)
    ]
    pool = {"BTCUSDT": DataBundle(candles=btc, funding=[0.0001] * len(btc), feature=[1e6] * len(btc))}
    for i in range(34):
        drift = 0.001 * ((i % 5) - 2)
        p = 50.0 + i
        candles = []
        for j in range(len(prices)):
            p *= 1.0 + drift + (0.002 if (j + i) % 3 == 0 else -0.001)
            candles.append(Candle(start + j * H4, p, p * 1.01, p * 0.99, p, 500.0 + i))
        pool[f"S{i:02d}USDT"] = DataBundle(candles=candles)
    daily["BTCUSDT"] = [DailyRow(start - 120 * DAY + j * DAY, 100.0, 20_000.0) for j in range(240)]
    return pool, daily


class TestSseCli(unittest.TestCase):
    def test_gate0_writes_artifacts_and_pending_lockbox_state(self):
        pool, daily = _pool_and_daily()
        sealed = {"verdict": "CLOSED_NEGATIVE", "trades": 12}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = run_gate0(pool, daily, out, top_n=34, min_history_days=30, vol_days=30,
                               horizon=4, draws=20, sealed_lockbox=sealed,
                               axes_ma_period=12, axes_ret_bars=2,
                               axes_z_window=24, traj_lookback=4, traj_z_window=24)
            self.assertIn(result["verdict"], {"PENDING_GATE1", "CLOSED", "SUSPECT_HARNESS"})
            self.assertTrue((out / "gate0_verdict.json").exists())
            self.assertTrue((out / "gate0_report.md").exists())
            if result["verdict"] == "PENDING_GATE1":
                state = json.loads((out / "lockbox_state.json").read_text())
                self.assertEqual(state["sealed_result"], sealed)

    def test_lockbox_is_one_touch(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "lockbox_state.json").write_text(json.dumps({"sealed_result": {"verdict": "CLOSED_NEGATIVE"}}))
            self.assertIn("REFUSED", run_lockbox(out, ack=False))
            self.assertIn("LOCKBOX", run_lockbox(out, ack=True))
            self.assertIn("REFUSED", run_lockbox(out, ack=True))

    def test_prewarm_reports_cache_stats(self):
        with patch("tools.sse.sse.load_gate0_inputs", return_value=({"BTCUSDT": object()}, {"BTCUSDT": [1]}, {
            "symbol_count": 10,
            "union_count": 4,
            "loaded_4h_count": 3,
        })):
            result = run_prewarm("cache/swing", 0, H4)
        self.assertEqual(result["symbol_count"], 10)
        self.assertEqual(result["union_count"], 4)
        self.assertEqual(result["loaded_4h_count"], 3)
        self.assertEqual(result["daily_loaded_count"], 1)
        self.assertEqual(result["pool_count"], 1)
        self.assertTrue(result["btc_ready"])

    def test_load_gate0_inputs_backfills_daily_window_without_network_listing(self):
        start_ms = 100 * DAY
        end_ms = start_ms + 40 * H4
        daily_rows = [DailyRow(start_ms - 120 * DAY + i * DAY, 100.0 + i, 1000.0) for i in range(140)]
        btc = [Candle(start_ms + i * H4, 100.0, 101.0, 99.0, 100.0, 1000.0) for i in range(40)]
        alt = [Candle(start_ms + i * H4, 50.0, 51.0, 49.0, 50.0, 500.0) for i in range(40)]
        with patch("tools.sse.sse._cached_daily_symbols", return_value=["ALTUSDT", "BTCUSDT"]), \
             patch("tools.sse.sse.list_um_perp_symbols") as listing, \
             patch("tools.sse.sse.fetch_daily_klines", return_value=daily_rows) as fetch_daily, \
             patch("tools.sse.sse.fetch_perp_candles", side_effect=[btc, alt]), \
             patch("tools.sse.sse.default_readers", return_value={
                 "funding": lambda sym: [0.0001] * len(btc),
                 "metrics": lambda sym, field: [1.0] * len(btc),
             }):
            pool, daily, meta = load_gate0_inputs("cache/swing", start_ms, end_ms)
        listing.assert_not_called()
        fetch_daily.assert_any_call("BTCUSDT", start_ms, end_ms, "cache/swing")
        fetch_daily.assert_any_call("ALTUSDT", start_ms, end_ms, "cache/swing")
        self.assertIn("BTCUSDT", pool)
        self.assertIn("ALTUSDT", daily)
        self.assertEqual(meta["symbol_count"], 2)
        self.assertGreaterEqual(meta["loaded_4h_count"], 1)
        self.assertGreaterEqual(meta["union_count"], 1)


if __name__ == "__main__":
    unittest.main()
