from moonface.core.models import Candle
from moonface.models.engine.macro import (
    MACRO_CONFIRM_CLOSES,
    MACRO_MA_WEEKS,
    MacroState,
    classify_macro,
)

W = 7 * 24 * 3_600_000


def _weekly(closes):
    return [Candle(i * W, c, c, c, c, 1.0) for i, c in enumerate(closes)]


def test_insufficient_history_is_neutral_and_unconfirmed():
    weekly = _weekly([float(x) for x in range(30)])
    state = classify_macro(weekly, "normal", None)
    assert state == MacroState(bias="NEUTRAL", confirmed=False, vol_state="normal")
    assert state.effective() == "NEUTRAL"


def test_bull_after_long_series_above_ma_is_confirmed():
    weekly = _weekly([float(x) for x in range(1, 61)])
    state = classify_macro(weekly, "high", None)
    assert state.bias == "BULL"
    assert state.confirmed is True
    assert state.vol_state == "high"
    assert state.effective() == "BULL"


def test_minimum_31_bar_bull_series_confirms():
    weekly = _weekly([float(x) for x in range(1, 32)])
    state = classify_macro(weekly, "normal", None)
    assert state.bias == "BULL"
    assert state.confirmed is True
    assert state.effective() == "BULL"


def test_one_close_below_flips_bias_but_not_effective():
    weekly = _weekly([float(x) for x in range(1, 60)] + [0.5])
    state = classify_macro(weekly, "normal", None)
    assert state.bias == "BEAR"
    assert state.confirmed is False
    assert state.effective() == "NEUTRAL"


def test_two_closes_below_confirm_bear():
    weekly = _weekly([float(x) for x in range(1, 59)] + [0.5, 0.4])
    state = classify_macro(weekly, "normal", None)
    assert state.bias == "BEAR"
    assert state.confirmed is True
    assert state.effective() == "BEAR"


def test_oscillating_across_ma_never_confirms():
    weekly = _weekly([99.0 if i % 2 == 0 else 101.0 for i in range(61)])
    state = classify_macro(weekly, "extreme", None)
    assert state.confirmed is False
    assert state.effective() == "NEUTRAL"
    assert state.vol_state == "extreme"


def test_classify_macro_is_pure_on_input_list():
    weekly = _weekly([float(x) for x in range(1, 61)])
    before = list(weekly)
    state = classify_macro(weekly, "normal", None)
    weekly.append(Candle(61 * W, 999.0, 999.0, 999.0, 999.0, 1.0))
    assert weekly[:-1] == before
    assert state.effective() == "BULL"
    assert len(before) == 60


def test_macro_constants_frozen():
    assert MACRO_MA_WEEKS == 30
    assert MACRO_CONFIRM_CLOSES == 2
