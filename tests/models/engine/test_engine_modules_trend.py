from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.macro import MacroState
from moonface.models.engine.modules.base import TfViews
from moonface.models.engine.modules.trend_book import score

H = 3_600_000
D = 24 * H
W = 7 * D


def _cfg() -> EngineConfig:
    return EngineConfig(atr_period=14)


def _candles(closes: list[float], step_ms: int, spread: float = 2.0) -> list[Candle]:
    out: list[Candle] = []
    prev = closes[0]
    for i, close in enumerate(closes):
        open_ = prev if i else close
        high = max(open_, close) + spread
        low = min(open_, close) - spread
        out.append(Candle(i * step_ms, open_, high, low, close, 1.0))
        prev = close
    return out


def _rising(n: int, step_ms: int, start: float = 100.0,
            step: float = 1.0) -> list[Candle]:
    return _candles([start + i * step for i in range(n)], step_ms)


def _flat(n: int, step_ms: int, price: float = 100.0) -> list[Candle]:
    return _candles([price] * n, step_ms, spread=0.5)


def _views(*, h1: list[Candle] | None = None, h4: list[Candle] | None = None,
           d1: list[Candle] | None = None, w1: list[Candle] | None = None) -> TfViews:
    return TfViews(
        h1=_rising(80, H) if h1 is None else h1,
        h4=_rising(80, 4 * H) if h4 is None else h4,
        d1=_rising(80, D) if d1 is None else d1,
        w1=_rising(80, W) if w1 is None else w1,
    )


_DEFAULT = object()


@dataclass(frozen=True)
class _Deriv:
    funding_pct: float | None


def _scores(views: TfViews, macro: MacroState | None = None,
            deriv: _Deriv | None | object = _DEFAULT) -> dict[str, object]:
    macro = MacroState("BULL", True, "normal") if macro is None else macro
    if deriv is _DEFAULT:
        deriv = _Deriv(funding_pct=0.0)
    return {item.module: item for item in score(views, macro, deriv, _cfg())}


def test_m2_breakout_scores_long_short_or_flat():
    cases = (
        ("long", _candles([100.0] * 40 + [102.0], 4 * H, spread=0.5), 1, 20),
        ("short", _candles([100.0] * 40 + [98.0], 4 * H, spread=0.5), -1, 20),
        ("inside", _candles([100.0] * 40 + [100.0], 4 * H, spread=0.5), 0, 0),
    )
    for _name, h4, direction, points in cases:
        got = _scores(_views(h4=h4))["m2_breakout"]
        assert got.direction == direction
        assert got.points == points
        assert got.data_ok is True


def test_m2_ma_align_requires_close_and_sma20_on_same_side_of_sma50():
    cases = (
        ("long", [100.0 + i for i in range(60)], 1, 10),
        ("short", [160.0 - i for i in range(60)], -1, 10),
        ("close_only", [100.0] * 30 + [80.0] * 29 + [120.0], 0, 0),
        ("ma_only", [80.0] * 30 + [120.0] * 29 + [90.0], 0, 0),
    )
    for _name, closes, direction, points in cases:
        got = _scores(_views(h4=_candles(closes, 4 * H)))["m2_ma_align"]
        assert got.direction == direction
        assert got.points == points
        assert got.data_ok is True


def test_m3_roc_uses_strong_and_weak_tiers():
    cases = (
        ("strong_long", 105.0, 1, 20),
        ("weak_long", 102.0, 1, 10),
        ("strong_short", 95.0, -1, 20),
        ("weak_short", 98.0, -1, 10),
        ("below_floor", 101.0, 0, 0),
    )
    for _name, last_close, direction, points in cases:
        closes = [100.0] * 67 + [last_close]
        got = _scores(_views(h4=_candles(closes, 4 * H)))["m3_roc"]
        assert got.direction == direction
        assert got.points == points
        assert got.data_ok is True


def test_m4_pullback_requires_trend_and_atr_band():
    trend_pullback = _candles([100.0 + i for i in range(59)] + [150.0], H)
    trend_far = _candles([100.0 + i for i in range(60)], H)
    broken_trend = _candles([160.0 - i for i in range(59)] + [130.0], H)

    cases = (
        ("fires_long", trend_pullback, 1, 15),
        ("too_far", trend_far, 0, 0),
        ("trend_broken", broken_trend, 0, 0),
    )
    for _name, h1, direction, points in cases:
        got = _scores(_views(h1=h1))["m4_pullback"]
        assert got.direction == direction
        assert got.points == points
        assert got.data_ok is True


def test_m1_macro_scores_confirmed_1w_bias_only():
    # M1 is pure 1W macro bias (spec §2): a confirmed weekly bias scores +20 in
    # its direction regardless of 4h structure. Opposition is the gate's job, so
    # a confirmed BULL still votes +20 even when the 4h view is falling.
    rising_h4 = _views(h4=_candles([100.0 + i for i in range(60)], 4 * H))
    falling_h4 = _views(h4=_candles([160.0 - i for i in range(60)], 4 * H))
    cases = (
        ("bull", rising_h4, MacroState("BULL", True, "normal"), 1, 20),
        ("bear", falling_h4, MacroState("BEAR", True, "normal"), -1, 20),
        ("bull_vs_falling_4h", falling_h4, MacroState("BULL", True, "normal"), 1, 20),
        ("neutral", rising_h4, MacroState("NEUTRAL", True, "normal"), 0, 0),
        ("unconfirmed", rising_h4, MacroState("BULL", False, "normal"), 0, 0),
    )
    for _name, views, macro, direction, points in cases:
        got = _scores(views, macro=macro)["m1_macro"]
        assert got.direction == direction
        assert got.points == points
        assert got.data_ok is True


def test_m5_funding_marks_missing_derivatives_as_not_ok():
    got = _scores(_views(), deriv=None)["m5_funding"]
    assert got.direction == 0
    assert got.points == 0
    assert got.data_ok is False


def test_all_scores_obey_points_quantum_and_direction_contract():
    scores = _scores(_views(), macro=MacroState("BULL", True, "normal"),
                     deriv=_Deriv(funding_pct=0.0002))
    assert set(scores) == {"m1_macro", "m2_breakout", "m2_ma_align", "m3_roc",
                           "m4_pullback", "m5_funding"}
    for item in scores.values():
        assert item.points >= 0
        assert item.points % 5 == 0
        assert item.direction in (-1, 0, 1)


def test_insufficient_history_returns_data_not_ok_without_raising():
    scores = _scores(
        _views(h1=_flat(5, H), h4=_flat(5, 4 * H), d1=_flat(5, D), w1=_flat(5, W)),
        macro=MacroState("BULL", True, "normal"),
        deriv=_Deriv(funding_pct=0.0),
    )
    for name in ("m2_breakout", "m2_ma_align", "m3_roc", "m4_pullback"):
        item = scores[name]
        assert item.points == 0
        assert item.direction == 0
        assert item.data_ok is False
    # m1_macro depends only on the (confirmed) macro state, not candle history
    assert scores["m1_macro"].data_ok is True
    assert scores["m5_funding"].data_ok is True
