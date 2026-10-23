"""Runner tests on synthetic bundles: a bundle with a genuine post-cascade
continuation drift PASSes; a bundle where cascades are followed by ZERO-mean
noise FAILs (drift absent). Uses small W so the fixtures stay compact."""
import random
import unittest

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.liq_twap import runner
from moonface.research.liq_twap import screen as S


def _drift_bundle(with_drift: bool, seed: int = 1) -> DataBundle:
    rng = random.Random(seed)
    n = 900
    candles, oi = [], []
    price = 100.0
    post = 0
    for i in range(n):
        cascade = (i % 30 == 0) and i >= 200
        if cascade:
            openp = price
            price *= 0.94
            candles.append(Candle(i * 3_600_000, openp, openp * 1.001, price * 0.999, price, 8000.0))
            oi.append(800.0)
            post = 4 if with_drift else 0
        else:
            openp = price
            if post > 0:
                price *= 0.985
                post -= 1
            else:
                price *= 1.0 + rng.uniform(-0.004, 0.004)
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
        S.WINDOW = 40
        runner.WINDOW = 40
        return self

    def __exit__(self, *a):
        S.WINDOW, runner.WINDOW = self._old


class TestRunner(unittest.TestCase):
    def test_drift_bundle_passes(self):
        with _Cfg():
            res = runner.run_screen(_drift_bundle(with_drift=True))
        self.assertTrue(res["verdict"]["passed"], res["verdict"])

    def test_no_drift_bundle_fails(self):
        with _Cfg():
            res = runner.run_screen(_drift_bundle(with_drift=False))
        self.assertFalse(res["verdict"]["passed"])

    def test_render_verdict_has_status(self):
        with _Cfg():
            res = runner.run_screen(_drift_bundle(with_drift=True))
        md = runner.render_verdict(res)
        self.assertIn("Status", md)


if __name__ == "__main__":
    unittest.main()
