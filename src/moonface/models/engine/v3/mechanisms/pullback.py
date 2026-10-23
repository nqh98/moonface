from __future__ import annotations

from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.mechanisms.base import (
    BarContext,
    MechanismSignal,
    clip01,
)
from moonface.models.engine.v3.regime import DirState, Regime


class Pullback:
    name = "PULLBACK"

    def __init__(self, cfg: EngineConfigV3 | None = None) -> None:
        self.cfg = cfg or EngineConfigV3()

    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal:
        d = self._direction(regime.dir_state)
        if d == 0 or ctx.ema_fast <= 0.0 or ctx.atr <= 0.0:
            return MechanismSignal(0, 0.0, "no trend direction")

        if self.cfg.pullback_tol <= 0.0 or self.cfg.adx_scale <= 0.0:
            return MechanismSignal(0, 0.0, "invalid scale")

        tol = self.cfg.pullback_tol
        if d == 1:
            tagged = ctx.low <= ctx.ema_fast * (1.0 + tol)
            reclaimed = ctx.close > ctx.ema_fast and ctx.close > ctx.open
        else:
            tagged = ctx.high >= ctx.ema_fast * (1.0 - tol)
            reclaimed = ctx.close < ctx.ema_fast and ctx.close < ctx.open
        if not (tagged and reclaimed):
            return MechanismSignal(0, 0.0, "no ema tag+reclaim")

        strength = clip01(ctx.adx / self.cfg.adx_scale)
        depth_atr = abs(ctx.close - ctx.ema_fast) / ctx.atr
        shallowness = clip01(1.0 - depth_atr)
        location = self._close_location(ctx, d)
        quality = clip01((strength + shallowness + location) / 3.0)
        return MechanismSignal(d, quality, f"pullback d={d} q={quality:.3f}")

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
