"""Event-proxy generator tests: a constructed cascade fires with the correct
continuation side; the volume/OI/magnitude gates each veto; the control
(require_oi_drop=False) selects the vol-matched non-deleveraging bars instead."""
import unittest

from moonface.core.models import Candle
from moonface.research.liq_twap.signals import make_liq_cascade

W = 20


def _flat_bar(i, price, vol):
    return Candle(i * 3_600_000, price, price * 1.001, price * 0.999, price, vol)


def _build(down_event_at, oi_drop=True):
    """Flat baseline with one big DOWN cascade bar at `down_event_at`."""
    n = 60
    candles, oi = [], []
    price = 100.0
    for i in range(n):
        if i == down_event_at:
            candles.append(Candle(i * 3_600_000, 100.0, 100.2, 95.5, 96.0, 5000.0))
            oi.append(900.0 if oi_drop else 1005.0)
        else:
            candles.append(_flat_bar(i, price, 100.0 + (i % 3)))
            oi.append(1000.0 + (i % 2))
    return candles, oi


class TestLiqCascade(unittest.TestCase):
    def _params(self, **kw):
        base = {"window": W, "k": 1.5, "m": 1.5, "atr_period": 14}
        base.update(kw)
        return base

    def test_down_cascade_fires_short(self):
        candles, oi = _build(40, oi_drop=True)
        gen = make_liq_cascade(oi)
        events = gen(candles, self._params())
        self.assertIn((40, "SHORT"), events)

    def test_up_cascade_fires_long(self):
        n = 60
        candles, oi = [], []
        for i in range(n):
            if i == 40:
                candles.append(Candle(i * 3_600_000, 100.0, 104.5, 99.8, 104.0, 5000.0))
                oi.append(900.0)
            else:
                candles.append(Candle(i * 3_600_000, 100.0, 100.1, 99.9, 100.0, 100.0))
                oi.append(1000.0 + (i % 2))
        gen = make_liq_cascade(oi)
        self.assertIn((40, "LONG"), gen(candles, self._params()))

    def test_no_oi_drop_vetoes_treatment(self):
        candles, oi = _build(40, oi_drop=False)
        gen = make_liq_cascade(oi)
        events = gen(candles, self._params(require_oi_drop=True))
        self.assertNotIn((40, "SHORT"), events)

    def test_control_selects_non_oi_drop(self):
        candles, oi = _build(40, oi_drop=False)
        gen = make_liq_cascade(oi)
        events = gen(candles, self._params(require_oi_drop=False))
        self.assertIn((40, "SHORT"), events)

    def test_small_body_vetoes(self):
        candles, oi = _build(40, oi_drop=True)
        candles[40] = Candle(40 * 3_600_000, 100.0, 100.05, 99.95, 100.0, 5000.0)
        gen = make_liq_cascade(oi)
        self.assertEqual(gen(candles, self._params()), [])


if __name__ == "__main__":
    unittest.main()
