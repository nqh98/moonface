from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.macro import MacroState
from moonface.models.engine.modules.base import TfViews
from moonface.models.engine.modules.revert_book import score, sweep_state

H = 3_600_000
D = 24 * H
W = 7 * D


def _cfg() -> EngineConfig:
    return EngineConfig(atr_period=14)


def _bar(i: int, close: float, *, low: float | None = None,
         high: float | None = None, open_: float | None = None) -> Candle:
    open_ = close if open_ is None else open_
    high = max(open_, close) + 0.5 if high is None else high
    low = min(open_, close) - 0.5 if low is None else low
    return Candle(i * H, open_, high, low, close, 1.0)


def _candles(closes: list[float], *, spread: float = 0.5) -> list[Candle]:
    out: list[Candle] = []
    prev = closes[0]
    for i, close in enumerate(closes):
        open_ = prev if i else close
        high = max(open_, close) + spread
        low = min(open_, close) - spread
        out.append(Candle(i * H, open_, high, low, close, 1.0))
        prev = close
    return out


def _flat(n: int, *, close: float = 100.0, low: float = 95.0,
          high: float = 105.0) -> list[Candle]:
    return [_bar(i, close, low=low, high=high) for i in range(n)]


def _views(h1: list[Candle]) -> TfViews:
    filler = _flat(80)
    return TfViews(h1=h1, h4=filler, d1=filler, w1=filler)


@dataclass(frozen=True)
class _Deriv:
    funding_pct: float | None = 50.0
    oi_change_z: float | None = 0.0
    oi_change_pct: float | None = 0.0


def _scores(h1: list[Candle], *, macro: MacroState | None = None,
            deriv: _Deriv | None = None) -> dict[str, object]:
    macro = MacroState("BULL", True, "normal") if macro is None else macro
    deriv = _Deriv() if deriv is None else deriv
    return {item.module: item for item in score(_views(h1), macro, deriv, _cfg())}


def test_sweep_long_scores_only_when_price_reclaims_the_broken_level():
    sweep = _flat(20) + [_bar(20, 96.0, open_=100.0, low=94.0, high=100.5)]
    breakdown = _flat(20) + [_bar(20, 94.0, open_=100.0, low=94.0, high=100.5)]

    got = _scores(sweep)["m1_sweep"]
    assert got.direction == 1
    assert got.points == 20
    assert got.data_ok is True

    broken = _scores(breakdown)["m1_sweep"]
    assert broken.direction == 0
    assert broken.points == 0
    assert broken.data_ok is True


def test_reclaim_only_starts_on_the_next_closed_bar_and_lasts_for_ttl():
    bars = _flat(20)
    bars.append(_bar(20, 96.0, open_=100.0, low=94.0, high=100.5))
    bars.append(_bar(21, 97.0, open_=96.0, low=95.5, high=98.0))
    bars.append(_bar(22, 98.0, open_=97.0, low=96.5, high=99.0))
    bars.append(_bar(23, 99.0, open_=98.0, low=97.5, high=100.0))
    bars.append(_bar(24, 100.0, open_=99.0, low=98.5, high=101.0))

    sweep_bar = _scores(bars[:21])
    confirm_bar = _scores(bars[:22])
    plus_one = _scores(bars[:23])
    plus_two = _scores(bars[:24])
    plus_three = _scores(bars[:25])

    assert sweep_bar["m2_reclaim"].points == 0
    assert sweep_bar["m2_reclaim"].direction == 0

    for state in (confirm_bar, plus_one, plus_two):
        assert state["m1_sweep"].direction == 1
        assert state["m1_sweep"].points == 20
        assert state["m2_reclaim"].direction == 1
        assert state["m2_reclaim"].points == 15

    assert plus_three["m1_sweep"].points == 0
    assert plus_three["m1_sweep"].direction == 0
    assert plus_three["m2_reclaim"].points == 0
    assert plus_three["m2_reclaim"].direction == 0


def test_sweep_short_mirror_scores_bearish_reclaim_of_prior_high():
    h1 = _flat(20) + [_bar(20, 104.0, open_=100.0, low=99.5, high=106.0)]
    got = _scores(h1)["m1_sweep"]
    assert got.direction == -1
    assert got.points == 20
    assert got.data_ok is True


def test_sweep_state_exposes_the_sweep_wick_extreme():
    h1 = _flat(20) + [_bar(20, 96.0, open_=100.0, low=94.0, high=100.5)]
    state = sweep_state(h1)
    assert state is not None
    assert state.direction == 1
    assert state.level == 95.0
    assert state.wick_extreme == 94.0


def test_divergence_scores_long_on_confirmed_price_lower_low_and_rsi_higher_low():
    closes = [
        120.0, 118.0, 116.0, 114.0, 112.0, 110.0, 108.0, 106.0, 104.0,
        102.0, 100.0, 98.0, 96.0, 94.0, 92.0, 94.0, 96.0, 98.0, 100.0,
        99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 91.0, 94.0, 96.0, 98.0,
    ]
    got = _scores(_candles(closes))["m3_divergence"]
    assert got.direction == 1
    assert got.points == 25
    assert got.data_ok is True


def test_divergence_requires_the_second_pivot_to_be_confirmed():
    closes = [
        120.0, 118.0, 116.0, 114.0, 112.0, 110.0, 108.0, 106.0, 104.0,
        102.0, 100.0, 98.0, 96.0, 94.0, 92.0, 94.0, 96.0, 98.0, 100.0,
        99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 91.0, 94.0,
    ]
    got = _scores(_candles(closes))["m3_divergence"]
    assert got.direction == 0
    assert got.points == 0
    assert got.data_ok is True


def test_divergence_rejects_pivots_more_than_forty_bars_apart():
    closes = [
        120.0, 118.0, 116.0, 114.0, 112.0, 110.0, 108.0, 106.0, 104.0,
        102.0, 100.0, 98.0, 96.0, 94.0, 92.0, 94.0, 96.0, 98.0, 100.0,
        102.0, 104.0, 106.0, 108.0, 110.0, 111.0, 110.0, 109.0, 108.0,
        107.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0, 99.0,
        98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 92.0, 91.0, 90.0, 89.0, 88.0,
        87.0, 86.0, 85.0, 84.0, 83.0, 82.0, 81.0, 80.0, 92.0, 94.0, 96.0,
    ]
    got = _scores(_candles(closes))["m3_divergence"]
    assert got.direction == 0
    assert got.points == 0
    assert got.data_ok is True


def test_divergence_scores_short_on_confirmed_price_higher_high_and_rsi_lower_high():
    closes = [
        80.0, 82.0, 84.0, 86.0, 88.0, 90.0, 92.0, 94.0, 96.0, 98.0, 100.0,
        102.0, 104.0, 106.0, 108.0, 106.0, 104.0, 102.0, 100.0, 101.0,
        102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 109.0, 107.0, 105.0, 103.0,
    ]
    got = _scores(_candles(closes))["m3_divergence"]
    assert got.direction == -1
    assert got.points == 25
    assert got.data_ok is True


def test_stretch_requires_two_atr_below_the_fifty_bar_mean():
    stretched = _candles([100.0] * 49 + [97.45])
    mild = _candles([100.0] * 49 + [97.75])

    strong = _scores(stretched)["m6_stretch"]
    assert strong.direction == 1
    assert strong.points == 15
    assert strong.data_ok is True

    quiet = _scores(mild)["m6_stretch"]
    assert quiet.direction == 0
    assert quiet.points == 0
    assert quiet.data_ok is True
