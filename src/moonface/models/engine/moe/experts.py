from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from moonface.core.models import Candle
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.matrix import MECHANISMS
from moonface.models.engine.v3.mechanisms.base import build_context, clip01
from moonface.models.engine.v3.regime import classify_regime

FUNDING_CAP = 0.01
OI_LOOKBACK = 24
ORTHO_CONSTANTS = {"FUNDING_CAP": FUNDING_CAP, "OI_LOOKBACK": OI_LOOKBACK}


@dataclass(frozen=True)
class RawSignal:
    direction: int
    magnitude: float


def raw_value(sig: RawSignal) -> float:
    return sig.direction * sig.magnitude


def _sign(x: float) -> int:
    return 1 if x > 0 else -1 if x < 0 else 0


@dataclass(frozen=True)
class ExpertContext:
    window: list[Candle]
    index: int
    cfg: EngineConfigV3
    funding: list[float | None] | None = None
    oi: list[float | None] | None = None


class Expert(Protocol):
    name: str

    def signal(self, ctx: ExpertContext) -> RawSignal:
        ...


@dataclass(frozen=True)
class _MechanismExpert:
    name: str

    def signal(self, ctx: ExpertContext) -> RawSignal:
        regime = classify_regime(ctx.window[: ctx.index + 1], ctx.cfg)
        bar_ctx = build_context(ctx.window, ctx.index, ctx.cfg)
        sig = MECHANISMS[self.name].evaluate(bar_ctx, regime)
        return RawSignal(direction=sig.direction, magnitude=clip01(sig.quality))


@dataclass(frozen=True)
class _FundingExpert:
    name: str = "FUNDING"

    def signal(self, ctx: ExpertContext) -> RawSignal:
        if ctx.funding is None:
            return RawSignal(0, 0.0)
        funding = ctx.funding[ctx.index]
        if funding is None or funding == 0.0:
            return RawSignal(0, 0.0)
        return RawSignal(direction=-_sign(funding), magnitude=clip01(abs(funding) / FUNDING_CAP))


@dataclass(frozen=True)
class _OiExpert:
    name: str = "OI"

    def signal(self, ctx: ExpertContext) -> RawSignal:
        if ctx.oi is None or ctx.index < OI_LOOKBACK:
            return RawSignal(0, 0.0)
        oi_now = ctx.oi[ctx.index]
        oi_prev = ctx.oi[ctx.index - OI_LOOKBACK]
        if oi_now is None or oi_prev is None or oi_prev <= 0.0:
            return RawSignal(0, 0.0)
        d_oi = oi_now - oi_prev
        if d_oi <= 0.0:
            return RawSignal(0, 0.0)
        d_px = ctx.window[ctx.index].close - ctx.window[ctx.index - OI_LOOKBACK].close
        return RawSignal(direction=_sign(d_px), magnitude=clip01(d_oi / oi_prev))


def mechanism_experts() -> list[Expert]:
    return [_MechanismExpert(name) for name in ("BREAKOUT", "PULLBACK", "REVERSION")]


def orthogonal_experts() -> list[Expert]:
    return [_FundingExpert(), _OiExpert()]


def default_experts() -> list[Expert]:
    return mechanism_experts() + orthogonal_experts()
