# tests/test_forced_error_null_calibration.py
"""Null-calibration guard (the vol_compression lesson): a valid surrogate-null
gate MUST reject a null OI feature. This bundle has a random-walk price with
GUARANTEED periodic pierce-and-fail events and an OI feature that spikes at those
events but is INDEPENDENT of forward returns. So the signal fires real trades,
yet OI carries no genuine edge -> the gate must NOT pass. If this test fails, the
gate is a tautology and the lane is INVALID (a research STOP condition), not a
flaky test."""
import random
import unittest

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.kernel.divergence_null import surrogate_null
from moonface.research.forced_error import forced_error_specs
from moonface.research.ladder import SCREEN_FRACTION, r_stream

EVENT_EVERY = 9
SEED = 20260708


def _build_null_bundle() -> DataBundle:
    rng = random.Random(SEED)
    n = 1500
    closes, highs, lows, vols, oi = [], [], [], [], []
    price = 100.0
    for i in range(n):
        price *= (1.0 + rng.uniform(-0.008, 0.008))
        event = (i % EVENT_EVERY == 0) and i >= 200
        if event:
            hi = price * 1.06                                  # pierces prior 24-bar high
            cl = price * (1.0 + rng.uniform(-0.010, -0.002))   # closes back inside (fail)
            lo = min(cl, price) * 0.995
            v = 6000.0                                         # volume spike
            oi.append(130.0)                                   # OI log-change spike
        else:
            hi = price * (1.0 + abs(rng.uniform(0, 0.004)))
            cl = price
            lo = price * (1.0 - abs(rng.uniform(0, 0.004)))
            v = rng.uniform(80, 140)
            oi.append(100.0 + rng.uniform(-1.0, 1.0))
        closes.append(cl)
        highs.append(hi)
        lows.append(lo)
        vols.append(v)
    candles = [Candle(i * 3_600_000, closes[i], highs[i], lows[i], closes[i], vols[i])
               for i in range(n)]
    return DataBundle(candles=candles, feature=oi, funding=[-0.001] * n)


class TestNullCalibration(unittest.TestCase):
    def test_gate_rejects_null_oi_with_real_trades(self):
        bundle = _build_null_bundle()
        spec = next(s for s in forced_error_specs()
                    if s.entry["family"] == "failed_breakout_harvest")
        split = int(len(bundle.candles) * SCREEN_FRACTION)
        holdout = [1 for i, _, _ in r_stream(spec, bundle) if i >= split]
        # (1) NON-VACUOUS: the signal genuinely fires real holdout trades.
        self.assertGreaterEqual(len(holdout), 10,
                                "guard is vacuous if the signal never fires")
        res = surrogate_null(spec, bundle, draws=100)
        # (2) the gate REJECTS this null (not hardwired to pass).
        self.assertFalse(res["passed"], f"gate must reject null OI, got {res}")
        # (3) SUBSTANTIVE reason: real MAR is NOT in the surrogate upper tail.
        self.assertGreater(res["p_value"], 0.5, f"real MAR not exceptional? {res}")


if __name__ == "__main__":
    unittest.main()
