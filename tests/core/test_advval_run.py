import json
import math
import random
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from tools.advval.advval import DESIGN, cmd_register
from tools.advval.advval_run import cmd_run, compute_cell_aucs

import pytest

pytestmark = pytest.mark.slow

H4 = 14_400_000
D1 = 86_400_000
F8 = 28_800_000
SPLIT = DESIGN["era_split_ms"]


def synth_candles(n, step, drift_shift_after_split, seed):
    rng = random.Random(seed)
    start = SPLIT - (n // 2) * step
    out, price = [], 100.0
    for i in range(n):
        ts = start + i * step
        shift = drift_shift_after_split if ts >= SPLIT else 0.0
        r = rng.gauss(shift, 0.02)
        new = price * math.exp(r)
        hi, lo = max(price, new) * 1.001, min(price, new) * 0.999
        out.append(Candle(ts, price, hi, lo, new, abs(rng.gauss(100, 10))))
        price = new
    return out


def make_loaders(shift=0.03, seed=5):
    c4 = synth_candles(1200, H4, shift, seed)
    c1 = synth_candles(600, D1, shift, seed + 1)
    rng = random.Random(seed + 2)
    start = SPLIT - 600 * F8
    funding = [(start + i * F8, rng.gauss(0.0001, 0.0002)) for i in range(1200)]
    oi = [100.0]
    for _ in range(1, len(c4)):
        oi.append(oi[-1] * math.exp(rng.gauss(0, 0.01)))
    return {
        "candles": lambda interval: c4 if interval == "4h" else c1,
        "funding": lambda: funding,
        "oi": lambda candles: list(oi[: len(candles)]),
    }


class ComputeTest(unittest.TestCase):
    def test_all_cells_present_with_counts(self):
        cells = compute_cell_aucs(dict(DESIGN), make_loaders())
        self.assertEqual(sorted(cells), sorted(DESIGN["cells"]))
        for name, cell in cells.items():
            self.assertGreater(cell["n_era0"], 50, name)
            self.assertGreater(cell["n_era1"], 50, name)
            self.assertTrue(0.0 <= cell["auc"] <= 1.0, name)

    def test_shifted_price_cell_detects(self):
        cells = compute_cell_aucs(dict(DESIGN), make_loaders(shift=0.05))
        self.assertGreater(cells["price_4h"]["auc"], 0.7)


class RunTest(unittest.TestCase):
    def test_one_touch_run_writes_and_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "advval"
            cmd_register(out, now_ms=SPLIT + 600 * H4)
            res = cmd_run(out, cache_dir=tmp, loaders=make_loaders())
            self.assertIn(res["retrodiction"]["verdict"], ("pass", "kill"))
            written = json.loads((out / "results.json").read_text())
            self.assertEqual(
                written["retrodiction"]["verdict"],
                res["retrodiction"]["verdict"],
            )
            self.assertTrue((out / "RESULT.md").exists())
            with self.assertRaises(SystemExit):
                cmd_run(out, cache_dir=tmp, loaders=make_loaders())

    def test_run_requires_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                cmd_run(Path(tmp) / "advval", cache_dir=tmp, loaders=make_loaders())
