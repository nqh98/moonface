from __future__ import annotations

from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.mechanisms.base import (
    BarContext,
    MechanismSignal,
    clip01,
)
from moonface.models.engine.v3.regime import Regime


class Reversion:
    name = "REVERSION"

    def __init__(self, cfg: EngineConfigV3 | None = None) -> None:
        self.cfg = cfg or EngineConfigV3()

    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal:
        del regime  # two-sided: direction comes from the band hit, not the regime
        if ctx.atr <= 0.0:
            return MechanismSignal(0, 0.0, "no atr")
        if self.cfg.stretch_scale <= 0.0:
            return MechanismSignal(0, 0.0, "invalid scale")

        upper_reject = ctx.high >= ctx.band_up and ctx.close < ctx.band_up
        lower_reject = ctx.low <= ctx.band_lo and ctx.close > ctx.band_lo
        if upper_reject:
            d, extreme, rsi_stretch = -1, ctx.high, (ctx.rsi - 50.0) / 50.0
        elif lower_reject:
            d, extreme, rsi_stretch = 1, ctx.low, (50.0 - ctx.rsi) / 50.0
        else:
            return MechanismSignal(0, 0.0, "inside bands or not rejected")

        stretch = clip01(abs(extreme - ctx.band_mid) / ctx.atr / self.cfg.stretch_scale)
        rejection = clip01(abs(extreme - ctx.close) / ctx.atr)
        rsi_q = clip01(rsi_stretch)
        quality = clip01((stretch + rejection + rsi_q) / 3.0)
        return MechanismSignal(d, quality, f"reversion d={d} q={quality:.3f}")
