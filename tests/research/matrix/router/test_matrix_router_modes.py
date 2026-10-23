import random
import unittest

from moonface.core.models import Candle
from moonface.research.matrix.router.modes import build_bar_modes
from moonface.research.matrix.router.semantics import (
    MODE_FREEZE,
    MODE_QUARANTINE,
    MODE_TREND,
)

PARAMS = dict(n=20, train_bars=150, test_bars=50, step_bars=50, gap_bars=10, k=2)


def _osc(n, seed=0):
    rng = random.Random(seed)
    out, px = [], 100.0
    for t in range(n):
        phase = (t // 30) % 2
        px = max(1.0, px + (0.6 if phase == 0 else -0.6) + rng.uniform(-0.1, 0.1))
        out.append(Candle(t * 14_400_000, px, px + 0.5, px - 0.5, px, 10.0))
    return out


class BuildBarModesTest(unittest.TestCase):
    def test_labels_are_test_block_bars_with_valid_modes(self):
        candles = _osc(500)
        modes = build_bar_modes(candles, [None] * 500, seed=11, **PARAMS)
        self.assertTrue(modes)
        self.assertTrue(
            all(m in (MODE_TREND, MODE_QUARANTINE, MODE_FREEZE) for m in modes.values())
        )
        self.assertTrue(any(260 <= i < 310 for i in modes))

    def test_mapping_is_train_only_causal(self):
        candles = _osc(500)
        base = build_bar_modes(candles, [None] * 500, seed=11, **PARAMS)
        flat = [
            Candle(c.timestamp_ms, 5000.0, 5001.0, 4999.0, 5000.0, 10.0)
            for c in candles[310:]
        ]
        after = build_bar_modes(candles[:310] + flat, [None] * 500, seed=11, **PARAMS)
        for i in range(260, 310):
            self.assertEqual(base.get(i), after.get(i))

    def test_low_entropy_threshold_forces_all_freeze(self):
        candles = _osc(500)
        modes = build_bar_modes(
            candles,
            [None] * 500,
            seed=11,
            entropy_freeze=-1.0,
            **PARAMS,
        )
        self.assertTrue(modes)
        self.assertTrue(all(m == MODE_FREEZE for m in modes.values()))


if __name__ == "__main__":
    unittest.main()
