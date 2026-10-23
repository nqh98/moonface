"""v3 orchestrator: classify -> select one mechanism -> trigger -> size.

The daemon entrypoint. Exactly one mechanism is consulted per bar and nothing
on the path sums — the spec-2 core invariant is enforced structurally here and
asserted in tests/test_v3_decide.py.
"""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.matrix import MECHANISMS, select_mechanism
from moonface.models.engine.v3.mechanisms.base import build_context
from moonface.models.engine.v3.regime import Regime, VolState, classify_regime
from moonface.models.engine.v3.sizing import size_from_quality


@dataclass(frozen=True)
class DecisionV3:
    action: str
    direction: int
    mechanism: str | None
    regime: Regime
    quality: float | None
    risk_fraction: float
    detail: str


def _wait(regime: Regime, mechanism: str | None, detail: str) -> DecisionV3:
    return DecisionV3("WAIT", 0, mechanism, regime, None, 0.0, detail)


def decide_v3(candles: list[Candle], index: int, cfg: EngineConfigV3) -> DecisionV3:
    regime = classify_regime(candles[: index + 1], cfg)

    if regime.vol_state == VolState.EXTREME:
        return _wait(regime, None, "extreme volatility — standing flat")

    name = select_mechanism(regime)
    if name is None:
        return _wait(
            regime,
            None,
            f"empty cell {regime.dir_state.value}/{regime.vol_state.value} — standing flat",
        )

    ctx = build_context(candles, index, cfg)
    signal = MECHANISMS[name].evaluate(ctx, regime)
    if signal.direction == 0:
        return _wait(regime, name, f"{name} no trigger: {signal.detail}")

    fraction = size_from_quality(name, signal.quality, cfg)
    if fraction == 0.0:
        return _wait(regime, name, f"{name} quality {signal.quality:.3f} below floor")

    return DecisionV3(
        action="ENTER",
        direction=signal.direction,
        mechanism=name,
        regime=regime,
        quality=signal.quality,
        risk_fraction=fraction,
        detail=(
            f"ENTER {name} dir={signal.direction} q={signal.quality:.3f} "
            f"frac={fraction:.4f} [{regime.dir_state.value}/{regime.vol_state.value}]"
        ),
    )
