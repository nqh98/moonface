"""v3 entry simulator reuses the frozen v2.2 ATR bracket for both directions."""

from moonface.models.engine.config import EngineConfig
from moonface.models.engine.v3.evaluate import simulate_bracket_v3

from tests.helpers_v3 import downtrend, uptrend

CFG22 = EngineConfig()


def test_long_bracket_exits_with_positive_r_in_uptrend():
    candles = uptrend(200, step=1.0)
    tr = simulate_bracket_v3(
        candles, 60, 1, 0.7, "BREAKOUT", "TRENDING_UP/NORMAL", CFG22
    )
    assert tr is not None
    assert tr.direction == 1
    assert tr.exit_index > tr.entry_index
    assert tr.net_r > 0
    assert tr.exit_reason != ""


def test_short_bracket_exits_with_positive_r_in_downtrend():
    candles = downtrend(200, step=1.0)
    tr = simulate_bracket_v3(
        candles, 60, -1, 0.7, "BREAKOUT", "TRENDING_DOWN/NORMAL", CFG22
    )
    assert tr is not None and tr.direction == -1 and tr.net_r > 0


def test_returns_none_when_data_ends_before_exit():
    candles = uptrend(70, step=0.01, wick=0.0)
    tr = simulate_bracket_v3(
        candles, 68, 1, 0.5, "PULLBACK", "TRENDING_UP/QUIET", CFG22
    )
    assert tr is None


def test_metadata_is_carried_through():
    candles = uptrend(200, step=1.0)
    tr = simulate_bracket_v3(
        candles, 60, 1, 0.42, "REVERSION", "RANGING/NORMAL", CFG22
    )
    assert tr.mechanism == "REVERSION" and tr.cell == "RANGING/NORMAL"
    assert tr.quality == 0.42
    assert tr.risk_fraction == CFG22.base_fraction
