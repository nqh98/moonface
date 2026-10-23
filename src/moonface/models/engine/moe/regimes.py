from __future__ import annotations

from enum import Enum

from moonface.core.models import Candle
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.regime import (
    DirState,
    Regime,
    VolState,
    classify_regime,
)


class MoeRegime(str, Enum):
    TREND = "TREND"
    CHOP = "CHOP"
    STRESS = "STRESS"
    FLAT = "FLAT"


TRADEABLE: tuple[MoeRegime, ...] = (MoeRegime.TREND, MoeRegime.CHOP, MoeRegime.STRESS)


def coarsen(regime: Regime) -> MoeRegime:
    if regime.vol_state == VolState.EXTREME:
        return MoeRegime.FLAT
    if regime.dir_state in (DirState.TRENDING_UP, DirState.TRENDING_DOWN):
        return MoeRegime.TREND
    if regime.vol_state == VolState.HIGH:
        return MoeRegime.STRESS
    return MoeRegime.CHOP


def classify_moe_regime(window: list[Candle], cfg: EngineConfigV3) -> MoeRegime:
    return coarsen(classify_regime(window, cfg))
