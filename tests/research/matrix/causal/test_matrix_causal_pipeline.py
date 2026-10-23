import random
import unittest

from moonface.core.models import Candle
from moonface.research.matrix.causal.pipeline import (
    RegimeInference, WindowReport, run_pipeline)

import pytest

pytestmark = pytest.mark.slow


def _candles(n, seed=0):
    rng = random.Random(seed)
    out, px = [], 100.0
    for t in range(n):
        px = max(1.0, px * (1.0 + rng.gauss(0.0, 0.01)))
        out.append(Candle(t * 3600_000, px, px * 1.01, px * 0.99, px, 10.0))
    return out


_PARAMS = dict(train_bars=200, test_bars=20, step_bars=20, gap_bars=24, k=3, seed=11)


class PipelineTest(unittest.TestCase):
    def test_shapes_and_anonymity(self):
        candles = _candles(400)
        funding = [0.0001] * 400
        infs, reports = run_pipeline(candles, funding, **_PARAMS)
        self.assertTrue(infs and reports)
        self.assertIsInstance(infs[0], RegimeInference)
        self.assertIsInstance(reports[0], WindowReport)
        for r in infs:
            self.assertEqual(len(r.state_probs), 3)
            self.assertAlmostEqual(sum(r.state_probs), 1.0, places=9)
            self.assertIn(r.top_state, (0, 1, 2))

    def test_deterministic(self):
        candles = _candles(400)
        funding = [0.0001] * 400
        a, _ = run_pipeline(candles, funding, **_PARAMS)
        b, _ = run_pipeline(candles, funding, **_PARAMS)
        self.assertEqual([r.state_probs for r in a], [r.state_probs for r in b])

    def test_no_future_leakage_or_carryover(self):
        """A window's inferences must not change when data beyond its test_hi is
        added/mutated (proves no forward leakage and no cross-window state carry)."""
        candles = _candles(400)
        funding = [0.0001] * 400
        full, reports = run_pipeline(candles, funding, **_PARAMS)
        w0 = reports[0].window_index
        w0_infs = [r for r in full if r.window_index == w0]
        cut = max(r.bar_index for r in w0_infs) + 1
        truncated, _ = run_pipeline(candles[:cut], funding[:cut], **_PARAMS)
        t0 = [r for r in truncated if r.window_index == w0]
        self.assertEqual([r.state_probs for r in w0_infs],
                         [r.state_probs for r in t0])


if __name__ == "__main__":
    unittest.main()
