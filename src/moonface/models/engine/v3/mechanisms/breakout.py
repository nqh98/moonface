from __future__ import annotations

from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.mechanisms.base import (
    BarContext,
    MechanismSignal,
    clip01,
)
from moonface.models.engine.v3.regime import DirState, Regime


class Breakout:
    name = "BREAKOUT"

    def __init__(self, cfg: EngineConfigV3 | None = None) -> None:
        self.cfg = cfg or EngineConfigV3()

    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal:
        d = self._direction(regime.dir_state)
        if d == 0 or ctx.atr <= 0.0:
            return MechanismSignal(0, 0.0, "no trend direction")
        if self.cfg.ext_scale <= 0.0 or self.cfg.roc_scale <= 0.0:
            return MechanismSignal(0, 0.0, "invalid scale")

        edge = ctx.donchian_high if d == 1 else ctx.donchian_low
        if d == 1 and ctx.close <= edge:
            return MechanismSignal(0, 0.0, "no upside break")
        if d == -1 and ctx.close >= edge:
            return MechanismSignal(0, 0.0, "no downside break")

        extension = clip01(
            abs(ctx.close - edge) / ctx.atr / self.cfg.ext_scale
        )
        momentum = clip01((d * ctx.roc) / self.cfg.roc_scale)
        location = self._close_location(ctx, d)
        quality = clip01((extension + momentum + location) / 3.0)
        return MechanismSignal(d, quality, f"breakout d={d} q={quality:.3f}")

    @staticmethod
    def _direction(dir_state: DirState) -> int:
        if dir_state == DirState.TRENDING_UP:
            return 1
        if dir_state == DirState.TRENDING_DOWN:
            return -1
        return 0

    @staticmethod
    def _close_location(ctx: BarContext, direction: int) -> float:
        span = ctx.high - ctx.low
        if span <= 0.0:
            return 0.0
        if direction == 1:
            return clip01((ctx.close - ctx.low) / span)
        return clip01((ctx.high - ctx.close) / span)
