from __future__ import annotations

from moonface.research.exogenous.conditioning import state_positions
from moonface.research.exogenous.fred_data import MacroPoint
from moonface.research.exogenous.grid import StateDef
from moonface.research.exogenous.exo_features import DAY_MS


def test_positions_clamp_to_sign_of_sum():
    series = {"X": [MacroPoint(0, 5.0), MacroPoint(DAY_MS, 5.0), MacroPoint(2 * DAY_MS, 5.0)]}
    long = StateDef("a", "X", 0, 0, ">", 1.0, +1)   # always active -> +1
    short = StateDef("b", "X", 0, 0, ">", 1.0, -1)  # always active -> -1
    # two opposing states cancel -> 0
    assert state_positions([2 * DAY_MS], series, states=(long, short)) == [0]
    # single long -> +1
    assert state_positions([2 * DAY_MS], series, states=(long,)) == [1]


def test_unresolvable_feature_is_flat():
    series = {"X": [MacroPoint(10 * DAY_MS, 5.0)]}  # nothing published by decision
    s = StateDef("a", "X", 0, 0, ">", 1.0, +1)
    assert state_positions([0], series, states=(s,)) == [0]
