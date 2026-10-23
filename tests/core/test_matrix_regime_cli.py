import random
import unittest

from moonface.core.models import Candle
from tools.matrix.matrix_regime import build_regime_report


def _candles(n, seed=0):
    rng = random.Random(seed)
    out, px = [], 100.0
    for t in range(n):
        px = max(1.0, px * (1.0 + rng.gauss(0.0, 0.01)))
        out.append(Candle(t * 3600_000, px, px * 1.01, px * 0.99, px, 10.0))
    return out


class RegimeReportTest(unittest.TestCase):
    def test_report_is_readonly_diagnostic(self):
        candles = _candles(400)
        funding = [0.0001] * 400
        rep = build_regime_report(candles, funding, train_bars=200, test_bars=20,
                                  step_bars=20, gap_bars=24, k=3, seed=11)
        self.assertEqual(rep["k_states"], 3)
        self.assertGreater(rep["n_windows"], 0)
        self.assertGreater(rep["n_inferences"], 0)
        self.assertEqual(len(rep["state_labels"]), 3)
        self.assertEqual(rep["state_labels"], ["State_0", "State_1", "State_2"])
        self.assertNotIn("verdict", rep)


if __name__ == "__main__":
    unittest.main()
