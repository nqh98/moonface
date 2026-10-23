from __future__ import annotations

from moonface.models.engine.v3.mechanisms.base import Mechanism
from moonface.models.engine.v3.mechanisms.breakout import Breakout
from moonface.models.engine.v3.mechanisms.pullback import Pullback
from moonface.models.engine.v3.mechanisms.reversion import Reversion
from moonface.models.engine.v3.regime import DirState, Regime, VolState

MECHANISMS: dict[str, Mechanism] = {
    m.name: m for m in (Breakout(), Pullback(), Reversion())
}

REGIME_MECHANISM: dict[tuple[DirState, VolState], str | None] = {
    (DirState.TRENDING_UP, VolState.QUIET): "PULLBACK",
    (DirState.TRENDING_UP, VolState.NORMAL): "BREAKOUT",
    (DirState.TRENDING_UP, VolState.HIGH): "BREAKOUT",
    (DirState.RANGING, VolState.QUIET): "REVERSION",
    (DirState.RANGING, VolState.NORMAL): "REVERSION",
    (DirState.RANGING, VolState.HIGH): None,
    (DirState.TRENDING_DOWN, VolState.QUIET): "PULLBACK",
    (DirState.TRENDING_DOWN, VolState.NORMAL): "BREAKOUT",
    (DirState.TRENDING_DOWN, VolState.HIGH): "BREAKOUT",
}


def select_mechanism(regime: Regime) -> str | None:
    return REGIME_MECHANISM.get((regime.dir_state, regime.vol_state))
