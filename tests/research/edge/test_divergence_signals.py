from dataclasses import dataclass

from moonface.research.edge.divergence_signals import (
    make_price_oi_divergence, price_extension_short)


@dataclass
class C:
    close: float


def _rising(n: int, step: float = 1.0) -> list[C]:
    return [C(100.0 + step * i) for i in range(n)]


def test_treatment_fires_short_when_price_up_and_oi_down():
    n = 12
    candles = _rising(n)
    oi = [1000.0, 1001.0, 1000.5, 1001.5, 1000.0, 1001.0, 1000.5, 1001.5,
          900.0, 1001.0, 1000.5, 1001.5]
    gen = make_price_oi_divergence(oi)
    entries = gen(candles, {"window": 4, "lookback": 1, "k": 1.0})
    assert (8, "SHORT") in entries
    assert all(side == "SHORT" for _, side in entries)


def test_treatment_silent_when_oi_confirms():
    n = 12
    candles = _rising(n)
    oi = [1000.0 + 10.0 * i for i in range(n)]
    gen = make_price_oi_divergence(oi)
    entries = gen(candles, {"window": 4, "lookback": 1, "k": 1.0})
    assert entries == []


def test_control_ignores_oi_and_shorts_on_price_extension():
    n = 16
    candles = [C(100.0)] * 4 + [C(100.0 + 5.0 * i) for i in range(n - 4)]
    entries = price_extension_short(candles,
                                    {"window": 4, "lookback": 1, "k": 0.5})
    assert entries, "price-extension control should emit at least one SHORT"
    assert all(side == "SHORT" for _, side in entries)
