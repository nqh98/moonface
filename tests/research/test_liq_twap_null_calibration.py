"""Gate-must-fail-on-null guard (vol_compression lesson). Cascade bars fire on a
random-walk price whose post-cascade direction is INDEPENDENT of the trigger, so
real trades exist yet no directional edge does. The screen MUST NOT pass, and the
direction-shuffle null MUST stay below the floor."""
import random
import unittest

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.liq_twap import runner
from moonface.research.liq_twap import screen as S
from moonface.research.liq_twap.signals import make_liq_cascade

SEED = 20260709


def _null_bundle() -> DataBundle:
    rng = random.Random(SEED)
    n = 900
    candles, oi = [], []
    price = 100.0
    for i in range(n):
        cascade = (i % 30 == 0) and i >= 200
        openp = price
        if cascade:
            price *= 0.94
            candles.append(Candle(i * 3_600_000, openp, openp * 1.001, price * 0.999, price, 8000.0))
            oi.append(800.0)
        else:
            price *= 1.0 + rng.uniform(-0.006, 0.006)
            candles.append(
                Candle(
                    i * 3_600_000,
                    openp,
                    max(openp, price) * 1.001,
                    min(openp, price) * 0.999,
                    price,
                    100.0,
                )
            )
            oi.append(1000.0 + rng.uniform(-1.0, 1.0))
    return DataBundle(candles=candles, feature=oi)


class _Cfg:
    def __enter__(self):
        self._old = (S.WINDOW, runner.WINDOW)
        S.WINDOW = runner.WINDOW = 40
        return self

    def __exit__(self, *a):
        S.WINDOW, runner.WINDOW = self._old


class TestNullCalibration(unittest.TestCase):
    def test_gate_rejects_directionless_cascades(self):
        bundle = _null_bundle()
        with _Cfg():
            gen = make_liq_cascade(bundle.feature)
            params = {"window": 40, "k": 1.5, "m": 1.5, "atr_period": 14}
            self.assertGreaterEqual(len(gen(bundle.candles, params)), 10, "guard is vacuous if no cascades fire")
            res = runner.run_screen(bundle)
        self.assertFalse(res["verdict"]["passed"], res["verdict"])
        self.assertTrue(
            res["verdict"]["conditions"]["null_fails"],
            f"shuffle null cleared the floor: {res['null_max_z']}",
        )


if __name__ == "__main__":
    unittest.main()
