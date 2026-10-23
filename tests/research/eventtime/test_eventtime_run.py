import json
import math
import random
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from moonface.research.eventtime.vision_klines import MinuteBar
from tools.eventtime.eventtime import DESIGN, cmd_register
from tools.eventtime.eventtime_run import cmd_run, compute


def make_clock_candles(n: int, step_ms: int, seed: int, drift: float) -> list[Candle]:
    rng = random.Random(seed)
    out: list[Candle] = []
    price = 100.0
    start = DESIGN["test_start_ms"]
    for i in range(n):
        ret = rng.gauss(drift, 0.01)
        close = price * math.exp(ret)
        high = max(price, close) * 1.002
        low = min(price, close) * 0.998
        out.append(Candle(start + i * step_ms, price, high, low, close, 1000.0))
        price = close
    return out


def make_minute_bars(
    start_ms: int,
    n: int,
    seed: int,
    drift: float,
    quote_volume: float,
) -> list[MinuteBar]:
    rng = random.Random(seed)
    out: list[MinuteBar] = []
    price = 100.0
    for i in range(n):
        ret = rng.gauss(drift, 0.002)
        close = price * math.exp(ret)
        high = max(price, close) * 1.001
        low = min(price, close) * 0.999
        base_volume = quote_volume / max((price + close) / 2.0, 1e-9)
        out.append(
            MinuteBar(
                ts_ms=start_ms + i * 60_000,
                open=price,
                high=high,
                low=low,
                close=close,
                base_volume=base_volume,
                quote_volume=quote_volume,
            )
        )
        price = close
    return out


def make_loaders() -> dict:
    calib_minutes = make_minute_bars(
        DESIGN["calib_start_ms"],
        600,
        seed=11,
        drift=0.0001,
        quote_volume=1.0,
    )
    test_minutes = make_minute_bars(
        DESIGN["test_start_ms"],
        4800,
        seed=17,
        drift=0.0004,
        quote_volume=120.0,
    )
    clock = make_clock_candles(1200, 14_400_000, seed=23, drift=0.003)

    def load_calib_minutes() -> list[MinuteBar]:
        return list(calib_minutes)

    def load_test_minutes() -> list[MinuteBar]:
        return list(test_minutes)

    def load_clock_4h() -> list[Candle]:
        return list(clock)

    return {
        "calib_minutes": load_calib_minutes,
        "test_minutes": load_test_minutes,
        "clock_4h": load_clock_4h,
    }


class ComputeTest(unittest.TestCase):
    def test_compute_returns_expected_shapes(self):
        result = compute(dict(DESIGN, test_end_ms=DESIGN["test_start_ms"] + 4800 * 60_000), make_loaders())

        self.assertIn("bar_size", result)
        self.assertIn("n_dollar_bars", result)
        self.assertIn("n_clock_bars", result)
        self.assertIn("clock_rows", result)
        self.assertIn("dollar_rows", result)
        self.assertIn("ladder", result)
        self.assertIn("verdict", result)
        self.assertGreater(result["bar_size"], 0.0)
        self.assertGreater(result["n_dollar_bars"], 0)
        self.assertEqual(result["n_clock_bars"], 1200)
        self.assertEqual(len(result["clock_rows"]), len(DESIGN["exit_rows"]))
        self.assertEqual(len(result["dollar_rows"]), len(DESIGN["exit_rows"]))
        self.assertIn("ladder_pass", result["ladder"])
        self.assertIn(result["verdict"]["verdict"], ("pass", "kill"))


class RunTest(unittest.TestCase):
    def test_cmd_run_writes_and_refuses_second_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "eventtime"
            cmd_register(out, now_ms=DESIGN["test_start_ms"] + 4800 * 60_000)

            result = cmd_run(out, cache_dir=tmp, loaders=make_loaders())

            written = json.loads((out / "results.json").read_text())
            self.assertEqual(written["verdict"], result["verdict"])
            self.assertTrue((out / "RESULT.md").exists())

            with self.assertRaises(SystemExit):
                cmd_run(out, cache_dir=tmp, loaders=make_loaders())

    def test_cmd_run_requires_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                cmd_run(Path(tmp) / "eventtime", cache_dir=tmp, loaders=make_loaders())


if __name__ == "__main__":
    unittest.main()
