import random
import unittest

from moonface.core.models import Candle
from tools.matrix.matrix_baselines import build_baseline_report


def _osc(n, seed=0):
    rng = random.Random(seed)
    out, px = [], 100.0
    for t in range(n):
        phase = (t // 30) % 2
        px = max(1.0, px + (0.6 if phase == 0 else -0.6) + rng.uniform(-0.1, 0.1))
        out.append(Candle(t * 14_400_000, px, px + 0.5, px - 0.5, px, 10.0))
    return out


class BaselineReportTest(unittest.TestCase):
    def test_report_is_readonly_floor(self):
        rep = build_baseline_report(
            _osc(400),
            n=20,
            atr_period=14,
            freeze_pctl=0.80,
            freeze_lookback=50,
            taker_fee=0.0004,
            slippage_bps=1.0,
        )
        self.assertEqual(set(rep["baselines"]), {"baseline_1", "baseline_2"})
        for name in ("baseline_1", "baseline_2"):
            self.assertEqual(set(rep["baselines"][name]), {"cost_1x", "cost_2x"})
            cell = rep["baselines"][name]["cost_1x"]
            self.assertIn("full", cell)
            self.assertEqual(set(cell["segments"]), {"train", "sealed"})
        self.assertNotIn("verdict", rep)


if __name__ == "__main__":
    unittest.main()
